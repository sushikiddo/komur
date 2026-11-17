"""Compact, cat-anchored Dark Glassmorphism chat HUD."""
import tkinter as tk

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
    WIDTH, HEIGHT = 300, 230

    def __init__(self, assistant):
        self.assistant = assistant
        self.app = assistant.app
        self.window = tk.Toplevel(self.app.root)
        self.window.withdraw()
        self.window.title("Kömür — sohbet")
        self.window.overrideredirect(True)
        try:
            self.window.attributes("-topmost", True)
            self.window.attributes("-alpha", 0.96)
        except tk.TclError:
            pass
        self.window.configure(bg=KEY)
        try:
            self.window.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass

        canvas = tk.Canvas(
            self.window,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=KEY,
            highlightthickness=0,
            borderwidth=0,
        )
        canvas.pack()

        ox, oy = 2, 2
        tail_h = 12
        box_w = self.WIDTH - 4
        box_h = self.HEIGHT - 4 - tail_h
        pts = rounded_bubble_points(
            box_w, box_h, "down", box_w / 2, radius=16, tail_w=16, tail_h=tail_h
        )
        shadow = [c + (ox + 1 if i % 2 == 0 else oy + 2) for p in pts for i, c in enumerate(p)]
        flat = [c + (ox if i % 2 == 0 else oy) for p in pts for i, c in enumerate(p)]
        canvas.create_polygon(*shadow, fill=SHADOW, outline="", joinstyle="round")
        canvas.create_polygon(*flat, fill=FILL, outline=BORDER, width=1.5, joinstyle="round")
        canvas.create_line(
            ox + 16, oy + 2, ox + box_w - 16, oy + 2,
            fill=ACCENT_GLOW, width=1.5, capstyle="round",
        )

        body = tk.Frame(canvas, bg=FILL)
        canvas.create_window(
            12, 8, window=body, anchor="nw", width=self.WIDTH - 24, height=box_h - 14
        )

        header = tk.Frame(body, bg=FILL)
        header.pack(fill="x")
        tk.Label(
            header,
            text="🐾 Kömür AI",
            bg=FILL,
            fg=TEXT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        close_btn = tk.Button(
            header,
            text="×",
            width=2,
            command=self.hide,
            bg=SURFACE,
            fg=MUTED,
            activebackground=HOVER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        close_btn.pack(side="right")
        _bind_hover(close_btn, SURFACE, HOVER, MUTED, TEXT)

        history_btn = tk.Button(
            header,
            text="Geçmiş",
            command=assistant.show_history,
            bg=SURFACE,
            fg=MUTED,
            activebackground=HOVER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=6,
            pady=1,
            highlightthickness=0,
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        history_btn.pack(side="right", padx=(0, 4))
        _bind_hover(history_btn, SURFACE, HOVER, MUTED, TEXT)

        self.status = tk.StringVar(value="Hazırım")
        tk.Label(
            body,
            textvariable=self.status,
            bg=FILL,
            fg=ACCENT_GLOW,
            anchor="w",
            font=("Segoe UI", 8),
        ).pack(fill="x", pady=(1, 3))

        self.messages = tk.Text(
            body,
            wrap="word",
            height=5,
            font=("Segoe UI", 9),
            bg=SURFACE,
            fg=TEXT,
            insertbackground=ACCENT_GLOW,
            selectbackground=HOVER,
            selectforeground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT_GLOW,
            state="disabled",
            padx=6,
            pady=4,
            spacing1=1,
            spacing3=2,
        )
        self.messages.tag_configure("user_label", foreground=ACCENT_GLOW, font=("Segoe UI", 9, "bold"))
        self.messages.tag_configure("bot_label", foreground=BOT_COLOR, font=("Segoe UI", 9, "bold"))
        self.messages.tag_configure("muted", foreground=MUTED)
        self.messages.pack(fill="both", expand=True)

        self.entry = tk.Entry(
            body,
            font=("Segoe UI", 9),
            bg=SURFACE,
            fg=TEXT,
            insertbackground=ACCENT_GLOW,
            selectbackground=HOVER,
            selectforeground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT_GLOW,
        )
        self.entry.pack(fill="x", pady=(5, 5), ipady=3)
        self.entry.bind("<Return>", lambda event: self.send())

        controls = tk.Frame(body, bg=FILL)
        controls.pack(fill="x")

        btn_style = {
            "bg": SURFACE,
            "fg": TEXT,
            "activebackground": HOVER,
            "activeforeground": TEXT,
            "disabledforeground": DISABLED_FG,
            "relief": "flat",
            "bd": 0,
            "padx": 5,
            "pady": 2,
            "highlightthickness": 0,
            "font": ("Segoe UI", 8),
            "cursor": "hand2",
        }

        self.mic_button = tk.Button(
            controls, text="🎤 Konuş", command=assistant.toggle_listening, **btn_style
        )
        self.mic_button.pack(side="left")
        _bind_hover(self.mic_button, SURFACE, HOVER)

        self.screen_button = tk.Button(
            controls, text="🖥️ Ekran", command=assistant.share_screen, **btn_style
        )
        self.screen_button.pack(side="left", padx=(3, 0))
        _bind_hover(self.screen_button, SURFACE, HOVER)

        self.stop_button = tk.Button(
            controls,
            text="⏹ Dur",
            command=self.stop_response,
            state="disabled",
            **btn_style,
        )
        self.stop_button.pack(side="left", padx=(3, 0))
        _bind_hover(self.stop_button, SURFACE, HOVER)

        self.voice_enabled = tk.BooleanVar(value=self.app.settings.get("voice_replies"))
        voice_chk = tk.Checkbutton(
            controls,
            text="🔊 Ses",
            variable=self.voice_enabled,
            command=lambda: assistant.set_voice_enabled(self.voice_enabled.get()),
            bg=FILL,
            fg=MUTED,
            selectcolor=SURFACE,
            activebackground=FILL,
            activeforeground=TEXT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        voice_chk.pack(side="left", padx=3)

        self.send_button = tk.Button(
            controls,
            text="Gönder",
            command=self.send,
            bg=ACCENT_BTN,
            fg="#ffffff",
            activebackground=ACCENT_BTN_HOVER,
            activeforeground="#ffffff",
            disabledforeground="#8b949e",
            relief="flat",
            bd=0,
            padx=7,
            pady=2,
            highlightthickness=0,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        self.send_button.pack(side="right")
        _bind_hover(self.send_button, ACCENT_BTN, ACCENT_BTN_HOVER, "#ffffff", "#ffffff")

        self.window.bind("<Escape>", lambda event: self.hide())
        self._visible = False
        self.partial = ""

    @property
    def visible(self):
        return self._visible and bool(self.window.winfo_exists())

    def show(self):
        self._visible = True
        self.refresh()
        self.window.deiconify()
        self.update_position()
        self.window.lift()
        self.entry.focus_set()

    def hide(self):
        cancel = getattr(self.assistant, "cancel_listening", None)
        if cancel:
            cancel()
        self.stop_response()
        self._visible = False
        self.window.withdraw()

    def stop_response(self):
        cancel = getattr(self.assistant, "cancel_response", None)
        if cancel:
            cancel()
        voice = getattr(self.assistant, "voice", None)
        if voice and hasattr(voice, "stop"):
            voice.stop()
        self.stop_button.configure(state="disabled")

    def update_position(self):
        if not self.visible:
            return
        x, y = self.app.brain.x, self.app.brain.y
        left, top, right, bottom = work_area_at(self.window, x + self.app.w / 2, y)
        px = max(left, min(right - self.WIDTH, x + self.app.w / 2 - self.WIDTH / 2))
        py = y - self.HEIGHT + 12
        if py < top:
            py = y + self.app.h
        py = max(top, min(bottom - self.HEIGHT, py))
        place_window(self.window, px, py, self.WIDTH, self.HEIGHT)

    def refresh(self):
        self.messages.configure(state="normal")
        self.messages.delete("1.0", "end")
        recent = self.assistant.chat_log[-4:]
        for speaker, text in recent:
            tag = "user_label" if speaker == "Sen" else "bot_label"
            self.messages.insert("end", f"{speaker}:", tag)
            self.messages.insert("end", f" {text}\n")
        if self.partial:
            self.messages.insert("end", "Kömür:", "bot_label")
            self.messages.insert("end", f" {self.partial}")
        elif not recent:
            self.messages.insert("end", "Buradayım. Yazabilir veya Konuş'a basabilirsin.", "muted")
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
        self.screen_button.configure(state="disabled" if busy else "normal")
        self.stop_button.configure(state="normal" if busy else "disabled")
        listening = bool(getattr(self.assistant, "listening", False))
        self.mic_button.configure(
            state="normal" if listening else ("disabled" if busy else "normal"),
            text="🎤 Bitir" if listening else "🎤 Konuş",
        )
        self.status.set(
            "Dinliyorum · Bitir ile gönder"
            if listening
            else ("Düşünüyorum…" if busy else "Hazırım")
        )

    def send(self):
        text = self.entry.get().strip()
        if text and self.assistant.send_text(text):
            self.entry.delete(0, "end")

    def destroy(self):
        self._visible = False
        self.window.destroy()
