"""Floating speech bubble for Kömür, drawn in its own transparent window.

The bubble used to be painted inside the cat's small canvas, so long text was
clipped and the font shrank with the cat. ``SpeechBubble`` is a separate
borderless, topmost, color-keyed ``tk.Toplevel`` with a fixed readable font,
pixel-measured word wrapping and screen clamping, so the full text always shows
regardless of the cat's size.

Anchor convention (what cat.py passes):
    ``anchor_x, anchor_y``  screen pixel of the cat window's TOP-LEFT corner
                            (``brain.x``, ``brain.y``)
    ``cat_w``               the cat window's width in pixels (``self.w``)
The tail tip aims at ``(anchor_x + cat_w / 2, anchor_y + HEAD_RATIO * cat_w)``,
i.e. the top of the cat's head. ``tick(now)`` expects ``time.monotonic()``,
the same clock cat.py's main loop uses, and ``show()`` records its expiry on
that clock.

Standard library only (tkinter + ctypes on Windows).
"""
from __future__ import annotations

import sys
import time
import tkinter as tk
import tkinter.font as tkfont

IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

KEY = "#ff00fe"                   # transparent color key (not used by the art)
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 11
MAX_TEXT_WIDTH = 300              # px, wrap width of the text block
MAX_CHARS = 600                   # beyond this the text is trimmed with "…"
PAD_X, PAD_Y = 16, 12             # bubble padding around the text
RADIUS = 16                       # corner radius
TAIL_W, TAIL_H = 18, 14           # tail base width / height
GAP = 6                           # space between tail tip and the cat's head
MARGIN = 2                        # canvas margin so the outline isn't clipped
HEAD_RATIO = 0.10                 # head top = anchor_y + HEAD_RATIO * cat_w
MIN_SECONDS, MAX_SECONDS = 2.5, 30.0
THINK_FRAMES = ("·", "· ·", "· · ·")

FILL = "#161b22"
BORDER = "#30363d"
ACCENT_GLOW = "#58a6ff"
SHADOW = "#090d12"
TEXT = "#f0f6fc"
THINK_TEXT = "#58a6ff"


def default_duration(text):
    """Seconds a message stays visible: 4 s + 0.06 s per character, 2.5..30."""
    n = len(str(text or ""))
    return max(MIN_SECONDS, min(MAX_SECONDS, 4.0 + 0.06 * n))


def trim_text(text, limit=MAX_CHARS):
    """Normalize whitespace per line and cut extremely long text with an ellipsis."""
    text = str(text if text is not None else "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in text.split("\n")]
    text = "\n".join(lines).strip("\n")
    if len(text) > limit:
        text = text[: max(0, limit - 1)].rstrip() + "…"
    return text


def _hwnd(window):
    user32 = ctypes.windll.user32
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    return user32.GetParent(window.winfo_id()) or window.winfo_id()


def place_window(window, x, y, w, h):
    """Move/resize a window to screen pixels without activating it. Uses
    SetWindowPos on Windows so an overrideredirect window honors negative
    (multi-monitor) coordinates; geometry() fallback elsewhere."""
    x, y, w, h = round(x), round(y), max(1, round(w)), max(1, round(h))
    if IS_WINDOWS:
        try:
            user32 = ctypes.windll.user32
            user32.SetWindowPos.argtypes = [
                wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, wintypes.UINT,
            ]
            # SWP_NOZORDER(4) | SWP_NOACTIVATE(16)
            user32.SetWindowPos(_hwnd(window), None, x, y, w, h, 20)
            return
        except (OSError, AttributeError, tk.TclError):
            pass
    try:
        window.geometry(f"{w}x{h}+{x}+{y}")
    except tk.TclError:
        pass


def _no_activate(window):
    """Mark the window WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW so showing it never
    steals keyboard focus and it stays off the taskbar."""
    if not IS_WINDOWS:
        return
    try:
        user32 = ctypes.windll.user32
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        user32.SetWindowLongW.restype = ctypes.c_long
        hwnd = _hwnd(window)
        style = user32.GetWindowLongW(hwnd, -20)        # GWL_EXSTYLE
        style |= 0x08000000 | 0x00000080                # NOACTIVATE | TOOLWINDOW
        user32.SetWindowLongW(hwnd, -20, style)
    except (OSError, AttributeError, tk.TclError):
        pass


def work_area_at(window, x, y):
    """(left, top, right, bottom) of the monitor work area containing (x, y)."""
    if IS_WINDOWS:
        try:
            class MonitorInfo(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                ]
            user32 = ctypes.windll.user32
            user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
            user32.MonitorFromPoint.restype = wintypes.HMONITOR
            user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MonitorInfo)]
            point = wintypes.POINT(int(x), int(y))
            handle = user32.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(info)
            if handle and user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                r = info.rcWork
                return (r.left, r.top, r.right, r.bottom)
        except (OSError, AttributeError, ValueError):
            pass
    try:
        return (0, 0, window.winfo_screenwidth(), window.winfo_screenheight())
    except tk.TclError:
        return (0, 0, 1920, 1080)


def rounded_bubble_points(w, h, mode, tip, radius=RADIUS, tail_w=TAIL_W, tail_h=TAIL_H):
    """Polygon points (canvas coords, box at 0,0..w,h) for a rounded rectangle
    with a tail merged into its edge. ``mode`` is the side the tail is on:
    'down', 'up', 'left' or 'right'; ``tip`` is the tail tip's coordinate along
    that edge (x for down/up, y for left/right). Corner arcs are sampled so
    the whole outline is one crisp polygon."""
    import math
    r = max(2, min(radius, w / 2 - 1, h / 2 - 1))
    steps = 6

    def arc(cx, cy, start_deg, end_deg):
        pts = []
        for i in range(steps + 1):
            a = math.radians(start_deg + (end_deg - start_deg) * i / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return pts

    half = tail_w / 2
    pts = []
    # top edge (left -> right)
    pts += arc(r, r, 180, 270)
    if mode == "up":
        tx = min(max(tip, r + half + 1), w - r - half - 1)
        pts += [(tx - half, 0), (tip, -tail_h), (tx + half, 0)]
    pts += arc(w - r, r, 270, 360)
    if mode == "right":
        ty = min(max(tip, r + half + 1), h - r - half - 1)
        pts += [(w, ty - half), (w + tail_h, tip), (w, ty + half)]
    pts += arc(w - r, h - r, 0, 90)
    if mode == "down":
        tx = min(max(tip, r + half + 1), w - r - half - 1)
        pts += [(tx + half, h), (tip, h + tail_h), (tx - half, h)]
    pts += arc(r, h - r, 90, 180)
    if mode == "left":
        ty = min(max(tip, r + half + 1), h - r - half - 1)
        pts += [(0, ty + half), (-tail_h, tip), (0, ty - half)]
    return pts


class SpeechBubble:
    """A floating speech bubble window. See the module docstring for the anchor
    convention. All methods are safe to call every frame."""

    def __init__(self, root, bounds=None):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.configure(bg=KEY)
        self.window.overrideredirect(True)
        try:
            self.window.attributes("-topmost", True)
        except tk.TclError:
            pass
        if IS_WINDOWS:
            try:
                self.window.wm_attributes("-transparentcolor", KEY)
            except tk.TclError:
                pass
        self.canvas = tk.Canvas(self.window, bg=KEY, highlightthickness=0, borderwidth=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: self.hide())
        self.window.bind("<Button-1>", lambda e: self.hide())
        self.font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE)
        self.bounds = bounds              # optional (l, t, r, b) override
        self.text = ""
        self.thinking = False
        self.until = None
        self._visible = False
        self._destroyed = False
        self._mapped_once = False
        self._anchor = (0, 0, 260)
        self._box = (0, 0)                # text block size (w, h)
        self._size = (0, 0)               # window size (w, h)
        self._mode = "down"
        self._pos = (None, None)
        self._think_phase = -1
        self._think_item = None
        self._last_now = None
        self._anim_start = None
        self._float_dy = 0

    # -- public API ---------------------------------------------------------
    @property
    def visible(self):
        return self._visible and not self._destroyed

    def show(self, text, anchor_x, anchor_y, cat_w, seconds=None, now=None):
        """Show ``text`` above the cat. Repeated calls with the same text only
        refresh the position and expiry (no flicker), so it can be called every
        frame. ``seconds=None`` picks a duration from the text length."""
        if self._destroyed:
            return
        text = trim_text(text)
        if not text:
            self.hide()
            return
        now = time.monotonic() if now is None else now
        if seconds is None:
            seconds = default_duration(text)
        self.until = None if seconds == float("inf") else now + max(0.0, float(seconds))
        newly_opened = not self._visible
        if text != self.text or self.thinking or not self._visible:
            self.text = text
            self.thinking = False
            self._layout_text()
        if newly_opened:
            self._start_float_in(now)
        self.update_position(anchor_x, anchor_y, cat_w)
        self._map()

    def show_thinking(self, anchor_x, anchor_y, cat_w, seconds=None, now=None):
        """Show animated typing dots until ``show()`` replaces them."""
        if self._destroyed:
            return
        now = time.monotonic() if now is None else now
        self.until = None if seconds is None else now + max(0.0, float(seconds))
        newly_opened = not self._visible
        if not self.thinking or not self._visible:
            self.text = ""
            self.thinking = True
            self._think_phase = -1
            self._layout_thinking()
        if newly_opened:
            self._start_float_in(now)
        self.update_position(anchor_x, anchor_y, cat_w)
        self._map()

    def update_position(self, anchor_x, anchor_y, cat_w):
        """Re-aim the bubble at the cat; cheap (one SetWindowPos). Relayouts the
        polygon only if the tail side has to flip."""
        if self._destroyed:
            return
        try:
            anchor_x, anchor_y, cat_w = float(anchor_x), float(anchor_y), float(cat_w)
        except (TypeError, ValueError):
            return
        self._anchor = (anchor_x, anchor_y, cat_w)
        bw, bh = self._box
        if bw <= 0:
            return
        box_w = bw + 2 * PAD_X
        box_h = bh + 2 * PAD_Y
        head_x = anchor_x + cat_w / 2
        head_y = anchor_y + HEAD_RATIO * cat_w
        left, top, right, bottom = self._screen_bounds(head_x, head_y)
        total_w = box_w + 2 * MARGIN
        total_h = box_h + 2 * MARGIN

        # Preferred: above the head, tail down.
        mode = "down"
        x = head_x - total_w / 2
        y = head_y - GAP - TAIL_H - total_h
        if y < top:
            cat_bottom = anchor_y + cat_w * 280 / 260
            mode = "up"
            y = cat_bottom + GAP + TAIL_H
            if y + total_h > bottom:
                # Neither above nor below: put it beside the cat.
                y = min(max(head_y - total_h / 2, top), bottom - total_h)
                if head_x + cat_w / 2 + GAP + TAIL_H + total_w <= right:
                    mode = "left"
                    x = anchor_x + cat_w + GAP + TAIL_H
                else:
                    mode = "right"
                    x = anchor_x - GAP - TAIL_H - total_w
        x = min(max(x, left), max(left, right - total_w))
        y = min(max(y, top), max(top, bottom - total_h))

        if mode in ("down", "up"):
            tip = head_x - x - MARGIN
            win_w, win_h = total_w, total_h + TAIL_H
            win_x = x
            win_y = y - TAIL_H if mode == "up" else y
        else:
            tip = head_y - y - MARGIN
            win_w, win_h = total_w + TAIL_H, total_h
            win_x = x - TAIL_H if mode == "left" else x
            win_y = y
        self._mode = mode
        self._draw_shape(box_w, box_h, mode, tip)
        if (win_w, win_h) != self._size:
            self._size = (win_w, win_h)
            self.canvas.configure(width=win_w, height=win_h)
        self._pos = (win_x, win_y)
        place_window(self.window, win_x, win_y + self._float_dy, win_w, win_h)

    def tick(self, now=None):
        """Call every frame with ``time.monotonic()``: hides the bubble when its
        duration expires and animates the thinking dots and float-in transition."""
        if self._destroyed or not self._visible:
            return
        now = time.monotonic() if now is None else now
        if self.until is not None and now >= self.until:
            self.hide()
            return
        if self._anim_start is not None:
            t_anim = min(1.0, max(0.0, (now - self._anim_start) / 0.18))
            ease = 1.0 - (1.0 - t_anim) ** 3
            try:
                self.window.attributes("-alpha", 0.15 + 0.81 * ease)
            except tk.TclError:
                pass
            float_dy = round((1.0 - ease) * 10)
            if float_dy != self._float_dy:
                self._float_dy = float_dy
                wx, wy = self._pos
                if wx is not None:
                    place_window(self.window, wx, wy + float_dy, *self._size)
            if t_anim >= 1.0:
                self._anim_start = None
                self._float_dy = 0
        if self.thinking:
            phase = int(now * 2.5) % len(THINK_FRAMES)
            if phase != self._think_phase:
                self._think_phase = phase
                if self._think_item is not None:
                    try:
                        self.canvas.itemconfigure(self._think_item, text=THINK_FRAMES[phase])
                    except tk.TclError:
                        pass

    def hide(self):
        if self._destroyed:
            return
        self._visible = False
        self.until = None
        self.text = ""
        self.thinking = False
        self._anim_start = None
        self._float_dy = 0
        try:
            self.window.withdraw()
        except tk.TclError:
            pass

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        self._visible = False
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    # -- internals ----------------------------------------------------------
    def _start_float_in(self, now):
        self._anim_start = now
        self._float_dy = 10
        try:
            self.window.attributes("-alpha", 0.15)
        except tk.TclError:
            pass

    def _screen_bounds(self, x, y):
        if self.bounds is not None:
            try:
                l, t, r, b = self.bounds
                return (float(l), float(t), float(r), float(b))
            except (TypeError, ValueError):
                pass
        return work_area_at(self.window, x, y)

    def _layout_text(self):
        self.canvas.delete("all")
        self._think_item = None
        item = self.canvas.create_text(
            0, 0, text=self.text, anchor="nw", width=MAX_TEXT_WIDTH,
            font=self.font, fill=TEXT, justify="left", tags=("text",),
        )
        x1, y1, x2, y2 = self.canvas.bbox(item)
        self._box = (max(1, x2 - x1), max(1, y2 - y1))

    def _layout_thinking(self):
        self.canvas.delete("all")
        widest = max(THINK_FRAMES, key=self.font.measure)
        self._think_item = self.canvas.create_text(
            0, 0, text=widest, anchor="nw", font=self.font, fill=THINK_TEXT,
            tags=("text",),
        )
        x1, y1, x2, y2 = self.canvas.bbox(self._think_item)
        self._box = (max(1, x2 - x1), max(1, y2 - y1))
        self.canvas.itemconfigure(self._think_item, text=THINK_FRAMES[0])
        self._think_phase = 0

    def _draw_shape(self, box_w, box_h, mode, tip):
        self.canvas.delete("shape")
        ox = MARGIN + (TAIL_H if mode == "left" else 0)
        oy = MARGIN + (TAIL_H if mode == "up" else 0)
        pts = rounded_bubble_points(box_w, box_h, mode, tip)
        shadow = [c + (ox + 2 if i % 2 == 0 else oy + 2) for p in pts for i, c in enumerate(p)]
        flat = [c + (ox if i % 2 == 0 else oy) for p in pts for i, c in enumerate(p)]
        self.canvas.create_polygon(*shadow, fill=SHADOW, outline="", tags=("shape",))
        self.canvas.create_polygon(*flat, fill=FILL, outline=BORDER, width=1.5,
                                   joinstyle="round", tags=("shape",))
        # Upper inner rim neon glow highlight
        r = max(2, min(RADIUS, box_w / 2 - 1, box_h / 2 - 1))
        glow_y = oy + 2
        gx1, gx2 = ox + r, ox + box_w - r
        if gx2 > gx1:
            if mode == "up":
                half = TAIL_W / 2
                tx = min(max(tip, r + half + 1), box_w - r - half - 1)
                tx_abs = ox + tx
                if tx_abs - half - 2 > gx1:
                    self.canvas.create_line(gx1, glow_y, tx_abs - half - 2, glow_y,
                                            fill=ACCENT_GLOW, width=1.5, capstyle="round", tags=("shape",))
                if gx2 > tx_abs + half + 2:
                    self.canvas.create_line(tx_abs + half + 2, glow_y, gx2, glow_y,
                                            fill=ACCENT_GLOW, width=1.5, capstyle="round", tags=("shape",))
            else:
                self.canvas.create_line(gx1, glow_y, gx2, glow_y,
                                        fill=ACCENT_GLOW, width=1.5, capstyle="round", tags=("shape",))
        self.canvas.tag_lower("shape")
        # text block sits at the padded origin
        self.canvas.coords("text", ox + PAD_X, oy + PAD_Y)
        if self.thinking and self._think_item is not None:
            # centre the dots in their reserved box
            self.canvas.itemconfigure(self._think_item, anchor="n")
            self.canvas.coords(self._think_item, ox + PAD_X + self._box[0] / 2, oy + PAD_Y)

    def _map(self):
        if self._visible:
            return
        self._visible = True
        try:
            self.window.deiconify()
            if not self._mapped_once:
                self._mapped_once = True
                self.window.update_idletasks()
                _no_activate(self.window)
            self.window.attributes("-topmost", True)
            self.window.lift()
        except tk.TclError:
            pass
        # deiconify can reset position on some WMs; re-place without activating
        wx, wy = self._pos
        if wx is not None:
            place_window(self.window, wx, wy + self._float_dy, *self._size)
