"""Compact, cat-anchored chat bubble."""
import tkinter as tk
from tkinter import ttk

from bubble import work_area_at, place_window


class ChatBubble:
    WIDTH, HEIGHT = 292, 224

    def __init__(self, assistant):
        self.assistant = assistant
        self.app = assistant.app
        self.window = tk.Toplevel(self.app.root)
        self.window.withdraw()
        self.window.title("Kömür — sohbet")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        key, fill = "#ff00fe", "#fffdf7"
        self.window.configure(bg=key)
        try:
            self.window.attributes("-transparentcolor", key)
        except tk.TclError:
            pass
        canvas = tk.Canvas(self.window, width=self.WIDTH, height=self.HEIGHT, bg=key,
                           highlightthickness=0, borderwidth=0)
        canvas.pack()
        canvas.create_polygon(2, 14, 14, 2, self.WIDTH - 14, 2, self.WIDTH - 2, 14,
                              self.WIDTH - 2, self.HEIGHT - 22, self.WIDTH - 14, self.HEIGHT - 12,
                              self.WIDTH // 2 + 10, self.HEIGHT - 12, self.WIDTH // 2, self.HEIGHT - 1,
                              self.WIDTH // 2 - 10, self.HEIGHT - 12, 14, self.HEIGHT - 12,
                              2, self.HEIGHT - 22, fill=fill, outline="#a8b3bb", smooth=True)
        body = tk.Frame(canvas, bg=fill)
        canvas.create_window(10, 8, window=body, anchor="nw", width=self.WIDTH - 20,
                             height=self.HEIGHT - 30)
        header = tk.Frame(body, bg=fill)
        header.pack(fill="x")
        tk.Label(header, text="Kömür", bg=fill, fg="#172b39",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Button(header, text="Geçmiş", width=7, command=assistant.show_history).pack(side="right", padx=(3, 0))
        ttk.Button(header, text="×", width=2, command=self.hide).pack(side="right")
        self.status = tk.StringVar(value="Hazırım")
        tk.Label(body, textvariable=self.status, bg=fill, fg="#63727b", anchor="w",
                 font=("Segoe UI", 8)).pack(fill="x", pady=(1, 2))
        self.messages = tk.Text(body, wrap="word", height=5, font=("Segoe UI", 9), bg=fill,
                                fg="#22333e", relief="flat", state="disabled", padx=2, pady=1,
                                spacing1=1, spacing3=2)
        self.messages.pack(fill="both", expand=True)
        self.entry = ttk.Entry(body, font=("Segoe UI", 9))
        self.entry.pack(fill="x", pady=(3, 3))
        self.entry.bind("<Return>", lambda event: self.send())
        controls = tk.Frame(body, bg=fill)
        controls.pack(fill="x")
        self.mic_button = ttk.Button(controls, text="Konuş", width=6, command=assistant.toggle_listening)
        self.mic_button.pack(side="left")
        self.screen_button = ttk.Button(controls, text="Ekran", width=6, command=assistant.share_screen)
        self.screen_button.pack(side="left", padx=(3, 0))
        self.stop_button = ttk.Button(controls, text="Dur", width=4, command=self.stop_response,
                                      state="disabled")
        self.stop_button.pack(side="left", padx=(3, 0))
        self.voice_enabled = tk.BooleanVar(value=self.app.settings.get("voice_replies"))
        ttk.Checkbutton(controls, text="Ses", variable=self.voice_enabled,
                        command=lambda: assistant.set_voice_enabled(self.voice_enabled.get())).pack(side="left", padx=3)
        self.send_button = ttk.Button(controls, text="Gönder", width=7, command=self.send)
        self.send_button.pack(side="right")
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
            self.messages.insert("end", f"{speaker}: {text}\n")
        if self.partial:
            self.messages.insert("end", f"Kömür: {self.partial}")
        elif not recent:
            self.messages.insert("end", "Buradayım. Yazabilir veya Konuş'a basabilirsin.")
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
        self.mic_button.configure(state="normal" if listening else ("disabled" if busy else "normal"),
                                  text="Bitir" if listening else "Konuş")
        self.status.set("Dinliyorum · Bitir ile gönder" if listening else ("Düşünüyorum…" if busy else "Hazırım"))

    def send(self):
        text = self.entry.get().strip()
        if text and self.assistant.send_text(text):
            self.entry.delete(0, "end")

    def destroy(self):
        self._visible = False
        self.window.destroy()
