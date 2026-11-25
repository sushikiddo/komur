"""Saydam/üstte pencere ve ekran (monitör) yardımcıları; Windows'ta user32, macOS'ta AppKit
(ctypes ile), değilse Tk geri dönüşü.

Yaprak modül: cat.py, companion.py ve panel.py bunu kullanır; hiçbiri cat'i içe aktarmaz
(cat.py ``__main__`` olarak da çalıştığı için döngüsel içe aktarma ikinci kopya yükler).
"""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
import tkinter as tk
from ctypes import wintypes

from behavior import Bounds

WIDTH, HEIGHT = 260, 280          # logical base size; scaled by the size setting
IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
# Saydam anahtar renk. macOS'ta "systemTransparent" kullanılamaz: Tk eski kareyi o renkle
# boyayarak siler, saydam boyama hiçbir şeyi silmez ve kediler üst üste iz bırakır. Opak saf
# siyah her karede gerçekten siler; Core Image filtresi de saf siyahı saydama çevirir.
MAC_KEY = "#000000"
BG = MAC_KEY if IS_MAC else "#ff00ff"


def apply_color_key(window, key):
    """``key`` rengiyle boyanan pikselleri saydam yap.

    Windows: Tk renk anahtarı. macOS: Tk 9 ``-transparent`` penceresinin saydam alanlarını opak
    saf siyah (#000000) boyuyor; pencere ekrana gelince içerik katmanına saf siyahı saydama
    çeviren bir Core Image filtresi takılır ve pencere gölgesi kapatılır (bkz. ``_mac_key_out_black``).
    Çizimler saf siyah kullanmamalı; kedinin siyahı #0a0d13'tür.
    """
    try:
        if IS_WINDOWS:
            window.wm_attributes("-transparentcolor", key)
        elif IS_MAC:
            window.wm_attributes("-transparent", True)
            # Tk pencere stilini <Map>'ten sonra yeniden uygular (gölgeyi açar, seviyeyi sıfırlar);
            # hemen ve 60ms sonra uygula ki ne titreme kalsın ne de geç oluşan katman kaçsın.
            def _on_map(_event, w=window):
                _mac_apply_window_chrome()
                try:
                    w.after(50, _mac_key_out_black)
                except tk.TclError:
                    pass
            window.bind("<Map>", _on_map, add="+")
            window.bind("<Destroy>", lambda _e: _mac_prune_keyed_windows(), add="+")
    except tk.TclError:
        pass


class _FlatButton(tk.Label):
    """macOS için tk.Button yerine geçen düz düğme: aqua tk.Button bg/fg renklerini yok sayıp
    beyaz yerel düğme çizer. Label renkleri uygular; tıklama ve ``invoke`` komutu çalıştırır."""

    def __init__(self, master=None, command=None, **kw):
        super().__init__(master, **kw)
        self._command = command
        self.bind("<ButtonRelease-1>", lambda event: self.invoke(), add="+")

    def configure(self, cnf=None, **kw):
        if "command" in kw:
            self._command = kw.pop("command")
        return super().configure(cnf, **kw)

    config = configure

    def invoke(self):
        if str(self.cget("state")) != "disabled" and self._command is not None:
            return self._command()
        return None


Button = _FlatButton if IS_MAC else tk.Button


class _CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class _CGSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class _CGRect(ctypes.Structure):
    _fields_ = [("origin", _CGPoint), ("size", _CGSize)]


class _ObjC:
    """Objective-C çalışma zamanına ctypes ile ince erişim (yalnız macOS; ilk kullanımda yüklenir)."""

    def __init__(self):
        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit"))
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreImage.framework/CoreImage")
        lib.objc_getClass.restype = ctypes.c_void_p
        lib.objc_getClass.argtypes = [ctypes.c_char_p]
        lib.sel_registerName.restype = ctypes.c_void_p
        lib.sel_registerName.argtypes = [ctypes.c_char_p]
        lib.object_getClass.restype = ctypes.c_void_p
        lib.object_getClass.argtypes = [ctypes.c_void_p]
        lib.object_getClassName.restype = ctypes.c_char_p
        lib.object_getClassName.argtypes = [ctypes.c_void_p]
        lib.class_getInstanceMethod.restype = ctypes.c_void_p
        lib.class_getInstanceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.method_getImplementation.restype = ctypes.c_void_p
        lib.method_getImplementation.argtypes = [ctypes.c_void_p]
        lib.class_replaceMethod.restype = ctypes.c_void_p
        lib.class_replaceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        self.lib = lib
        vp = ctypes.c_void_p

        def proto(restype, *args):
            return ctypes.CFUNCTYPE(restype, vp, vp, *args)(("objc_msgSend", lib))
        self.send_void = proto(None)
        self.send = proto(vp)
        self.send_obj = proto(vp, vp)
        self.send_obj2 = proto(vp, vp, vp)
        self.send_index = proto(vp, ctypes.c_ulong)
        self.send_int = proto(vp, ctypes.c_int)
        self.get_int = proto(ctypes.c_int)
        self.send_long = proto(None, ctypes.c_long)
        self.get_long = proto(ctypes.c_long)
        self.send_ulong = proto(None, ctypes.c_ulong)
        self.get_ulong = proto(ctypes.c_ulong)
        self.send_bytes = proto(vp, vp, ctypes.c_ulong)
        self.send_bool = proto(None, ctypes.c_bool)
        self.get_bool = proto(ctypes.c_bool)
        self.get_bool_obj = proto(ctypes.c_bool, vp)
        self.send_point = proto(_CGPoint)
        self.send_rect = proto(_CGRect)
        self.utf8 = proto(ctypes.c_char_p)
        self._keyable_installed = False
        self._keyable_imp = None
        self._first_click_installed = False
        self._accepts_first_mouse_imp = None
        self._send_event_imp = None

    def cls(self, name):
        return self.lib.objc_getClass(name.encode())

    def sel(self, name):
        return self.lib.sel_registerName(name.encode())

    def string(self, text):
        return self.send_obj(self.cls("NSString"), self.sel("stringWithUTF8String:"),
                             ctypes.c_char_p(text.encode()))

    def to_str(self, nsstring):
        if not nsstring:
            return ""
        raw = self.utf8(nsstring, self.sel("UTF8String"))
        return raw.decode("utf-8", errors="replace") if raw else ""

    def items(self, array):
        if not array:
            return []
        count = int(self.send(array, self.sel("count")) or 0)
        return [self.send_index(array, self.sel("objectAtIndex:"), i) for i in range(count)]

    def make_keyable(self, nswindow):
        """TKWindow sınıfında canBecomeKeyWindow'u KVO-güvenli olarak etkinleştir (isa değiştirmez)."""
        if not nswindow or self._keyable_installed:
            return
        tk_cls = self.cls("TKWindow")
        if not tk_cls:
            return
        sel_key = self.sel("canBecomeKeyWindow")
        sel_title = self.sel("title")
        method = self.lib.class_getInstanceMethod(tk_cls, sel_key)
        orig_ptr = self.lib.method_getImplementation(method) if method else None
        imp_type = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        orig_fn = imp_type(orig_ptr) if orig_ptr else None

        def _can_become_key(self_ptr, cmd):
            try:
                title = self.to_str(self.send(self_ptr, sel_title))
                if title in _KEYABLE_TITLES:
                    return True
            except Exception:
                pass
            return bool(orig_fn(self_ptr, cmd)) if orig_fn else False

        self._keyable_imp = imp_type(_can_become_key)
        self.lib.class_replaceMethod(
            tk_cls, sel_key, ctypes.cast(self._keyable_imp, ctypes.c_void_p), b"B@:",
        )
        self._keyable_installed = True

    def install_first_click_support(self):
        """macOS ilk tıklama ve odak-çalmayan TKPanel etkileşim desteği:

        Tk 9.1 Aqua'nın ``tkProcessMouseEvent:`` yordamı olay penceresinin ``isKeyWindow`` ve
        ``[NSApp keyWindow]`` olmasını şart koşar; AppKit de pasif pencerelerde ilk tıklamayı
        iletmek için ``acceptsFirstMouse:`` sonucuna bakar. Çerçevesiz ``TKPanel`` (``0x80`` =
        Borderless | NonactivatingPanel) varsayılan olarak ``canBecomeKeyWindow == NO`` döndürür.

        Tk 9.1'in kendi saf yerel (2 komutluk ``mov w0, #1; ret``, sıfır Python/GIL geri çağrısı)
        ``-[TKContentView wantsUpdateLayer]`` IMP'ini ``TKPanel.canBecomeKeyWindow`` ve
        ``TKContentView.acceptsFirstMouse:`` üzerine takarak hem tek tık sevme/sürükleme hem de
        Hızlı Menü düğmelerinin etkin uygulamayı (Chrome vb.) arka plana atmadan çalışmasını sağla.
        """
        if self._first_click_installed:
            return
        try:
            cv_cls = self.cls("TKContentView")
            panel_cls = self.cls("TKPanel")
            yes_method = (
                self.lib.class_getInstanceMethod(cv_cls, self.sel("wantsUpdateLayer"))
                if cv_cls else None
            )
            yes_imp = self.lib.method_getImplementation(yes_method) if yes_method else None
            if yes_imp and panel_cls and cv_cls:
                self.lib.class_replaceMethod(
                    panel_cls, self.sel("canBecomeKeyWindow"), yes_imp, b"B@:",
                )
                self.lib.class_replaceMethod(
                    cv_cls, self.sel("acceptsFirstMouse:"), yes_imp, b"B@:@",
                )
                self._first_click_installed = True
        except Exception:
            pass


_objc = None
_cg_lib = None
_black_key = None              # paylaşılan CIFilter (bir kez kurulur)
_keyed_windows = set()          # filtresi takılmış NSWindow işaretçileri
_NONACTIVATING_PANELS: set[str] = set()   # Tk 9.1 -class nspanel pencere yolları
_panel_seq = 0
_right_click_handlers: dict[str, tuple[tk.Misc, object]] = {}
_last_left_click_was_active: bool = True
_mac_last_rc: int | None = None
_mac_last_lc: int | None = None
_CUBE = 64                     # #0a0d13 gibi koyu renkler ilk hücrenin dışında kalsın diye 64
_KEYABLE_TITLES = {"Kömür — komut"}
_ELEVATED_TITLES = {"Kömür — Hızlı Menü", "Kömür — komut", "Kömür — konuşma"}
_NS_FLOATING_LEVEL = 1000      # kCGScreenSaverWindowLevel: tam ekran video ve Spaces üstünde kalır
_NS_ELEVATED_LEVEL = 1001      # Menü, konuşma ve sohbet balonları her zaman kedilerin üstünde
# CanJoinAllSpaces | Stationary | IgnoresCycle | FullScreenAuxiliary
_NS_COLLECTION_ALL_SPACES = (1 << 0) | (1 << 4) | (1 << 6) | (1 << 8)
_NS_NONACTIVATING_PANEL_MASK = 1 << 7   # NSWindowStyleMaskNonactivatingPanel | Borderless
_NS_DOCMODAL_MASK = 64


def create_nonactivating_panel(master, name: str | None = None) -> tk.Toplevel:
    """macOS Tk 9.1'de yerel odak-çalmayan NSPanel (TKPanel) oluştur; diğer platformlarda Toplevel.

    NSPanel + NonactivatingPanel iki kritik şeyi birden sağlar:
    1) Kediye veya hızlı menüye tıklamak Chrome/VS Code gibi etkin uygulamayı arka plana atmaz.
    2) macOS tam ekran video Space'lerinin üstünde kalır.
    """
    global _panel_seq
    if IS_MAC and master is not None:
        if not name:
            _panel_seq += 1
            name = f"komur_panel_{_panel_seq}"
        parent_w = str(master._w)
        child_w = f".{name}" if parent_w == "." else f"{parent_w}.{name}"
        try:
            master.tk.call("wm", "attributes", child_w, "-class", "nspanel")
            win = tk.Toplevel(master, name=name)
            _NONACTIVATING_PANELS.add(str(win._w))
            return win
        except tk.TclError:
            pass
    return tk.Toplevel(master)


def is_nonactivating_panel(window) -> bool:
    """Pencere macOS Tk 9.1 NonactivatingPanel (TKPanel) olarak mı oluşturuldu?"""
    if not IS_MAC or window is None:
        return False
    try:
        return str(window._w) in _NONACTIVATING_PANELS
    except AttributeError:
        return False


def _objc_runtime():
    global _objc
    if _objc is None:
        _objc = _ObjC()
    return _objc


_INK = (0x0a / 255, 0x0d / 255, 0x13 / 255)   # kedinin dış çizgi rengi (renderer.INK)
# Kenar yumuşatma, çizginin kenarını siyah zeminle karıştırır. 0.032 (~8/255) eşiği saf siyahı
# saydam, kenar geçişini yumuşak tutar; gece (#030509) ve göbek (#080a0e) dahil tüm koyu kürkler
# %100 opak kalır ve arkadaki açık zemin kedinin üstünde gri sızıntı yapmaz.
_KEY_RAMP = 0.032


def _key_color(r, g, b):
    """Küpün bir noktası için önceden çarpılmış (premultiplied) RGBA: siyah saydam, siyah ile
    _KEY_RAMP arası INK renginde kademeli saydam, gerisi aynen opak."""
    level = max(r, g, b)
    if level >= _KEY_RAMP:
        return (r, g, b, 1.0)
    alpha = level / _KEY_RAMP
    return (_INK[0] * alpha, _INK[1] * alpha, _INK[2] * alpha, alpha)


def _black_key_filter(o):
    """sRGB'de saf siyahı saydam yapan, kenar geçişlerini yumuşatan CIColorCubeWithColorSpace filtresi."""
    global _black_key
    if _black_key is None:
        n = _CUBE
        steps = [i / (n - 1) for i in range(n)]
        values = []
        for b in steps:
            for g in steps:
                for r in steps:
                    values.extend(_key_color(r, g, b))
        cube = (ctypes.c_float * len(values))(*values)
        data = o.send_bytes(o.cls("NSData"), o.sel("dataWithBytes:length:"),
                            ctypes.addressof(cube), ctypes.sizeof(cube))
        cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
        cg.CGColorSpaceCreateWithName.restype = ctypes.c_void_p
        cg.CGColorSpaceCreateWithName.argtypes = [ctypes.c_void_p]
        srgb = cg.CGColorSpaceCreateWithName(ctypes.c_void_p.in_dll(cg, "kCGColorSpaceSRGB"))
        key_filter = o.send_obj(o.cls("CIFilter"), o.sel("filterWithName:"),
                                o.string("CIColorCubeWithColorSpace"))
        set_value = o.sel("setValue:forKey:")
        o.send_obj2(key_filter, set_value, o.send_int(o.cls("NSNumber"), o.sel("numberWithInt:"), n),
                    o.string("inputCubeDimension"))
        o.send_obj2(key_filter, set_value, data, o.string("inputCubeData"))
        o.send_obj2(key_filter, set_value, srgb, o.string("inputColorSpace"))
        o.send(key_filter, o.sel("retain"))
        _black_key = key_filter
    return _black_key


def _mac_prune_keyed_windows():
    """Kapanmış NSWindow işaretçilerini önbellekten temizle (dangling pointer önleme)."""
    if not _keyed_windows:
        return
    try:
        o = _objc_runtime()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        live = set(o.items(o.send(app, o.sel("windows"))))
        _keyed_windows.intersection_update(live)
    except (OSError, AttributeError, TypeError, ValueError):
        _keyed_windows.clear()


def _is_tk_nswindow(o, window) -> bool:
    """NSStatusBarWindow / sistem pencerelerini atla; yalnız Tk pencerelerini (TKWindow/TKPanel) işle."""
    try:
        name = o.lib.object_getClassName(window) or b""
        return b"TKWindow" in name or b"TKPanel" in name
    except Exception:
        return False


def _is_tk_nspanel(o, window) -> bool:
    """Pencere Tk 9.1 NSPanel alt sınıfı (TKPanel) mı?"""
    try:
        name = o.lib.object_getClassName(window) or b""
        return b"TKPanel" in name
    except Exception:
        return False


def _mac_apply_window_chrome(order_front=False):
    """Opak olmayan pencerelerin seviye, gölge, zemin, Spaces ve odak-çalmayan panel özelliklerini uygula."""
    try:
        o = _objc_runtime()
        o.install_first_click_support()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        windows = o.items(o.send(app, o.sel("windows")))
        clear = o.send(o.cls("NSColor"), o.sel("clearColor"))
        for window in windows:
            if not _is_tk_nswindow(o, window) or o.get_bool(window, o.sel("isOpaque")):
                continue
            title = o.to_str(o.send(window, o.sel("title")))
            o.send_bool(window, o.sel("setHasShadow:"), False)
            o.send_bool(window, o.sel("setHidesOnDeactivate:"), False)
            o.send_bool(window, o.sel("setCanHide:"), False)
            o.send_obj(window, o.sel("setBackgroundColor:"), clear)
            if _is_tk_nspanel(o, window):
                if o.get_ulong(window, o.sel("styleMask")) != _NS_NONACTIVATING_PANEL_MASK:
                    o.send_ulong(window, o.sel("setStyleMask:"), _NS_NONACTIVATING_PANEL_MASK)
                    _keyed_windows.discard(window)
                o.send_bool(window, o.sel("setFloatingPanel:"), True)
                # NonactivatingPanel (0x80) uygulamayı etkinleştirmeden keyWindow olabilir;
                # Tk 9.1 tkProcessMouseEvent: tıklama teslimi için isKeyWindow == YES şart koşar.
                o.send_bool(window, o.sel("setBecomesKeyOnlyIfNeeded:"), False)
                o.send_bool(window, o.sel("setWorksWhenModal:"), True)
            else:
                style = o.get_ulong(window, o.sel("styleMask"))
                if style & _NS_DOCMODAL_MASK:
                    o.send_ulong(window, o.sel("setStyleMask:"), style & ~_NS_DOCMODAL_MASK)
            target_level = _NS_ELEVATED_LEVEL if title in _ELEVATED_TITLES else _NS_FLOATING_LEVEL
            if o.get_long(window, o.sel("level")) != target_level:
                o.send_long(window, o.sel("setLevel:"), target_level)
            if o.get_ulong(window, o.sel("collectionBehavior")) != _NS_COLLECTION_ALL_SPACES:
                o.send_ulong(window, o.sel("setCollectionBehavior:"), _NS_COLLECTION_ALL_SPACES)
            if title in _KEYABLE_TITLES:
                o.make_keyable(window)
            on_active = o.get_bool(window, o.sel("isOnActiveSpace"))
            if (order_front or not on_active) and o.get_bool(window, o.sel("isVisible")):
                o.send_long(window, o.sel("setLevel:"), target_level)
                o.send_void(window, o.sel("orderFrontRegardless"))
    except (OSError, AttributeError, TypeError, ValueError):
        pass


def _mac_key_out_black():
    """Opak olmayan (``-transparent``) Tk pencerelerine siyah anahtar filtresi, gölgesiz zemin,
    yüzen pencere seviyesi ve gerektiğinde klavye odak yeteneği uygula."""
    try:
        _mac_apply_window_chrome()
        o = _objc_runtime()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        windows = o.items(o.send(app, o.sel("windows")))
        live = set(windows)
        _keyed_windows.intersection_update(live)
        for window in windows:
            if not _is_tk_nswindow(o, window) or o.get_bool(window, o.sel("isOpaque")):
                continue
            view = o.send(window, o.sel("contentView"))
            if not view:
                continue
            o.send_bool(view, o.sel("setWantsLayer:"), True)
            layer = o.send(view, o.sel("layer"))
            if not layer:
                continue
            o.send_bool(layer, o.sel("setOpaque:"), False)
            o.send_obj(layer, o.sel("setBackgroundColor:"), None)
            existing_filters = o.send(layer, o.sel("filters"))
            filter_count = int(o.send(existing_filters, o.sel("count")) or 0) if existing_filters else 0
            if filter_count == 0 or window not in _keyed_windows:
                o.send_bool(view, o.sel("setLayerUsesCoreImageFilters:"), True)
                filters = o.send_obj(o.cls("NSArray"), o.sel("arrayWithObject:"), _black_key_filter(o))
                o.send_obj(layer, o.sel("setFilters:"), filters)
                o.send_bool(view, o.sel("setNeedsDisplay:"), True)
                _keyed_windows.add(window)
    except (OSError, AttributeError, TypeError, ValueError):
        pass


def ensure_floating(window, *, keyable=False, elevated=False):
    """Pencerenin diğer uygulamaların üstünde yüzer seviyede kalmasını garantile."""
    if keyable or elevated:
        try:
            title = window.wm_title()
            if title:
                if keyable:
                    _KEYABLE_TITLES.add(title)
                if elevated:
                    _ELEVATED_TITLES.add(title)
        except tk.TclError:
            pass
    try:
        window.attributes("-topmost", True)
    except tk.TclError:
        pass
    if IS_MAC:
        _mac_apply_window_chrome(order_front=True)
        _mac_key_out_black()
        try:
            window.after(50, _mac_key_out_black)
        except tk.TclError:
            pass


def ensure_topmost_now(window=None):
    """Pencereyi tam ekran video/uygulama üstünde tutmak için anında en öne al."""
    if IS_MAC:
        _mac_apply_window_chrome(order_front=True)
        return
    if IS_WINDOWS and window is not None:
        try:
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            user32.SetWindowPos.argtypes = [
                wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, wintypes.UINT,
            ]
            hwnd = user32.GetParent(window.winfo_id())
            if hwnd:
                # HWND_TOPMOST = -1; SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE = 0x13
                user32.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x0013)
        except (AttributeError, OSError, tk.TclError):
            pass


def mac_windows_on_active_space() -> bool:
    """macOS: görünür Kömür pencerelerinin tümü aktif Space (tam ekran dahil) üstünde mi?"""
    if not IS_MAC:
        return True
    try:
        o = _objc_runtime()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        for window in o.items(o.send(app, o.sel("windows"))):
            if not _is_tk_nswindow(o, window) or o.get_bool(window, o.sel("isOpaque")):
                continue
            if o.get_bool(window, o.sel("isVisible")) and not o.get_bool(window, o.sel("isOnActiveSpace")):
                return False
        return True
    except (OSError, AttributeError, TypeError, ValueError):
        return True


def mac_notch_rect():
    """macOS çentikli MacBook ekranında çentik kutusu (left, top, right, bottom) veya None."""
    if not IS_MAC:
        return None
    try:
        o = _objc_runtime()
        screens = o.items(o.send(o.cls("NSScreen"), o.sel("screens")))
        if not screens:
            return None
        primary_h = o.send_rect(screens[0], o.sel("frame")).size.height
        sel_aux_l = o.sel("auxiliaryTopLeftArea")
        sel_aux_r = o.sel("auxiliaryTopRightArea")
        sel_resp = o.sel("respondsToSelector:")
        for scr in screens:
            if not o.send_obj(scr, sel_resp, sel_aux_l):
                continue
            left_area = o.send_rect(scr, sel_aux_l)
            right_area = o.send_rect(scr, sel_aux_r)
            if left_area.size.width <= 0 or right_area.size.width <= 0:
                continue
            notch_left = round(left_area.origin.x + left_area.size.width)
            notch_right = round(right_area.origin.x)
            notch_h = round(max(left_area.size.height, right_area.size.height))
            if notch_right - notch_left >= 60 and notch_h >= 16:
                f = o.send_rect(scr, o.sel("frame"))
                top = round(primary_h - (f.origin.y + f.size.height))
                return (notch_left, top, notch_right, top + notch_h)
        return None
    except (OSError, AttributeError, TypeError, ValueError):
        return None


def _mac_find_nswindow(window):
    """Tk penceresine karşılık gelen NSWindow işaretçisini başlıkla bul (yoksa None)."""
    if not IS_MAC or window is None:
        return None
    try:
        title = window.wm_title()
        if not title:
            return None
        o = _objc_runtime()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        for nswin in o.items(o.send(app, o.sel("windows"))):
            if _is_tk_nswindow(o, nswin) and o.to_str(o.send(nswin, o.sel("title"))) == title:
                return nswin
    except (OSError, AttributeError, TypeError, ValueError, tk.TclError):
        pass
    return None


def mac_prepare_hidden_panel(window, width: int = 120, height: int = 120) -> bool:
    """macOS TKPanel'i açılışta ekran dışında eşleyip orderOut: ile gizle; sonraki gösterimlerde
    ``deiconify()`` gerekmez, böylece etkin uygulama (Chrome vb.) asla arka plana atılmaz."""
    if not is_nonactivating_panel(window):
        return False
    try:
        place_window(window, -3200, -3200, max(16, int(width)), max(16, int(height)))
        window.deiconify()
        window.update_idletasks()
        _mac_apply_window_chrome()
        nswin = _mac_find_nswindow(window)
        if nswin:
            o = _objc_runtime()
            o.send_obj(nswin, o.sel("orderOut:"), None)
            return True
        window.withdraw()
    except (OSError, AttributeError, TypeError, ValueError, tk.TclError):
        pass
    return False


def mac_hide_nonactivating_panel(window) -> bool:
    """macOS TKPanel'i ``withdraw()`` yerine ``orderOut:`` ile gizle (sonraki gösterimde odak çalmaz)."""
    if not is_nonactivating_panel(window):
        return False
    nswin = _mac_find_nswindow(window)
    if not nswin:
        return False
    try:
        o = _objc_runtime()
        o.send_obj(nswin, o.sel("orderOut:"), None)
        return True
    except (OSError, AttributeError, TypeError, ValueError):
        return False


def mac_present_nonactivating_panel(window, *, make_key: bool = True, elevated: bool = True):
    """macOS'ta odak-çalmayan TKPanel'i (Hızlı Menü / konuşma balonu) etkin uygulamayı
    arka plana atmadan göster; ``make_key=True`` ise Tk düğme tıklamaları için keyWindow yap."""
    if not IS_MAC or window is None:
        return
    try:
        title = window.wm_title()
        if title and elevated:
            _ELEVATED_TITLES.add(title)
        if window.wm_state() == "withdrawn":
            window.deiconify()
        _mac_key_out_black()
        nswin = _mac_find_nswindow(window)
        if nswin:
            o = _objc_runtime()
            level = _NS_ELEVATED_LEVEL if elevated else _NS_FLOATING_LEVEL
            o.send_long(nswin, o.sel("setLevel:"), level)
            if make_key:
                o.send_obj(nswin, o.sel("makeKeyAndOrderFront:"), None)
            else:
                o.send_void(nswin, o.sel("orderFrontRegardless"))
    except (OSError, AttributeError, TypeError, ValueError, tk.TclError):
        pass


def mac_present_key_window(window):
    """macOS'ta çerçevesiz etkileşimli pencereyi (HUD / Sohbet) öne getirip klavye odağı ver."""
    if not IS_MAC:
        return
    try:
        title = window.wm_title()
        if title:
            _KEYABLE_TITLES.add(title)
            _ELEVATED_TITLES.add(title)
        _mac_key_out_black()
        o = _objc_runtime()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        o.send_bool(app, o.sel("activateIgnoringOtherApps:"), True)
        for nswin in o.items(o.send(app, o.sel("windows"))):
            if title and o.to_str(o.send(nswin, o.sel("title"))) == title:
                o.make_keyable(nswin)
                o.send_long(nswin, o.sel("setLevel:"), _NS_ELEVATED_LEVEL)
                o.send_obj(nswin, o.sel("makeKeyAndOrderFront:"), None)
                break
    except (OSError, AttributeError, TypeError, ValueError, tk.TclError):
        pass


def _set_last_left_click_was_active(value: bool) -> None:
    global _last_left_click_was_active
    _last_left_click_was_active = bool(value)


def last_left_click_was_active() -> bool:
    """macOS'ta son sol tıklama gerçekleşmeden önce uygulama zaten etkin miydi?"""
    if not IS_MAC:
        return True
    return bool(_last_left_click_was_active)


def register_mac_right_click(window, callback) -> None:
    """Pencere başlığını macOS TKApplication.sendEvent: sağ-tık yöneticisine kaydet."""
    if window is None or not callable(callback):
        return
    try:
        title = window.wm_title()
    except (tk.TclError, AttributeError):
        return
    if not title:
        return
    _right_click_handlers[title] = (window, callback)

    def _on_destroy(event, w=window, t=title):
        if getattr(event, "widget", None) is w:
            cur = _right_click_handlers.get(t)
            if cur is not None and cur[0] is w:
                _right_click_handlers.pop(t, None)

    try:
        window.bind("<Destroy>", _on_destroy, add="+")
    except (tk.TclError, AttributeError):
        pass
    if IS_MAC:
        try:
            _objc_runtime().install_first_click_support()
        except (OSError, AttributeError, TypeError, ValueError):
            pass


def mac_app_is_active() -> bool:
    """macOS'ta Kömür uygulaması şu an etkin (ön planda) mı?"""
    if not IS_MAC:
        return True
    try:
        o = _objc_runtime()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        return bool(o.get_bool(app, o.sel("isActive")))
    except (OSError, AttributeError, TypeError, ValueError):
        return True


def _cg_events():
    """macOS CoreGraphics olay sayacı işlevlerini tembel yükle (sıfır kanca, sıfır izin istemi)."""
    global _cg_lib
    if _cg_lib is None:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGEventSourceCounterForEventType.argtypes = [ctypes.c_int32, ctypes.c_uint32]
        cg.CGEventSourceCounterForEventType.restype = ctypes.c_uint32
        cg.CGEventSourceFlagsState.argtypes = [ctypes.c_int32]
        cg.CGEventSourceFlagsState.restype = ctypes.c_uint64
        _cg_lib = cg
    return _cg_lib


def mac_right_click_counter() -> int:
    """macOS sistem geneli sağ tık / iki parmak dokunma sayacı (kCGEventRightMouseDown = 3)."""
    if not IS_MAC:
        return 0
    try:
        return int(_cg_events().CGEventSourceCounterForEventType(1, 3))
    except (OSError, AttributeError, TypeError, ValueError):
        return 0


def mac_left_click_counter() -> int:
    """macOS sistem geneli sol tık sayacı (kCGEventLeftMouseDown = 1)."""
    if not IS_MAC:
        return 0
    try:
        return int(_cg_events().CGEventSourceCounterForEventType(1, 1))
    except (OSError, AttributeError, TypeError, ValueError):
        return 0


def mac_control_key_down() -> bool:
    """macOS Control tuşu basılı mı (kCGEventFlagMaskControl = 0x40000)."""
    if not IS_MAC:
        return False
    try:
        return bool(_cg_events().CGEventSourceFlagsState(1) & 0x40000)
    except (OSError, AttributeError, TypeError, ValueError):
        return False


def consume_mac_click_counters() -> None:
    """Tk olayı zaten işlediyse CoreGraphics tık sayaçlarını eşitle (çift tetiklemeyi önle)."""
    global _mac_last_rc, _mac_last_lc
    if not IS_MAC:
        return
    _mac_last_rc = mac_right_click_counter()
    _mac_last_lc = mac_left_click_counter()


def mac_activate_app() -> None:
    """macOS'ta Kömür uygulamasını güvenli biçimde (ana Python iş parçacığından) etkinleştir."""
    if not IS_MAC:
        return
    try:
        o = _objc_runtime()
        app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
        if app and not o.get_bool(app, o.sel("isActive")):
            o.send_bool(app, o.sel("activateIgnoringOtherApps:"), True)
    except (OSError, AttributeError, TypeError, ValueError):
        pass


def _point_in_window(tk_win, px: float, py: float) -> bool:
    try:
        if not tk_win.winfo_viewable():
            return False
        wx = tk_win.winfo_rootx()
        wy = tk_win.winfo_rooty()
        ww = tk_win.winfo_width()
        wh = tk_win.winfo_height()
        return ww > 1 and wh > 1 and wx <= px <= wx + ww and wy <= py <= wy + wh
    except (tk.TclError, AttributeError, TypeError, ValueError):
        return False


def poll_mac_right_clicks(pointer_xy) -> bool:
    """Ana 60 FPS döngüsünden çağrılır: başka bir uygulama etkinken bile kedi üstünde yapılan
    ilk iki parmak dokunma/sağ tık (veya Control+Tık) anında kayıtlı menü geri çağrısını açar.
    """
    global _mac_last_rc, _mac_last_lc
    if not IS_MAC:
        return False
    rc = mac_right_click_counter()
    lc = mac_left_click_counter()
    if _mac_last_rc is None or _mac_last_lc is None:
        _mac_last_rc = rc
        _mac_last_lc = lc
        return False

    right_fired = rc != _mac_last_rc
    left_fired = lc != _mac_last_lc
    _mac_last_rc = rc
    _mac_last_lc = lc

    if not right_fired and not left_fired:
        return False

    is_secondary = right_fired or (left_fired and mac_control_key_down())
    if is_secondary:
        if pointer_xy is None:
            return False
        px, py = pointer_xy
        for tk_win, cb in list(_right_click_handlers.values()):
            if _point_in_window(tk_win, px, py):
                if not is_nonactivating_panel(tk_win):
                    mac_activate_app()
                try:
                    cb(int(round(px)), int(round(py)))
                except Exception:
                    pass
                return True
        return False

    # Normal sol tık: NonactivatingPanel ise etkin uygulamayı (Chrome vb.) asla arka plana atma!
    was_active = mac_app_is_active()
    _set_last_left_click_was_active(was_active)
    if not was_active and pointer_xy is not None:
        px, py = pointer_xy
        for tk_win, _cb in list(_right_click_handlers.values()):
            if _point_in_window(tk_win, px, py):
                if not is_nonactivating_panel(tk_win):
                    mac_activate_app()
                break
    return False


def _mac_screen_areas():
    """[NSScreen screens] visibleFrame'leri (menü çubuğu ve Dock hariç), Tk ekran koordinatında.

    Cocoa'da orijin ana ekranın sol altıdır; Tk'de sol üst. Sidecar/harici ekranlar dahil.
    """
    o = _objc_runtime()
    screens = o.items(o.send(o.cls("NSScreen"), o.sel("screens")))
    if not screens:
        return []
    primary_h = o.send_rect(screens[0], o.sel("frame")).size.height
    areas = []
    for screen in screens:
        r = o.send_rect(screen, o.sel("visibleFrame"))
        left, top = r.origin.x, primary_h - (r.origin.y + r.size.height)
        areas.append(Bounds(round(left), round(top), round(left + r.size.width),
                            round(top + r.size.height)))
    return areas


def enable_dpi_awareness():
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def monitor_bounds(root):
    """Each monitor's usable work area, including monitors left of the primary."""
    if IS_WINDOWS:
        class MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
            ]

        areas = []
        ctypes.windll.user32.GetMonitorInfoW.argtypes = [
            wintypes.HMONITOR, ctypes.POINTER(MonitorInfo)
        ]
        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
            ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
        )

        def collect(handle, dc, rect, data):
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(info)
            if ctypes.windll.user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                r = info.rcWork
                areas.append(Bounds(r.left, r.top, r.right, r.bottom))
            return True

        callback = callback_type(collect)
        ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0)
        if areas:
            return areas
    elif IS_MAC:
        try:
            areas = _mac_screen_areas()
        except (OSError, AttributeError, TypeError):
            areas = []
        if areas:
            return areas
    return [Bounds(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]


def pointer_position(root):
    if IS_WINDOWS:
        point = wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return (point.x, point.y)
    return root.winfo_pointerxy()


def _win_apply_noactivate(window):
    """Windows: kedi/balon pencerelerine WS_EX_NOACTIVATE ekleyerek odak çalmayı önle."""
    if not IS_WINDOWS:
        return
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
        if not hwnd:
            return
        gwl_exstyle = -20
        ws_ex_noactivate = 0x08000000
        style = user32.GetWindowLongW(hwnd, gwl_exstyle)
        if not (style & ws_ex_noactivate):
            user32.SetWindowLongW(hwnd, gwl_exstyle, style | ws_ex_noactivate)
    except (AttributeError, OSError, tk.TclError):
        pass


def make_transparent(window, *, keyable=False, elevated=False):
    """Apply the borderless, topmost, color-keyed transparency to a window."""
    if IS_MAC:
        _mac_prune_keyed_windows()
    if IS_MAC and (keyable or elevated):
        try:
            title = window.wm_title()
            if title:
                if keyable:
                    _KEYABLE_TITLES.add(title)
                if elevated:
                    _ELEVATED_TITLES.add(title)
        except tk.TclError:
            pass
    # macOS: gizlenmemiş yeni Toplevel çerçevesiz yapılınca "docmodal" stiline düşer ve koyu,
    # yuvarlak köşeli bir zemin çizer. Önce gizle, ayarla, görünürdüyse geri göster.
    show_again = IS_MAC and window.wm_state() != "withdrawn"
    if IS_MAC:
        window.withdraw()
    window.configure(bg=BG)
    window.overrideredirect(True)
    window.attributes("-topmost", True)
    apply_color_key(window, BG)
    if IS_WINDOWS and not keyable:
        window.bind("<Map>", lambda _e, w=window: _win_apply_noactivate(w), add="+")
    if show_again:
        window.deiconify()
        ensure_floating(window, keyable=keyable, elevated=elevated)


def place_window(window, x, y, w, h):
    """Move a window to screen pixel (x, y). Uses SetWindowPos on Windows so an
    overrideredirect window honors the request, with a geometry fallback."""
    x, y = round(x), round(y)
    if IS_WINDOWS:
        try:
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            user32.SetWindowPos.argtypes = [
                wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, wintypes.UINT,
            ]
            hwnd = user32.GetParent(window.winfo_id())
            if hwnd:   # harita öncesi çerçeve yok: aşağıdaki geometry yoluna düş
                user32.SetWindowPos(hwnd, None, x, y, w, h, 20)  # NOSIZE off: set both
                return
        except OSError:
            pass
    window.geometry(f"{w}x{h}+{x}+{y}")


def movement_bounds(area, w=WIDTH, h=HEIGHT):
    return Bounds(area.left, area.top, max(area.left, area.right - w),
                  max(area.top, area.bottom - h))


_SHELL_CLASSES = ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd")


def _is_own_window(user32, hwnd):
    """Pencere bu surece (Komur: kedi, HUD, balon, oyuncaklar) aitse True."""
    try:
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
        return int(pid.value) == os.getpid()
    except (AttributeError, OSError, TypeError):
        return False


def _usable_hwnd(user32, hwnd, ignore=None):
    if not hwnd or (ignore and hwnd in ignore) or _is_own_window(user32, hwnd):
        return False
    if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return False
    cls_buf = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, cls_buf, 64)
    return cls_buf.value not in _SHELL_CLASSES


def _rect_of(user32, hwnd):
    rect = wintypes.RECT()
    dwm_ok = False
    try:
        # DWMWA_EXTENDED_FRAME_BOUNDS = 9
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), wintypes.DWORD(9), ctypes.byref(rect), ctypes.sizeof(rect))
        dwm_ok = (hr == 0)
    except (AttributeError, OSError):
        dwm_ok = False
    if not dwm_ok and not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    if rect.right <= rect.left or rect.bottom <= rect.top:
        return None
    return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))


def _ignore_set(ignore_hwnds):
    if ignore_hwnds is None:
        return None
    return {ignore_hwnds} if isinstance(ignore_hwnds, int) else set(ignore_hwnds)


_MAC_SYSTEM_OWNERS = frozenset({
    "Dock", "Window Server", "Wallpaper", "Control Center",
    "Notification Center", "Spotlight", "SystemUIServer", "loginwindow",
})


def _mac_cg_lib():
    cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
    cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
    cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
    cg.CGRectMakeWithDictionaryRepresentation.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(_CGRect),
    ]
    cg.CGRectMakeWithDictionaryRepresentation.restype = ctypes.c_bool
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    return cg, cf


def _mac_cg_windows():
    """macOS ekrandaki normal uygulama pencereleri (kendi sürecimiz ve sistem çubukları hariç)."""
    if not IS_MAC:
        return []
    try:
        o = _objc_runtime()
        cg, cf = _mac_cg_lib()
        # kCGWindowListOptionOnScreenOnly (1) | kCGWindowListExcludeDesktopElements (16)
        arr = cg.CGWindowListCopyWindowInfo(17, 0)
        if not arr:
            return []
        own_pid = os.getpid()
        out = []
        try:
            k_layer = o.string("kCGWindowLayer")
            k_owner = o.string("kCGWindowOwnerName")
            k_name = o.string("kCGWindowName")
            k_num = o.string("kCGWindowNumber")
            k_pid = o.string("kCGWindowOwnerPID")
            k_bounds = o.string("kCGWindowBounds")
            sel_key = o.sel("objectForKey:")
            sel_int = o.sel("intValue")
            for item in o.items(arr):
                layer_obj = o.send_obj(item, sel_key, k_layer)
                layer = o.get_int(layer_obj, sel_int) if layer_obj else -1
                if layer < 0 or layer > 25:
                    continue
                pid_obj = o.send_obj(item, sel_key, k_pid)
                pid = o.get_int(pid_obj, sel_int) if pid_obj else 0
                if pid == own_pid or pid <= 0:
                    continue
                owner = o.to_str(o.send_obj(item, sel_key, k_owner))
                if owner in _MAC_SYSTEM_OWNERS:
                    continue
                bounds_obj = o.send_obj(item, sel_key, k_bounds)
                if not bounds_obj:
                    continue
                rect = _CGRect()
                if not cg.CGRectMakeWithDictionaryRepresentation(bounds_obj, ctypes.byref(rect)):
                    continue
                if rect.size.width < 80 or rect.size.height < 40:
                    continue
                # Yalnız normal pencereler (layer 0) veya ekranı kaplayan tam ekran video katmanları
                if layer != 0 and (rect.size.width < 800 or rect.size.height < 480):
                    continue
                wid_obj = o.send_obj(item, sel_key, k_num)
                wid = o.get_int(wid_obj, sel_int) if wid_obj else 0
                if wid <= 0:
                    continue
                title = o.to_str(o.send_obj(item, sel_key, k_name))
                l, t = round(rect.origin.x), round(rect.origin.y)
                r, b = round(rect.origin.x + rect.size.width), round(rect.origin.y + rect.size.height)
                out.append({"wid": wid, "pid": pid, "owner": owner, "title": title, "rect": (l, t, r, b)})
        finally:
            cf.CFRelease(arr)
        return out
    except (OSError, AttributeError, TypeError, ValueError):
        return []


def mac_foreground_window_info(ignore_hwnds=None):
    """macOS ön plandaki (Kömür hariç) uygulama penceresi bilgisi veya None."""
    if not IS_MAC:
        return None
    ignore = _ignore_set(ignore_hwnds) or set()
    windows = [w for w in _mac_cg_windows() if w["wid"] not in ignore]
    try:
        o = _objc_runtime()
        ws = o.send(o.cls("NSWorkspace"), o.sel("sharedWorkspace"))
        front = o.send(ws, o.sel("frontmostApplication"))
        front_pid = o.get_int(front, o.sel("processIdentifier")) if front else 0
        front_name = o.to_str(o.send(front, o.sel("localizedName"))) if front else ""
        if front_pid and front_pid != os.getpid():
            for w in windows:
                if w["pid"] == front_pid:
                    return w
            if front_name and front_name not in _MAC_SYSTEM_OWNERS:
                return {"wid": 0, "pid": front_pid, "owner": front_name, "title": "", "rect": None}
    except (OSError, AttributeError, TypeError, ValueError):
        pass
    return windows[0] if windows else None


def _mac_dock_rect():
    """macOS Dock alanı (ekran koordinatında); Dock gizliyse ekranın alt şeridi."""
    try:
        o = _objc_runtime()
        screens = o.items(o.send(o.cls("NSScreen"), o.sel("screens")))
        if not screens:
            return None
        frame = o.send_rect(screens[0], o.sel("frame"))
        vis = o.send_rect(screens[0], o.sel("visibleFrame"))
        primary_h = frame.size.height
        left = round(vis.origin.x)
        right = round(vis.origin.x + vis.size.width)
        vis_bottom = round(primary_h - vis.origin.y)
        full_bottom = round(primary_h)
        if full_bottom - vis_bottom >= 16:
            return (left, vis_bottom, right, full_bottom)
        return (left, max(0, vis_bottom - 4), right, vis_bottom)
    except (OSError, AttributeError, TypeError, ValueError):
        return None


def foreground_hwnd(ignore_hwnds=None):
    """On plandaki (kendi sureclerimiz haric) kullanilabilir pencerenin hwnd'si ya da None."""
    if IS_WINDOWS:
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            return int(hwnd) if _usable_hwnd(user32, hwnd, _ignore_set(ignore_hwnds)) else None
        except (AttributeError, OSError):
            return None
    if IS_MAC:
        info = mac_foreground_window_info(ignore_hwnds=ignore_hwnds)
        return int(info["wid"]) if info and info.get("wid") else None
    return None


def window_rect(hwnd):
    """Belirli pencerenin (left, top, right, bottom) kutusu; kapali/kucultulmus/gorunmezse None."""
    if not hwnd:
        return None
    if IS_WINDOWS:
        try:
            user32 = ctypes.windll.user32
            if not _usable_hwnd(user32, hwnd):
                return None
            return _rect_of(user32, hwnd)
        except (AttributeError, OSError):
            return None
    if IS_MAC:
        target = int(hwnd)
        for w in _mac_cg_windows():
            if w["wid"] == target:
                return w["rect"]
        return None
    return None


def active_window_rect(ignore_hwnds=None):
    """On plandaki pencerenin kutusu; Komur'un kendi pencereleri HER ZAMAN yok sayilir."""
    hwnd = foreground_hwnd(ignore_hwnds)
    return window_rect(hwnd) if hwnd else None


def taskbar_rect():
    """Return (left, top, right, bottom) of the taskbar (Windows) or Dock (macOS), or None."""
    if IS_WINDOWS:
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW("Shell_TrayWnd", None)
            if not hwnd or not user32.IsWindowVisible(hwnd):
                return None
            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return None
            if rect.right <= rect.left or rect.bottom <= rect.top:
                return None
            return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
        except (AttributeError, OSError):
            return None
    if IS_MAC:
        return _mac_dock_rect()
    return None


def has_toast_notification():
    """Return True if a visible Windows toast notification window is present."""
    if not IS_WINDOWS:
        return False
    try:
        user32 = ctypes.windll.user32
        if user32.FindWindowW("Windows.UI.Core.CoreWindow", "New notification"):
            return True
        found = False
        cls_buf = ctypes.create_unicode_buffer(128)
        title_buf = ctypes.create_unicode_buffer(128)
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def check(hwnd, _lparam):
            nonlocal found
            if not user32.IsWindowVisible(hwnd):
                return True
            user32.GetClassNameW(hwnd, cls_buf, 128)
            user32.GetWindowTextW(hwnd, title_buf, 128)
            cls_name = cls_buf.value
            title = title_buf.value.lower()
            if cls_name == "Windows.UI.Core.CoreWindow" and (
                "notification" in title or "bildirim" in title or "toast" in title
            ):
                found = True
                return False
            return True

        cb = callback_type(check)
        user32.EnumWindows(cb, 0)
        return found
    except (AttributeError, OSError):
        return False
