"""macOS uyarlaması: uygulama çözümleme, kapatma, ses, otomatik başlatma (gerçek uygulama açmadan)."""
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import autostart
import pc_actions
from pc_actions import PCActions


@pytest.fixture
def mac(monkeypatch, tmp_path):
    apps = tmp_path / "Applications"
    for name in ("TextEdit", "Google Chrome", "Safari", "Notes"):
        (apps / f"{name}.app").mkdir(parents=True)
    monkeypatch.setattr(pc_actions, "IS_MAC", True)
    monkeypatch.setattr(pc_actions, "MAC_APP_DIRS", (apps,))
    calls = []

    def runner(argv, timeout=60):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "closed", "")

    actions = PCActions(popen=calls.append, runner=runner, startfile=lambda t: calls.append(["open", t]),
                        keybd=lambda vk, n=1: calls.append(["key", vk, n]),
                        resolver=pc_actions.resolve_mac_app, plugins=False)
    return actions, calls


def test_catalog_and_mac_only_names_resolve_to_open_a(mac):
    assert pc_actions.resolve_mac_app("not defteri") == ("exec", ["open", "-a", "TextEdit"])
    assert pc_actions.resolve_mac_app("chrome") == ("exec", ["open", "-a", "Google Chrome"])
    assert pc_actions.resolve_mac_app("notlar") == ("exec", ["open", "-a", "Notes"])
    assert pc_actions.resolve_mac_app("valorant") is None


def test_open_app_launches_and_known_mac_names_need_no_confirmation(mac):
    actions, calls = mac
    assert actions.execute("open_app", {"name": "chrome"}) == "Chrome açılıyor."
    assert actions.execute("open_app", {"name": "safari"}).endswith("açılıyor.")
    assert calls == [["open", "-a", "Google Chrome"], ["open", "-a", "Safari"]]
    assert isinstance(actions.execute("open_app", {"name": "gizemli uygulama"}), pc_actions.PendingAction)
    assert "bulunamadı" in actions.open_app("gizemli uygulama")


def test_close_app_quits_through_applescript_without_launching(mac):
    actions, calls = mac
    assert actions.close_app("chrome") == "Chrome kapatıldı."
    script = calls[-1][2]
    assert calls[-1][:2] == ["osascript", "-e"]
    assert 'if application "Google Chrome" is running' in script


def test_volume_uses_absolute_osascript_level(mac):
    actions, calls = mac
    assert actions.set_volume(130) == "Ses seviyesi %100 yapıldı."
    assert calls[-1] == ["osascript", "-e", "set volume output volume 100"]


def test_shutdown_now_only_and_shell_is_zsh(mac):
    actions, calls = mac
    assert "yönetici" in actions.shutdown(5)
    actions.shutdown(0)
    assert calls[-1] == ["osascript", "-e", 'tell application "System Events" to shut down']
    actions.run_command("echo hi")
    assert calls[-1] == ["/bin/zsh", "-c", "echo hi"]


def test_applescript_strings_are_escaped():
    assert pc_actions._applescript_text('a"b\\c') == '"a\\"b\\\\c"'


def test_mac_autostart_writes_and_removes_launch_agent(monkeypatch, tmp_path):
    monkeypatch.setattr(autostart, "_MAC", True)
    monkeypatch.setattr(autostart.Path, "home", lambda: tmp_path)
    assert autostart.available()
    assert autostart.set_enabled(True) is True
    data = plistlib.loads(autostart.mac_plist_path().read_bytes())
    assert data["Label"] == autostart.MAC_LABEL and data["RunAtLoad"] is True
    assert data["ProgramArguments"][0] == sys.executable
    assert autostart.is_enabled()
    assert autostart.set_enabled(False) is False
    assert not autostart.is_enabled()


@pytest.mark.skipif(sys.platform != "darwin", reason="AppKit ekran alanı yalnız macOS'ta")
def test_mac_screen_areas_exclude_menu_bar():
    import window_utils
    areas = window_utils._mac_screen_areas()
    assert areas and areas[0].top > 0 and areas[0].right > areas[0].left


@pytest.mark.skipif(sys.platform != "darwin", reason="AppKit pencere filtresi yalnız macOS'ta")
def test_mac_transparent_window_gets_black_key_and_no_shadow():
    import tkinter as tk
    import window_utils
    root = tk.Tk()
    try:
        root.withdraw()
        window_utils.make_transparent(root)
        root.geometry("80x80+200+200")
        root.deiconify()
        deadline = __import__("time").monotonic() + 3
        while not window_utils._keyed_windows and __import__("time").monotonic() < deadline:
            root.update()
        o = window_utils._objc_runtime()
        window = next(iter(window_utils._keyed_windows))
        assert not o.get_bool(window, o.sel("hasShadow"))
        layer = o.send(o.send(window, o.sel("contentView")), o.sel("layer"))
        assert int(o.send(o.send(layer, o.sel("filters")), o.sel("count"))) == 1
    finally:
        root.destroy()


def test_key_ramp_keeps_ink_and_belly_opaque_but_fades_darker_edge_tones():
    import window_utils
    ink = window_utils._INK
    assert window_utils._key_color(0, 0, 0)[3] == 0.0
    assert window_utils._key_color(*ink)[3] == 1.0
    assert window_utils._key_color(*(c * 0.75 for c in ink))[3] == 1.0      # renderer'daki göbek tonu
    assert window_utils._key_color(0x03 / 255, 0x05 / 255, 0x09 / 255)[3] == 1.0  # gece skini INK
    assert 0 < window_utils._key_color(*(c * 0.3 for c in ink))[3] < 1


@pytest.mark.skipif(sys.platform != "darwin", reason="NSWindow stil maskesi yalnız macOS'ta")
def test_mac_fresh_toplevel_is_not_docmodal_after_make_transparent():
    import ctypes
    import tkinter as tk
    import window_utils
    root = tk.Tk()
    try:
        root.withdraw()
        toy = tk.Toplevel(root)               # oyuncak ve arkadaş kediler böyle açılır (önce gizlenmeden)
        window_utils.make_transparent(toy)
        toy.geometry("30x30+250+250")
        root.update()
        o = window_utils._objc_runtime()
        style = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", o.lib))
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        visible = [w for w in o.items(o.send(app, o.sel("windows"))) if o.get_bool(w, o.sel("isVisible"))]
        assert toy.winfo_ismapped() and visible
        assert all(not style(w, o.sel("styleMask")) & 64 for w in visible)   # 64 = docmodal
        assert all(o.get_long(w, o.sel("level")) >= window_utils._NS_FLOATING_LEVEL for w in visible)
    finally:
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="AppKit yüzer pencere testi yalnız macOS'ta")
def test_mac_companion_and_hud_are_floating_non_docmodal_and_keyable():
    import time
    import types
    import tkinter as tk
    import window_utils
    from companion import Companion
    from context_hud import ModernContextHUD

    root = tk.Tk()
    try:
        root.withdraw()
        window_utils.make_transparent(root)
        root.geometry("143x154+500+400")
        root.deiconify()
        window_utils.ensure_floating(root)

        area = window_utils.monitor_bounds(root)[0]
        mate = Companion(root, area, 0.55, "komur", True, "sakin", start_pos=(330, 400))
        app_stub = types.SimpleNamespace(
            root=root, settings={"name": "Kömür"},
            brain=types.SimpleNamespace(mood="Keyifli"), affection=None, physics=None,
        )
        hud = ModernContextHUD(app_stub)
        hud.show(520, 420)
        for _ in range(12):
            root.update()
            time.sleep(0.01)

        assert mate.window.winfo_ismapped()
        assert hud.visible
        o = window_utils._objc_runtime()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        by_title = {}
        for w in o.items(o.send(app, o.sel("windows"))):
            if not o.get_bool(w, o.sel("isVisible")):
                continue
            by_title.setdefault(o.to_str(o.send(w, o.sel("title"))), []).append(w)
        assert "Kömür — Arkadaş" in by_title
        mate_ns = by_title["Kömür — Arkadaş"][0]
        assert o.get_long(mate_ns, o.sel("level")) >= window_utils._NS_FLOATING_LEVEL
        assert not (o.get_ulong(mate_ns, o.sel("styleMask")) & 64)

        assert "Kömür — Hızlı Menü" in by_title
        hud_ns = by_title["Kömür — Hızlı Menü"][0]
        assert o.get_long(hud_ns, o.sel("level")) >= window_utils._NS_ELEVATED_LEVEL
        hud_style = o.get_ulong(hud_ns, o.sel("styleMask"))
        assert not (hud_style & 64)
        # NonactivatingPanel odak çalmadan tıklanabilir; eski TKWindow ise keyable olmalıdır
        assert bool(hud_style & window_utils._NS_NONACTIVATING_PANEL_MASK) or o.get_bool(hud_ns, o.sel("canBecomeKeyWindow"))
        hud.destroy()
        mate.destroy()
    finally:
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS Dock ve aktivite testi yalnız macOS'ta")
def test_mac_dock_idle_and_app_categorization():
    import awareness
    import context
    import window_utils

    dock = window_utils.taskbar_rect()
    assert dock is not None and dock[2] > dock[0] and dock[3] > dock[1]
    assert context.idle_seconds() >= 0.0
    assert context.categorize("Safari", "")[0] == "browsing"
    assert context.categorize("Visual Studio Code", "")[0] == "coding"
    assert context.categorize("Notes", "")[0] == "office"
    assert context.categorize("Finder", "")[0] == "files"
    assert awareness.is_browser("Safari")
    assert awareness.is_browser("Google Chrome")


@pytest.mark.skipif(sys.platform != "darwin", reason="AppKit lazer penceresi testi yalnız macOS'ta")
def test_mac_laser_dot_window_is_elevated_shadowless_non_docmodal_and_click_through():
    import time
    import tkinter as tk
    import window_utils
    from desktop_toys import _LaserDotWindow

    root = tk.Tk()
    try:
        root.withdraw()
        dot = _LaserDotWindow(root)
        dot.show(400, 350)
        for _ in range(10):
            root.update()
            time.sleep(0.01)

        assert dot.visible
        o = window_utils._objc_runtime()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        laser_wins = [
            w for w in o.items(o.send(app, o.sel("windows")))
            if o.get_bool(w, o.sel("isVisible"))
            and o.to_str(o.send(w, o.sel("title"))) == "Kömür — Lazer"
        ]
        assert laser_wins
        nswin = laser_wins[0]
        assert o.get_long(nswin, o.sel("level")) >= window_utils._NS_ELEVATED_LEVEL
        assert not (o.get_ulong(nswin, o.sel("styleMask")) & 64)
        assert not o.get_bool(nswin, o.sel("hasShadow"))
        assert o.get_bool(nswin, o.sel("ignoresMouseEvents"))
        dot.destroy()
    finally:
        root.destroy()


def test_mac_fullscreen_level_and_collection_constants():
    import window_utils

    assert window_utils._NS_FLOATING_LEVEL >= 1000
    assert window_utils._NS_ELEVATED_LEVEL > window_utils._NS_FLOATING_LEVEL
    cb = window_utils._NS_COLLECTION_ALL_SPACES
    assert cb & (1 << 0)   # CanJoinAllSpaces
    assert cb & (1 << 4)   # Stationary
    assert cb & (1 << 6)   # IgnoresCycle
    assert cb & (1 << 8)   # FullScreenAuxiliary


@pytest.mark.skipif(sys.platform != "darwin", reason="AppKit ilk tık ve tam ekran pencere testi yalnız macOS'ta")
def test_mac_window_hides_on_deactivate_false_and_accepts_first_mouse():
    import time
    import tkinter as tk
    import window_utils

    root = tk.Tk()
    try:
        root.withdraw()
        window_utils.make_transparent(root)
        root.geometry("90x90+240+240")
        root.deiconify()
        window_utils.ensure_floating(root)
        for _ in range(8):
            root.update()
            time.sleep(0.01)

        o = window_utils._objc_runtime()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        visible = [
            w for w in o.items(o.send(app, o.sel("windows")))
            if window_utils._is_tk_nswindow(o, w) and o.get_bool(w, o.sel("isVisible"))
        ]
        assert visible
        nswin = visible[0]
        assert o.get_long(nswin, o.sel("level")) >= window_utils._NS_FLOATING_LEVEL
        assert not o.get_bool(nswin, o.sel("hidesOnDeactivate"))
        cb = o.get_ulong(nswin, o.sel("collectionBehavior"))
        assert (cb & window_utils._NS_COLLECTION_ALL_SPACES) == window_utils._NS_COLLECTION_ALL_SPACES
        assert window_utils.mac_right_click_counter() >= 0
        assert window_utils.mac_left_click_counter() >= 0
    finally:
        root.destroy()


def test_release_does_not_pet_when_pressed_from_inactive_app(monkeypatch, tmp_path):
    import threading
    import tkinter as tk
    import types
    import cat
    import window_utils

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(cat, "Tray", lambda tooltip="": types.SimpleNamespace(
        available=False, poll_show=lambda: False, poll_quit=lambda: False, close=lambda: None,
    ))

    class FakeShortcut:
        def __init__(self):
            self.requested = threading.Event()
            self.boss_requested = threading.Event()
            self.registered = True

        def close(self):
            pass

    monkeypatch.setattr(cat, "PanelShortcut", FakeShortcut)
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel(root)
    win.withdraw()
    app = cat.DesktopCat(root=win)
    try:
        commands = []
        monkeypatch.setattr(app, "command", lambda name: commands.append(name))
        ev = types.SimpleNamespace(x_root=200, y_root=200, state=0)

        # Pasif uygulamadan geçiş tıklaması: sev tetiklenmez
        monkeypatch.setattr(window_utils, "mac_app_is_active", lambda: False)
        app._press(ev)
        app._release(ev)
        assert commands == []

        # Uygulama etkinken tek sol tık: sev tetiklenir
        monkeypatch.setattr(window_utils, "mac_app_is_active", lambda: True)
        app._press(ev)
        app._release(ev)
        assert commands == ["pet"]
    finally:
        if not app.closed:
            app.close()
        root.destroy()


def test_laser_removed_from_hud_and_mac_apps_and_reactions(monkeypatch, tmp_path):
    import threading
    import tkinter as tk
    import types
    import awareness
    import cat
    import context
    import sounds

    # macOS yaygın uygulamaları ve YouTube Music/Video tespiti
    assert context.categorize("Google Chrome", "Lo-fi - YouTube Music") == ("media", "YouTube Music")
    assert context.categorize("Safari", "Film - YouTube") == ("browsing", "YouTube")
    assert context.categorize("Netflix", "")[0] == "media"
    assert context.categorize("VLC", "")[0] == "media"
    assert context.categorize("IINA", "")[0] == "media"
    assert context.categorize("QuickTime Player", "")[0] == "media"
    assert context.categorize("Spotify", "")[0] == "media"
    assert context.categorize("Apple Music", "")[0] == "media"
    assert context.categorize("Cursor", "")[0] == "coding"
    assert context.categorize("Antigravity", "")[0] == "coding"
    assert context.categorize("Terminal", "")[0] == "coding"
    assert all("Mısırım" not in m for m in awareness.REACTIONS["video"]["messages"])

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(cat, "Tray", lambda tooltip="": types.SimpleNamespace(
        available=False, poll_show=lambda: False, poll_quit=lambda: False, close=lambda: None,
    ))

    class FakeShortcut:
        def __init__(self):
            self.requested = threading.Event()
            self.boss_requested = threading.Event()
            self.registered = True

        def close(self):
            pass

    monkeypatch.setattr(cat, "PanelShortcut", FakeShortcut)
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel(root)
    win.withdraw()
    app = cat.DesktopCat(root=win)
    try:
        hud = app.context_hud
        assert hud is not None
        assert "laser" not in hud.action_buttons
        assert len(hud.action_buttons) % 2 == 0

        # Video tepkisi: altyazıyı kapatmamak için alt köşeye doğru gider
        area = app.areas[app.area_index]
        app.brain.move_to((area.left + area.right) * 0.5, area.top + 60)
        app.activity_reactions._reaction = {
            "class": "video", "from_class": "none", "state": "watch",
            "message": None, "still": True, "welcome_back": False,
        }
        app._apply_activity_reaction(1000.0)
        assert app.brain._goal is True
        assert app.brain.target_y >= area.bottom - app.h - 20

        # Away -> coding karşılama: gerinme + chirp sesi
        played = []
        monkeypatch.setattr(sounds, "play", lambda name="meow", **kw: played.append(name))
        app.settings.set("sound", True)
        app.muted = False
        app.brain.command("sleep")
        app.activity_reactions._reaction = {
            "class": "coding", "from_class": "away", "state": "sit",
            "message": awareness.WELCOME_BACK, "still": True, "welcome_back": True,
        }
        app._apply_activity_reaction(2000.0)
        assert app.brain.state == "stretch"
        assert "chirp" in played
    finally:
        if not app.closed:
            app.close()
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="CoreGraphics sağ-tık sayacı yalnız macOS'ta")
def test_mac_send_event_hook_and_right_click_registry(monkeypatch):
    import tkinter as tk
    import window_utils

    root = tk.Tk()
    root.withdraw()
    try:
        win = tk.Toplevel(root)
        win.geometry("120x120+200+200")
        win.title("Kömür — Test Sağ Tık")
        child = tk.Frame(win)
        child.pack()
        win.deiconify()
        root.update()

        received = []
        window_utils.register_mac_right_click(win, lambda x, y: received.append((x, y)))
        assert "Kömür — Test Sağ Tık" in window_utils._right_click_handlers

        # CoreGraphics sayaç artınca pasif uygulamadan bile kayıtlı sağ-tık geri çağrısı tetiklenir
        orig_rc = window_utils._mac_last_rc
        orig_lc = window_utils._mac_last_lc
        try:
            window_utils._mac_last_rc = 10
            window_utils._mac_last_lc = 20
            rc_val = [11]
            monkeypatch.setattr(window_utils, "mac_right_click_counter", lambda: rc_val[0])
            monkeypatch.setattr(window_utils, "mac_left_click_counter", lambda: 20)
            monkeypatch.setattr(window_utils, "mac_activate_app", lambda: None)
            wx, wy = win.winfo_rootx() + 40, win.winfo_rooty() + 40
            assert window_utils.poll_mac_right_clicks((wx, wy)) is True
            assert received == [(wx, wy)]
        finally:
            window_utils._mac_last_rc = orig_rc
            window_utils._mac_last_lc = orig_lc

        # Alt bileşen yok olunca pencerenin kaydı silinmez
        child.destroy()
        root.update_idletasks()
        assert "Kömür — Test Sağ Tık" in window_utils._right_click_handlers

        # Pencere yok olunca kayıt temizlenir
        win.destroy()
        root.update_idletasks()
        assert "Kömür — Test Sağ Tık" not in window_utils._right_click_handlers
    finally:
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_last_left_click_was_active_gates_inactive_pet(monkeypatch, tmp_path):
    import threading
    import tkinter as tk
    import types
    import cat
    import window_utils

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(cat, "Tray", lambda tooltip="": types.SimpleNamespace(
        available=False, poll_show=lambda: False, poll_quit=lambda: False, close=lambda: None,
    ))

    class FakeShortcut:
        def __init__(self):
            self.requested = threading.Event()
            self.boss_requested = threading.Event()
            self.registered = True

        def close(self):
            pass

    monkeypatch.setattr(cat, "PanelShortcut", FakeShortcut)
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel(root)
    win.withdraw()
    app = cat.DesktopCat(root=win)
    try:
        commands = []
        monkeypatch.setattr(app, "command", lambda name: commands.append(name))
        ev = types.SimpleNamespace(x_root=220, y_root=220, state=0)

        # sendEvent: NSApp'i aktifleştirdikten sonra mac_app_is_active() True olsa bile
        # last_left_click_was_active() False olduğu için ilk tık sevme tetiklemez
        monkeypatch.setattr(window_utils, "mac_app_is_active", lambda: True)
        monkeypatch.setattr(window_utils, "last_left_click_was_active", lambda: False)
        app._press(ev)
        app._release(ev)
        assert commands == []

        # Uygulama zaten etkinken tek sol tık sevme tetikler
        monkeypatch.setattr(window_utils, "last_left_click_was_active", lambda: True)
        app._press(ev)
        app._release(ev)
        assert commands == ["pet"]
    finally:
        if not app.closed:
            app.close()
        root.destroy()


def test_strict_sound_whitelist_and_hud_mute_toggle(monkeypatch, tmp_path):
    import threading
    import tkinter as tk
    import types
    import cat
    import panel
    import sounds

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(cat, "Tray", lambda tooltip="": types.SimpleNamespace(
        available=False, poll_show=lambda: False, poll_quit=lambda: False, close=lambda: None,
    ))

    class FakeShortcut:
        def __init__(self):
            self.requested = threading.Event()
            self.boss_requested = threading.Event()
            self.registered = True

        def close(self):
            pass

    monkeypatch.setattr(cat, "PanelShortcut", FakeShortcut)
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel(root)
    win.withdraw()
    app = cat.DesktopCat(root=win)
    try:
        played = []
        monkeypatch.setattr(sounds, "play", lambda name="meow", **kw: played.append(name) if kw.get("enabled", True) else None)
        app.sound_var.set(True)
        app.settings.set("sound", True)
        app.muted = False

        # Oyun, mama, takip, yuvarlanma ve uykuya geçiş: SIFIR ses!
        app.brain._change("sit", duration=5.0)
        app._prev_sound_state = "sit"
        app._effect_state = "sit"
        for cmd in ("play", "feed", "follow", "wander", "roll", "sleep"):
            app.command(cmd)
        assert played == []

        # Uyanma (sleep -> awake): miyav sesi
        app.command("wake")
        assert played == ["meow"]

        # Esneme: yawn sesi
        played.clear()
        app.command("yawn")
        assert played == ["yawn"]

        # Sevme: purr sesi
        played.clear()
        app.command("pet")
        assert played == ["purr"]

        # HUD tek tıkla ses kapatma/açma düğmesi
        hud = app.context_hud
        assert hud is not None
        assert hasattr(hud, "sound_button")
        hud.refresh()
        assert "Açık" in str(hud.sound_button.cget("text"))

        hud.sound_button.invoke()
        assert app.sound_var.get() is False
        assert app.settings.get("sound") is False
        assert app.effect_orchestrator.sound_enabled is False
        assert "Kapalı" in str(hud.sound_button.cget("text"))
        assert "kapatıldı" in app.message

        # Ses kapalıyken sevme, esneme ve uyanma dahil HİÇ ses çalmaz
        played.clear()
        app.command("pet")
        app.command("yawn")
        app.command("sleep")
        app.command("wake")
        assert played == []

        # Tekrar açma
        hud.sound_button.invoke()
        assert app.sound_var.get() is True
        assert app.settings.get("sound") is True
        assert app.effect_orchestrator.sound_enabled is True
        assert "Açık" in str(hud.sound_button.cget("text"))
        assert "açıldı" in app.message

        # Panel on_sound_change senkronizasyonu
        app.sound_var.set(False)
        panel.on_sound_change(app)
        assert app.settings.get("sound") is False
        assert app.effect_orchestrator.sound_enabled is False
        assert "Kapalı" in str(hud.sound_button.cget("text"))
    finally:
        if not app.closed:
            app.close()
        root.destroy()
