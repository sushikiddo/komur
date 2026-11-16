"""A minimal Windows system-tray icon implemented with ctypes (stdlib only).

Follows the same pattern as the panel hotkey: a dedicated daemon thread owns a
message-only window and the tray icon, runs the Win32 message loop, and signals
the Tk loop through threading.Events which it polls. Left/double click asks to
show the panel; right click opens a native popup menu (Panel / Çıkış).

Any failure during setup disables the tray cleanly — the cat keeps running.
"""
from __future__ import annotations
import ctypes
import logging
import sys
import threading

_WINDOWS = sys.platform == "win32"

if _WINDOWS:
    from ctypes import wintypes

    WM_DESTROY = 0x0002
    WM_COMMAND = 0x0111
    WM_CLOSE = 0x0010
    WM_APP = 0x8000
    WM_TRAY = WM_APP + 1
    WM_LBUTTONUP = 0x0202
    WM_LBUTTONDBLCLK = 0x0203
    WM_RBUTTONUP = 0x0205
    NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
    NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x01, 0x02, 0x04
    IDI_APPLICATION = 32512
    IDC_ARROW = 32512
    MF_STRING = 0x0000
    MF_SEPARATOR = 0x0800
    TPM_RIGHTBUTTON = 0x0002
    TPM_RETURNCMD = 0x0100
    CW_USEDEFAULT = 0x80000000 - 0x100000000  # as signed int
    HWND_MESSAGE = -3
    ID_PANEL, ID_QUIT = 1001, 1002

    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                                 wintypes.WPARAM, wintypes.LPARAM)

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_byte * 8)]

    class NOTIFYICONDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", wintypes.WCHAR * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", wintypes.WCHAR * 256),
            ("uVersion", wintypes.UINT),
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
            ("guidItem", GUID),
            ("hBalloonIcon", wintypes.HICON),
        ]

    class WNDCLASS(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]


class Tray:
    def __init__(self, tooltip="Kömür"):
        self.available = False
        self.show_requested = threading.Event()
        self.quit_requested = threading.Event()
        self._tooltip = tooltip
        self._hwnd = None
        self._thread = None
        self._wndproc = None
        self._ready = threading.Event()
        if not _WINDOWS:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(1.0)

    # -- Win32 thread -----------------------------------------------------
    def _run(self):
        try:
            self._setup()
            self.available = True
        except Exception:
            logging.exception("Tray setup failed")
            self.available = False
            self._ready.set()
            return
        self._ready.set()
        try:
            self._pump()
        except Exception:
            logging.exception("Tray message loop failed")
        finally:
            self._remove_icon()

    def _setup(self):
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        # prototypes (pointer-correct on 64-bit)
        k32.GetModuleHandleW.restype = wintypes.HMODULE
        k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        u32.LoadIconW.restype = wintypes.HICON
        u32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        u32.LoadCursorW.restype = wintypes.HANDLE
        u32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        u32.RegisterClassW.restype = wintypes.ATOM
        u32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
        u32.CreateWindowExW.restype = wintypes.HWND
        u32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
        ]
        u32.DefWindowProcW.restype = LRESULT
        u32.DefWindowProcW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        ctypes.windll.shell32.Shell_NotifyIconW.restype = wintypes.BOOL
        ctypes.windll.shell32.Shell_NotifyIconW.argtypes = [
            wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATA)]

        hinst = k32.GetModuleHandleW(None)
        app_icon = ctypes.cast(ctypes.c_void_p(IDI_APPLICATION), wintypes.LPCWSTR)
        arrow = ctypes.cast(ctypes.c_void_p(IDC_ARROW), wintypes.LPCWSTR)
        self._wndproc = WNDPROC(self._on_message)
        cls = WNDCLASS()
        cls.lpfnWndProc = self._wndproc
        cls.hInstance = hinst
        cls.lpszClassName = "KomurTrayWindow"
        cls.hIcon = u32.LoadIconW(None, app_icon)
        cls.hCursor = u32.LoadCursorW(None, arrow)
        u32.RegisterClassW(ctypes.byref(cls))  # may already exist; ignore result
        # a hidden ordinary window (parent=None) is enough to receive the
        # tray callback messages; we never show it.
        self._hwnd = u32.CreateWindowExW(
            0, "KomurTrayWindow", "Komur", 0, 0, 0, 0, 0,
            None, None, hinst, None,
        )
        if not self._hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._icon = u32.LoadIconW(None, app_icon)
        self._add_icon()

    def _nid(self, flags):
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = flags
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._icon
        nid.szTip = self._tooltip[:127]
        return nid

    def _add_icon(self):
        nid = self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _remove_icon(self):
        if not self._hwnd:
            return
        try:
            nid = self._nid(0)
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        except Exception:
            pass

    def _on_message(self, hwnd, msg, wparam, lparam):
        u32 = ctypes.windll.user32
        if msg == WM_TRAY:
            event = lparam & 0xFFFF
            if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self.show_requested.set()
            elif event == WM_RBUTTONUP:
                self._popup_menu()
            return 0
        if msg == WM_COMMAND:
            cmd = wparam & 0xFFFF
            if cmd == ID_PANEL:
                self.show_requested.set()
            elif cmd == ID_QUIT:
                self.quit_requested.set()
            return 0
        if msg == WM_DESTROY:
            u32.PostQuitMessage(0)
            return 0
        return u32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _popup_menu(self):
        u32 = ctypes.windll.user32
        menu = u32.CreatePopupMenu()
        u32.AppendMenuW(menu, MF_STRING, ID_PANEL, "Kontrol paneli")
        u32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        u32.AppendMenuW(menu, MF_STRING, ID_QUIT, "Çıkış")
        pt = wintypes.POINT()
        u32.GetCursorPos(ctypes.byref(pt))
        u32.SetForegroundWindow(self._hwnd)
        cmd = u32.TrackPopupMenu(
            menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self._hwnd, None
        )
        u32.PostMessageW(self._hwnd, 0x0000, 0, 0)  # WM_NULL, classic fix
        u32.DestroyMenu(menu)
        if cmd == ID_PANEL:
            self.show_requested.set()
        elif cmd == ID_QUIT:
            self.quit_requested.set()

    def _pump(self):
        u32 = ctypes.windll.user32
        msg = wintypes.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))

    # -- API used by the Tk loop -----------------------------------------
    def poll_show(self):
        if self.show_requested.is_set():
            self.show_requested.clear()
            return True
        return False

    def poll_quit(self):
        if self.quit_requested.is_set():
            self.quit_requested.clear()
            return True
        return False

    def close(self):
        if _WINDOWS and self._hwnd:
            try:
                ctypes.windll.user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
                ctypes.windll.user32.DestroyWindow(self._hwnd)
            except Exception:
                pass
        self._remove_icon()
