"""Saydam/üstte pencere ve ekran (monitör) yardımcıları; Windows'ta ctypes, değilse Tk geri dönüşü.

Yaprak modül: cat.py, companion.py ve panel.py bunu kullanır; hiçbiri cat'i içe aktarmaz
(cat.py ``__main__`` olarak da çalıştığı için döngüsel içe aktarma ikinci kopya yükler).
"""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

from behavior import Bounds

WIDTH, HEIGHT = 260, 280          # logical base size; scaled by the size setting
BG = "#ff00ff"                    # transparent color key
IS_WINDOWS = sys.platform == "win32"


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
    return [Bounds(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]


def pointer_position(root):
    if IS_WINDOWS:
        point = wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return (point.x, point.y)
    return root.winfo_pointerxy()


def make_transparent(window):
    """Apply the borderless, topmost, color-keyed transparency to a window."""
    window.configure(bg=BG)
    window.overrideredirect(True)
    window.attributes("-topmost", True)
    if IS_WINDOWS:
        window.wm_attributes("-transparentcolor", BG)


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


def foreground_hwnd(ignore_hwnds=None):
    """On plandaki (kendi sureclerimiz haric) kullanilabilir pencerenin hwnd'si ya da None."""
    if not IS_WINDOWS:
        return None
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        return int(hwnd) if _usable_hwnd(user32, hwnd, _ignore_set(ignore_hwnds)) else None
    except (AttributeError, OSError):
        return None


def window_rect(hwnd):
    """Belirli pencerenin (left, top, right, bottom) kutusu; kapali/kucultulmus/gorunmezse None."""
    if not IS_WINDOWS or not hwnd:
        return None
    try:
        user32 = ctypes.windll.user32
        if not _usable_hwnd(user32, hwnd):
            return None
        return _rect_of(user32, hwnd)
    except (AttributeError, OSError):
        return None


def active_window_rect(ignore_hwnds=None):
    """On plandaki pencerenin kutusu; Komur'un kendi pencereleri HER ZAMAN yok sayilir."""
    hwnd = foreground_hwnd(ignore_hwnds)
    return window_rect(hwnd) if hwnd else None


def taskbar_rect():
    """Return (left, top, right, bottom) of the Windows taskbar, or None."""
    if not IS_WINDOWS:
        return None
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
