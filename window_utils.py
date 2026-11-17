"""Saydam/üstte pencere ve ekran (monitör) yardımcıları; Windows'ta ctypes, değilse Tk geri dönüşü.

Yaprak modül: cat.py, companion.py ve panel.py bunu kullanır; hiçbiri cat'i içe aktarmaz
(cat.py ``__main__`` olarak da çalıştığı için döngüsel içe aktarma ikinci kopya yükler).
"""
from __future__ import annotations

import ctypes
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
            hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
            user32.SetWindowPos(hwnd, None, x, y, w, h, 20)  # NOSIZE off: set both
            return
        except OSError:
            pass
    window.geometry(f"{w}x{h}+{x}+{y}")


def movement_bounds(area, w=WIDTH, h=HEIGHT):
    return Bounds(area.left, area.top, max(area.left, area.right - w),
                  max(area.top, area.bottom - h))
