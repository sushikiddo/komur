"""window_utils macOS ObjC köprüsü düzeltmeleri: CGRect dönüşü ABI seçimi ve pencere yıkımı güvenliği."""
import ctypes
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import window_utils


@pytest.mark.parametrize("machine, expected", [
    ("x86_64", "objc_msgSend_stret"),
    ("AMD64", "objc_msgSend_stret"),
    ("arm64", "objc_msgSend"),
    ("aarch64", "objc_msgSend"),
])
def test_rect_msgsend_name_per_arch(machine, expected):
    assert window_utils._rect_msgsend_name(machine) == expected


def test_rect_msgsend_uses_stret_on_x86_64(monkeypatch):
    monkeypatch.setattr(window_utils.platform, "machine", lambda: "x86_64")
    assert window_utils._rect_msgsend_name() == "objc_msgSend_stret"
    monkeypatch.setattr(window_utils.platform, "machine", lambda: "arm64")
    assert window_utils._rect_msgsend_name() == "objc_msgSend"


@pytest.mark.skipif(sys.platform != "darwin", reason="ObjC çalışma zamanı yalnız macOS'ta")
def test_objc_send_rect_binds_stret_entry_on_x86_64(monkeypatch):
    """_ObjC.send_rect x86_64'te objc_msgSend_stret'e, diğer tüm mesajlar objc_msgSend'e bağlanır."""
    bound = []
    real_cfunctype = ctypes.CFUNCTYPE

    def recording_cfunctype(restype, *argtypes):
        proto = real_cfunctype(restype, *argtypes)

        def factory(spec):
            bound.append((restype, spec[0]))
            return proto(("objc_msgSend", spec[1]))   # arm64 kitaplığında _stret yoktur
        return factory

    monkeypatch.setattr(window_utils.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(window_utils.ctypes, "CFUNCTYPE", recording_cfunctype)
    window_utils._ObjC()
    rect_entries = {name for restype, name in bound if restype is window_utils._CGRect}
    other_entries = {name for restype, name in bound if restype is not window_utils._CGRect}
    assert rect_entries == {"objc_msgSend_stret"}
    assert other_entries == {"objc_msgSend"}


class _FakeObjC:
    """_is_tk_nswindow için sahte ObjC: sınıf adı ve windowNumber verir."""

    def __init__(self, name, number):
        self._name, self._number = name, number
        self.lib = type("L", (), {"object_getClassName": staticmethod(lambda _w: self._name)})()

    def sel(self, name):
        return name

    def get_long(self, _window, sel):
        assert sel == "windowNumber"
        return self._number


@pytest.mark.parametrize("name, number, expected", [
    (b"TKWindow", 4242, True),
    (b"NSKVONotifying_TKPanel", 17, True),
    (b"TKWindow", -1, False),       # Tk destroy kapattı, havuzda bekliyor: dokunma
    (b"TKPanel", 0, False),
    (b"NSStatusBarWindow", 99, False),
])
def test_closed_or_foreign_nswindows_are_never_touched(name, number, expected):
    assert window_utils._is_tk_nswindow(_FakeObjC(name, number), 1) is expected


def _tk_root():
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()
    return root


def test_pending_after_is_cancelled_when_window_is_destroyed():
    import tkinter as tk
    root = _tk_root()
    calls, errors = [], []
    root.report_callback_exception = lambda *exc: errors.append(exc)
    try:
        win = tk.Toplevel(root)
        window_utils._mac_after_while_alive(win, 30, lambda: calls.append("fired"))
        win.destroy()
        deadline = __import__("time").monotonic() + 0.3
        while __import__("time").monotonic() < deadline:
            root.update()
        assert calls == [] and errors == []
        keep = tk.Toplevel(root)
        window_utils._mac_after_while_alive(keep, 10, lambda: calls.append("alive"))
        deadline = __import__("time").monotonic() + 0.3
        while not calls and __import__("time").monotonic() < deadline:
            root.update()
        assert calls == ["alive"]
    finally:
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="AppKit yıkım yarışı yalnız macOS'ta")
def test_repeated_transparent_window_teardown_does_not_crash():
    """Eski hata: yıkılmış ``-transparent`` Tk pencereleri ``[NSApp windows]`` içinde kalıyor,
    ``_mac_apply_window_chrome`` onlara setStyleMask: gönderiyor ve süreç ilk birkaç turda
    SIGTRAP/SIGSEGV ile ölüyordu (test_chat_v4 çökmesi). Çökme pytest sürecini öldürür."""
    from types import SimpleNamespace
    from chat_bubble import ChatBubble
    for i in range(10):
        root = _tk_root()
        assistant = SimpleNamespace(
            app=SimpleNamespace(root=root, brain=SimpleNamespace(x=300 + i, y=300), w=140, h=150,
                                settings=SimpleNamespace(get=lambda key: False)),
            chat_log=[("Sen", "Merhaba")], show_history=lambda: None, send_text=lambda value: True)
        ChatBubble(assistant).destroy()       # hiç gösterilmeden yıkılan pencere havuzda kalır
        chat = ChatBubble(assistant)
        try:
            chat.show()
            chat.window.update()
            chat.hide()
        finally:
            chat.destroy()
            root.destroy()
