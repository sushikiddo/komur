"""Native system-tray / menu-bar icon (Windows Win32 ctypes + macOS Tk 9.1 systray).

Windows: dedicated daemon thread owns a hidden window + tray icon (loads bundled
assets/komur.ico with IDI_APPLICATION fallback) and signals the Tk loop via
threading.Events & SimpleQueue.
macOS: native ``tk systray`` menu-bar icon with crisp cat-head graphic & quick menu.
Any failure during setup disables the tray cleanly — the cat keeps running.
"""
from __future__ import annotations
import ctypes
import logging
from pathlib import Path
import queue
import sys
import threading

_WINDOWS = sys.platform == "win32"
_MAC = sys.platform == "darwin"


def _asset_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / name


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
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    MF_STRING = 0x0000
    MF_SEPARATOR = 0x0800
    TPM_RIGHTBUTTON = 0x0002
    TPM_RETURNCMD = 0x0100
    CW_USEDEFAULT = 0x80000000 - 0x100000000
    HWND_MESSAGE = -3
    ID_PANEL = 1001
    ID_QUIT = 1002
    ID_HIDE = 1003
    ID_FEED = 1004
    ID_SOUND = 1005
    ID_PEEK = 1006
    ID_UPDATE = 1007
    ID_FOCUS = 1008
    ID_DOCK = 1009

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
        self._actions: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._tooltip = tooltip
        self._hwnd = None
        self._icon = None
        self._custom_icon = False
        self._thread = None
        self._wndproc = None
        self._ready = threading.Event()
        self._tk_root = None
        self._tk_image = None
        self._tk_menu = None
        self._tk_focus_index = None
        self._focus_label = "🍅 Odak Başlat (25 dk)"
        self._on_toggle_hide = None
        if not _WINDOWS:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(1.0)

    def attach_tk(self, root, on_toggle_hide=None):
        """macOS Tk 9.1 yerel menü çubuğu simgesi (``tk systray``). Windows'ta yok sayılır."""
        if not _MAC or root is None:
            return
        try:
            import tkinter as tk
            if str(root.tk.call("tk", "systray", "exists")) == "1":
                root.tk.call("tk", "systray", "destroy")
            img = tk.PhotoImage(width=18, height=18, master=root)
            # 18x18 Kömür kedi portresi (siyah kulaklı silüet + parlak sarı-yeşil gözler + beyaz göğüs)
            cat_rows = [
                "..................",
                "..##..........##..",
                "..###........###..",
                "..####......####..",
                "..##############..",
                ".################.",
                ".################.",
                ".###YY######YY###.",
                ".###YY######YY###.",
                ".################.",
                ".#######..#######.",
                "..##############..",
                "...###WWWWWW###...",
                "....##WWWWWW##....",
                ".....##WWWW##.....",
                "......######......",
                "..................",
                "..................",
            ]
            palette = {"#": "#141821", "Y": "#e8e348", "W": "#fffaf2"}
            for y, row in enumerate(cat_rows):
                for x, ch in enumerate(row):
                    col = palette.get(ch)
                    if col:
                        img.put(col, to=(x, y, x + 1, y + 1))
            self._tk_root = root
            self._tk_image = img
            self._on_toggle_hide = on_toggle_hide
            menu = tk.Menu(root, tearoff=False)
            if callable(on_toggle_hide):
                menu.add_command(label="Göster / Gizle", command=self._mac_toggle_hide)
            menu.add_command(label="Mama Ver", command=lambda: self._actions.put("feed"))
            menu.add_command(label="Ses Aç / Kapa", command=lambda: self._actions.put("toggle_sound"))
            menu.add_command(label=self._focus_label, command=lambda: self._actions.put("toggle_focus"))
            self._tk_focus_index = menu.index("end")
            menu.add_separator()
            menu.add_command(label="Pencereden Bak", command=lambda: self._actions.put("peek"))
            try:
                import window_utils
                if window_utils.mac_notch_rect() is not None:
                    menu.add_command(label="Çentikten Bak", command=lambda: self._actions.put("notch"))
            except Exception:
                pass
            menu.add_command(label="Dock Üstünde Gez", command=lambda: self._actions.put("dock"))
            menu.add_separator()
            menu.add_command(label="Kontrol Paneli", command=self.show_requested.set)
            menu.add_command(label="Güncellemeleri Denetle", command=lambda: self._actions.put("check_update"))
            menu.add_separator()
            menu.add_command(label="Çıkış", command=self.quit_requested.set)
            self._tk_menu = menu
            root.tk.call(
                "tk", "systray", "create",
                "-image", img,
                "-text", self._tooltip,
                "-button1", root.register(self._mac_left_click),
                "-button3", root.register(self._mac_right_click),
            )
            self.available = True
        except Exception:
            logging.debug("macOS systray attach failed", exc_info=True)

    def _mac_toggle_hide(self):
        if callable(self._on_toggle_hide):
            try:
                self._on_toggle_hide()
            except Exception:
                logging.debug("macOS tray toggle hide failed", exc_info=True)

    def _mac_left_click(self):
        if self._tk_root is not None:
            try:
                if self._tk_root.wm_state() == "withdrawn" and callable(self._on_toggle_hide):
                    self._on_toggle_hide()
                    return
            except Exception:
                pass
        self.show_requested.set()

    def _mac_right_click(self):
        if self._tk_menu is None or self._tk_root is None:
            self.show_requested.set()
            return
        try:
            x, y = self._tk_root.winfo_pointerxy()
            self._tk_menu.tk_popup(x, y)
        except Exception:
            self.show_requested.set()

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

    def _load_win_icon(self, u32):
        """Load custom Kömür .ico if present; fall back cleanly to IDI_APPLICATION."""
        try:
            ico = _asset_path("komur.ico")
            if ico.is_file():
                u32.LoadImageW.restype = wintypes.HANDLE
                u32.LoadImageW.argtypes = [
                    wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                    ctypes.c_int, ctypes.c_int, wintypes.UINT,
                ]
                handle = u32.LoadImageW(None, str(ico), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                if handle:
                    self._custom_icon = True
                    return handle
        except Exception:
            logging.debug("Custom Windows tray icon load failed", exc_info=True)
        app_icon = ctypes.cast(ctypes.c_void_p(IDI_APPLICATION), wintypes.LPCWSTR)
        return u32.LoadIconW(None, app_icon)

    def _setup(self):
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
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
        arrow = ctypes.cast(ctypes.c_void_p(IDC_ARROW), wintypes.LPCWSTR)
        self._icon = self._load_win_icon(u32)
        self._wndproc = WNDPROC(self._on_message)
        cls = WNDCLASS()
        cls.lpfnWndProc = self._wndproc
        cls.hInstance = hinst
        cls.lpszClassName = "KomurTrayWindow"
        cls.hIcon = self._icon
        cls.hCursor = u32.LoadCursorW(None, arrow)
        u32.RegisterClassW(ctypes.byref(cls))
        self._hwnd = u32.CreateWindowExW(
            0, "KomurTrayWindow", "Komur", 0, 0, 0, 0, 0,
            None, None, hinst, None,
        )
        if not self._hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
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
        if _WINDOWS and self._custom_icon and self._icon:
            try:
                ctypes.windll.user32.DestroyIcon(self._icon)
            except Exception:
                pass
            self._custom_icon = False

    def _dispatch_win_cmd(self, cmd):
        if cmd == ID_PANEL:
            self.show_requested.set()
        elif cmd == ID_QUIT:
            self.quit_requested.set()
        elif cmd == ID_HIDE:
            self._actions.put("toggle_hide")
        elif cmd == ID_FEED:
            self._actions.put("feed")
        elif cmd == ID_SOUND:
            self._actions.put("toggle_sound")
        elif cmd == ID_PEEK:
            self._actions.put("peek")
        elif cmd == ID_FOCUS:
            self._actions.put("toggle_focus")
        elif cmd == ID_DOCK:
            self._actions.put("dock")
        elif cmd == ID_UPDATE:
            self._actions.put("check_update")

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
            self._dispatch_win_cmd(wparam & 0xFFFF)
            return 0
        if msg == WM_DESTROY:
            u32.PostQuitMessage(0)
            return 0
        return u32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _popup_menu(self):
        u32 = ctypes.windll.user32
        menu = u32.CreatePopupMenu()
        u32.AppendMenuW(menu, MF_STRING, ID_HIDE, "Göster / Gizle")
        u32.AppendMenuW(menu, MF_STRING, ID_FEED, "Mama Ver")
        u32.AppendMenuW(menu, MF_STRING, ID_SOUND, "Ses Aç / Kapa")
        u32.AppendMenuW(menu, MF_STRING, ID_FOCUS, self._focus_label)
        u32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        u32.AppendMenuW(menu, MF_STRING, ID_PEEK, "Pencereden Bak")
        u32.AppendMenuW(menu, MF_STRING, ID_DOCK, "Görev Çubuğuna İn")
        u32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        u32.AppendMenuW(menu, MF_STRING, ID_PANEL, "Kontrol Paneli")
        u32.AppendMenuW(menu, MF_STRING, ID_UPDATE, "Güncellemeleri Denetle")
        u32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        u32.AppendMenuW(menu, MF_STRING, ID_QUIT, "Çıkış")
        pt = wintypes.POINT()
        u32.GetCursorPos(ctypes.byref(pt))
        u32.SetForegroundWindow(self._hwnd)
        cmd = u32.TrackPopupMenu(
            menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self._hwnd, None
        )
        u32.PostMessageW(self._hwnd, 0x0000, 0, 0)
        u32.DestroyMenu(menu)
        self._dispatch_win_cmd(cmd)

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

    def update_focus_label(self, label: str):
        """Update the Focus/Pomodoro countdown label shown in the menu bar / tray menu."""
        if not label or label == self._focus_label:
            return
        self._focus_label = label
        if _MAC and self._tk_menu is not None and self._tk_focus_index is not None:
            try:
                self._tk_menu.entryconfigure(self._tk_focus_index, label=label)
            except Exception:
                pass

    def poll_action(self) -> str | None:
        try:
            return self._actions.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        if _MAC and self._tk_root is not None:
            try:
                if str(self._tk_root.tk.call("tk", "systray", "exists")) == "1":
                    self._tk_root.tk.call("tk", "systray", "destroy")
            except Exception:
                pass
            self._tk_root = None
            self._tk_image = None
            self._tk_menu = None
        if _WINDOWS and self._hwnd:
            try:
                ctypes.windll.user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
                ctypes.windll.user32.DestroyWindow(self._hwnd)
            except Exception:
                pass
        self._remove_icon()
