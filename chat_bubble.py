"""Kediye bağlı küçük komut yazma baloncuğu (Dark Glassmorphism)."""
import tkinter as tk

from window_utils import IS_MAC, Button, apply_color_key, ensure_floating, mac_present_key_window
from bubble import ACCENT_GLOW, BORDER, FILL, KEY, SHADOW, TEXT, place_window, rounded_bubble_points, work_area_at

SURFACE = "#1f2630"
HOVER = "#283548"
MUTED = "#8b949e"
ACCENT_BTN = "#1f6feb"
ACCENT_BTN_HOVER = "#388bfd"
BOT_COLOR = "#7ee787"
DISABLED_FG = "#484f58"


def _bind_hover(widget, normal_bg, hover_bg, normal_fg=TEXT, hover_fg=TEXT):
    def on_enter(_event):
        if str(widget["state"]) != "disabled":
            widget.configure(bg=hover_bg, fg=hover_fg)

    def on_leave(_event):
        widget.configure(bg=normal_bg, fg=normal_fg)

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


class ChatBubble:
    WIDTH, HEIGHT = 250, 146
    RECENTER_DISTANCE = 250   # kedi balondan bu kadar uzaklaşırsa yeniden konumlan (px)
    LOG_LINES = 3             # gösterilen son mesaj sayısı

    def __init__(self, assistant):
        self.assistant = assistant
        self.app = assistant.app
        self.window = tk.Toplevel(self.app.root)
        self.window.withdraw()
        self.window.title("Kömür — komut")
        self.window.overrideredirect(True)
        try:
            self.window.attributes("-topmost", True)
            self.window.attributes("-alpha", 0.96)
        except tk.TclError:
            pass
        self.window.configure(bg=KEY)
        apply_color_key(self.window, KEY)

        canvas = tk.Canvas(
            self.window, width=self.WIDTH, height=self.HEIGHT, bg=KEY, highlightthickness=0, borderwidth=0,
        )
        canvas.pack()

        ox, oy = 2, 2
        tail_h = 9
        box_w = self.WIDTH - 4
        box_h = self.HEIGHT - 4 - tail_h
        pts = rounded_bubble_points(box_w, box_h, "down", box_w / 2, radius=14, tail_w=14, tail_h=tail_h)
        shadow = [c + (ox + 1 if i % 2 == 0 else oy + 2) for p in pts for i, c in enumerate(p)]
        flat = [c + (ox if i % 2 == 0 else oy) for p in pts for i, c in enumerate(p)]
        canvas.create_polygon(*shadow, fill=SHADOW, outline="", joinstyle="round")
        canvas.create_polygon(*flat, fill=FILL, outline=BORDER, width=1.5, joinstyle="round")
        canvas.create_line(ox + 14, oy + 2, ox + box_w - 14, oy + 2, fill=ACCENT_GLOW, width=1.5, capstyle="round")

        body = tk.Frame(canvas, bg=FILL)
        canvas.create_window(9, 6, window=body, anchor="nw", width=self.WIDTH - 18, height=box_h - 10)

        small = {
            "bg": SURFACE, "fg": MUTED, "activebackground": HOVER, "activeforeground": TEXT,
            "disabledforeground": DISABLED_FG, "relief": "flat", "bd": 0, "padx": 4, "pady": 0,
            "highlightthickness": 0, "font": ("Segoe UI", 9), "cursor": "hand2",
        }

        # Başlık: Kömür + durum (aynı satır) + geçmiş + kapat. Buradan tutup taşınır.
        header = tk.Frame(body, bg=FILL, cursor="fleur")
        header.pack(fill="x")
        title = tk.Label(header, text="🐾 Kömür", bg=FILL, fg=TEXT, font=("Segoe UI", 9, "bold"), cursor="fleur")
        title.pack(side="left")
        self.status = tk.StringVar(value="Hazırım")
        status_label = tk.Label(header, textvariable=self.status, bg=FILL, fg=ACCENT_GLOW, anchor="w",
                                font=("Segoe UI", 7), cursor="fleur")
        status_label.pack(side="left", padx=(5, 0), fill="x", expand=True)
        close_btn = Button(header, text="×", command=self.hide, **small)
        close_btn.pack(side="right")
        _bind_hover(close_btn, SURFACE, HOVER, MUTED, TEXT)
        history_btn = Button(header, text="🕘", command=assistant.show_history, **small)
        history_btn.pack(side="right", padx=(0, 3))
        _bind_hover(history_btn, SURFACE, HOVER, MUTED, TEXT)
        for widget in (header, title, status_label, canvas):
            widget.bind("<ButtonPress-1>", self._drag_start, add="+")
            widget.bind("<B1-Motion>", self._drag_move, add="+")
        self._drag_origin = None

        self.messages = tk.Text(
            body, wrap="word", height=3, font=("Segoe UI", 9), bg=SURFACE, fg=TEXT,
            insertbackground=ACCENT_GLOW, selectbackground=HOVER, selectforeground=TEXT,
            relief="flat", highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT_GLOW,
            state="disabled", padx=5, pady=3, spacing1=1, spacing3=2,
        )
        self.messages.tag_configure("user_label", foreground=ACCENT_GLOW, font=("Segoe UI", 9, "bold"))
        self.messages.tag_configure("bot_label", foreground=BOT_COLOR, font=("Segoe UI", 9, "bold"))
        self.messages.tag_configure("muted", foreground=MUTED)
        self.messages.pack(fill="both", expand=True, pady=(4, 0))

        # Giriş + gönder aynı satırda.
        entry_row = tk.Frame(body, bg=FILL)
        entry_row.pack(fill="x", pady=(4, 3))
        self.send_button = Button(
            entry_row, text="➤", command=self.send, bg=ACCENT_BTN, fg="#ffffff",
            activebackground=ACCENT_BTN_HOVER, activeforeground="#ffffff", disabledforeground="#8b949e",
            relief="flat", bd=0, padx=8, pady=0, highlightthickness=0, font=("Segoe UI", 9, "bold"), cursor="hand2",
        )
        self.send_button.pack(side="right", padx=(4, 0), fill="y")
        _bind_hover(self.send_button, ACCENT_BTN, ACCENT_BTN_HOVER, "#ffffff", "#ffffff")
        self.entry = tk.Entry(
            entry_row, font=("Segoe UI", 9), bg=SURFACE, fg=TEXT, insertbackground=ACCENT_GLOW,
            selectbackground=HOVER, selectforeground=TEXT, relief="flat", highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT_GLOW,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.entry.bind("<Return>", lambda event: self.send())

        self.window.bind("<Escape>", lambda event: self.hide())
        self._visible = False
        self._placed_at = None   # son konumlanmada balonun sol-üst köşesi

    # -- sürükleme -----------------------------------------------------------
    def _drag_start(self, event):
        self._drag_origin = (event.x_root - self.window.winfo_x(), event.y_root - self.window.winfo_y())

    def _drag_move(self, event):
        if not self._drag_origin:
            return
        x, y = event.x_root - self._drag_origin[0], event.y_root - self._drag_origin[1]
        place_window(self.window, x, y, self.WIDTH, self.HEIGHT)
        self._placed_at = (x, y)

    @property
    def visible(self):
        return self._visible and bool(self.window.winfo_exists())

    def show(self):
        self._visible = True
        self.refresh()
        self.window.deiconify()
        self.update_position(force=True)
        self.window.lift()
        if IS_MAC:
            ensure_floating(self.window, keyable=True, elevated=True)
            mac_present_key_window(self.window)
            self.entry.focus_force()
        else:
            self.entry.focus_set()

    def hide(self):
        self._visible = False
        self.window.withdraw()

    def _target_position(self):
        x, y = self.app.brain.x, self.app.brain.y
        left, top, right, bottom = work_area_at(self.window, x + self.app.w / 2, y)
        px = max(left, min(right - self.WIDTH, x + self.app.w / 2 - self.WIDTH / 2))
        py = y - self.HEIGHT + 12
        if py < top:
            py = y + self.app.h
        py = max(top, min(bottom - self.HEIGHT, py))
        return px, py

    def update_position(self, force=False):
        """Açılışta konumlan; sonrasında kediyi kovalama, yalnız kedi çok uzaklaşınca yeniden konumlan."""
        if not self.visible:
            return
        if not force and self._placed_at is not None:
            cat_x = self.app.brain.x + self.app.w / 2
            cat_y = self.app.brain.y + self.app.h / 2
            bubble_x = self._placed_at[0] + self.WIDTH / 2
            bubble_y = self._placed_at[1] + self.HEIGHT / 2
            if ((cat_x - bubble_x) ** 2 + (cat_y - bubble_y) ** 2) ** 0.5 <= self.RECENTER_DISTANCE:
                return
        px, py = self._target_position()
        place_window(self.window, px, py, self.WIDTH, self.HEIGHT)
        self._placed_at = (px, py)

    def refresh(self):
        self.messages.configure(state="normal")
        self.messages.delete("1.0", "end")
        recent = self.assistant.chat_log[-self.LOG_LINES:]
        for speaker, text in recent:
            tag = "user_label" if speaker == "Sen" else "bot_label"
            self.messages.insert("end", f"{speaker}:", tag)
            self.messages.insert("end", f" {text}\n")
        if not recent:
            self.messages.insert("end", "Komut yaz: 'not defterini aç', 'uyu', 'dans et'…", "muted")
        self.messages.configure(state="disabled")
        self.messages.see("end")

    def set_partial(self, text):
        """Akan (henüz kesinleşmemiş) yanıt; kalıcı sohbet kaydına yazılmaz."""
        text = str(text or "")
        if text == self.partial:
            return
        self.partial = text
        if self.visible:
            self.refresh()

    def set_busy(self, busy):
        self.send_button.configure(state="disabled" if busy else "normal")
        self.status.set("Yapıyorum…" if busy else "Hazırım")

    def send(self):
        text = self.entry.get().strip()
        if text and self.assistant.send_text(text):
            self.entry.delete(0, "end")

    def destroy(self):
        self._visible = False
        self.window.destroy()
