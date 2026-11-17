"""Modern Dark Glassmorphism right-click quick action HUD for Kömür."""
from __future__ import annotations

import tkinter as tk

from bubble import ACCENT_GLOW, BORDER, FILL, KEY, SHADOW, TEXT, place_window, rounded_bubble_points, work_area_at

SURFACE = "#1f2630"
HOVER = "#283548"
MUTED = "#8b949e"
BADGE_BG = "#1b2838"
XP_PER_LEVEL = 100
DANGER_HOVER = "#b62324"
HEART_COLOR = "#f778ba"

ACCESSORY_ORDER = [
    None,
    "bow",
    "scarf",
    "hat",
    "glasses",
    "witch_hat",
    "winter_set",
    "cyberpunk_collar",
    "headphones",
]

ACCESSORY_LABELS = {
    None: "Yok",
    "bow": "Papyon",
    "scarf": "Atkı",
    "hat": "Şapka",
    "glasses": "Gözlük",
    "witch_hat": "Cadı Şapkası",
    "winter_set": "Kış Seti",
    "cyberpunk_collar": "Siber Tasma",
    "headphones": "Kulaklık",
}


class ModernContextHUD:
    """Frameless Dark Glassmorphism right-click HUD with affection bar,
    2-column action cards, and bottom quick interaction pills.
    """

    WIDTH = 316
    HEIGHT = 368

    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title("Kömür — Hızlı Menü")
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

        self._visible = False
        self._destroyed = False
        self._focus_check_id = None
        self.action_buttons: dict[str, tk.Button] = {}
        self.pill_buttons: dict[str, tk.Button] = {}

        self.canvas = tk.Canvas(
            self.window,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=KEY,
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack()
        self._draw_backdrop()

        self.body = tk.Frame(self.canvas, bg=FILL)
        self.canvas.create_window(
            14, 12, window=self.body, anchor="nw",
            width=self.WIDTH - 28, height=self.HEIGHT - 24,
        )

        self._build_header()
        self._build_affection_bar()
        self._build_action_grid()
        self._build_pills()

        self.window.bind("<Escape>", lambda _e: self.hide())
        self.window.bind("<FocusOut>", self._on_focus_out)

    @property
    def visible(self) -> bool:
        return self._visible and not self._destroyed and bool(self.window.winfo_exists())

    # -- UI construction ----------------------------------------------------
    def _draw_backdrop(self):
        ox, oy = 3, 3
        box_w, box_h = self.WIDTH - 6, self.HEIGHT - 6
        pts = rounded_bubble_points(box_w, box_h, "none", 0, radius=16, tail_w=0, tail_h=0)
        shadow = [c + (ox + 1 if i % 2 == 0 else oy + 2) for p in pts for i, c in enumerate(p)]
        flat = [c + (ox if i % 2 == 0 else oy) for p in pts for i, c in enumerate(p)]
        self.canvas.create_polygon(*shadow, fill=SHADOW, outline="", joinstyle="round")
        self.canvas.create_polygon(*flat, fill=FILL, outline=BORDER, width=1.5, joinstyle="round")
        self.canvas.create_line(
            ox + 16, oy + 2, ox + box_w - 16, oy + 2,
            fill=ACCENT_GLOW, width=1.5, capstyle="round",
        )

    def _build_header(self):
        header = tk.Frame(self.body, bg=FILL)
        header.pack(fill="x", pady=(0, 6))

        self.name_var = tk.StringVar(value="🐾 Kömür")
        tk.Label(
            header,
            textvariable=self.name_var,
            bg=FILL,
            fg=TEXT,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")

        self.mood_var = tk.StringVar(value="Keyifli")
        self.mood_badge = tk.Label(
            header,
            textvariable=self.mood_var,
            bg=BADGE_BG,
            fg=ACCENT_GLOW,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.mood_badge.pack(side="right")

    def _build_affection_bar(self):
        wrap = tk.Frame(self.body, bg=FILL)
        wrap.pack(fill="x", pady=(0, 8))

        top_row = tk.Frame(wrap, bg=FILL)
        top_row.pack(fill="x", pady=(0, 3))
        self.affection_label_var = tk.StringVar(value="♥ Dostluk Sv.1")
        self.affection_xp_var = tk.StringVar(value="0 / 100 XP")
        tk.Label(
            top_row,
            textvariable=self.affection_label_var,
            bg=FILL,
            fg=TEXT,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")
        tk.Label(
            top_row,
            textvariable=self.affection_xp_var,
            bg=FILL,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(side="right")

        bar_w = self.WIDTH - 28
        self.xp_canvas = tk.Canvas(
            wrap,
            width=bar_w,
            height=7,
            bg=SURFACE,
            highlightthickness=1,
            highlightbackground=BORDER,
            borderwidth=0,
        )
        self.xp_canvas.pack(fill="x")
        self._xp_bar_width = bar_w
        self._xp_fill_item = self.xp_canvas.create_rectangle(
            0, 0, 0, 7, fill=ACCENT_GLOW, outline=""
        )

    def _build_action_grid(self):
        grid = tk.Frame(self.body, bg=FILL)
        grid.pack(fill="both", expand=True, pady=(0, 8))
        grid.columnconfigure(0, weight=1, uniform="cards")
        grid.columnconfigure(1, weight=1, uniform="cards")

        cards = [
            ("fish", "🐟 Balık Avı", self._action_fish),
            ("box", "📦 Kutu Bırak", self._action_box),
            ("laser", "🔴 Lazer Aç", self._action_laser),
            ("perch", "🪟 Pencereye Tüne", self._action_perch),
            ("accessory", "👓 Aksesuarlar", self._action_accessory),
            ("lofi", "☕ Odak / Lofi", self._action_lofi_focus),
            ("duck", "🦆 Lastik Ördek", self._action_rubber_duck),
            ("panel", "⚙️ Kontrol Paneli", self._action_panel),
        ]

        for idx, (key, label, callback) in enumerate(cards):
            border_frame = tk.Frame(grid, bg=BORDER, padx=1, pady=1)
            border_frame.grid(
                row=idx // 2,
                column=idx % 2,
                padx=(0 if idx % 2 == 0 else 4, 4 if idx % 2 == 0 else 0),
                pady=3,
                sticky="nsew",
            )
            btn = tk.Button(
                border_frame,
                text=label,
                command=lambda fn=callback: self._run_and_hide(fn),
                bg=SURFACE,
                fg=TEXT,
                activebackground=HOVER,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                anchor="w",
                padx=8,
                pady=7,
                highlightthickness=0,
                font=("Segoe UI", 9),
                cursor="hand2",
            )
            btn.pack(fill="both", expand=True)
            btn.bind("<Enter>", lambda _e, b=btn, f=border_frame: (
                b.configure(bg=HOVER), f.configure(bg=ACCENT_GLOW)
            ))
            btn.bind("<Leave>", lambda _e, b=btn, f=border_frame: (
                b.configure(bg=SURFACE), f.configure(bg=BORDER)
            ))
            self.action_buttons[key] = btn

    def _build_pills(self):
        tk.Frame(self.body, bg=BORDER, height=1).pack(fill="x", pady=(0, 7))
        row = tk.Frame(self.body, bg=FILL)
        row.pack(fill="x")

        pills = [
            ("pet", "♥ Sev", lambda: self._run_command("pet"), HEART_COLOR, HOVER),
            ("feed", "🍖 Mama", lambda: self._run_command("feed"), TEXT, HOVER),
            ("play", "🎾 Oyna", lambda: self._run_command("play"), TEXT, HOVER),
            ("sleep", "💤 Uyu", lambda: self._run_command("sleep"), TEXT, HOVER),
            ("hide", "🕵️ Gizle", self._action_hide, MUTED, HOVER),
            ("close", "✕ Kapat", self._action_close, MUTED, DANGER_HOVER),
        ]

        for idx, (key, label, callback, fg_color, hover_bg) in enumerate(pills):
            pill = tk.Button(
                row,
                text=label,
                command=lambda fn=callback, is_close=(key == "close"): (
                    fn() if is_close else self._run_and_hide(fn)
                ),
                bg=SURFACE,
                fg=fg_color,
                activebackground=hover_bg,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                padx=5,
                pady=4,
                highlightthickness=1,
                highlightbackground=BORDER,
                font=("Segoe UI", 8),
                cursor="hand2",
            )
            pill.pack(side="left", expand=True, fill="x", padx=(0 if idx == 0 else 2, 0))
            pill.bind("<Enter>", lambda _e, p=pill, hb=hover_bg: p.configure(bg=hb, fg=TEXT))
            pill.bind("<Leave>", lambda _e, p=pill, fc=fg_color: p.configure(bg=SURFACE, fg=fc))
            self.pill_buttons[key] = pill

    # -- lifecycle ----------------------------------------------------------
    def show(self, x_root: int, y_root: int):
        if self._destroyed:
            return
        self._cancel_focus_check()
        self.refresh()
        left, top, right, bottom = work_area_at(self.window, x_root, y_root)
        px = max(left, min(right - self.WIDTH, int(x_root) + 8))
        py = max(top, min(bottom - self.HEIGHT, int(y_root) - self.HEIGHT // 2))
        self._visible = True
        try:
            self.window.deiconify()
            place_window(self.window, px, py, self.WIDTH, self.HEIGHT)
            self.window.attributes("-topmost", True)
            self.window.lift()
            self.window.focus_force()
        except tk.TclError:
            pass

    def hide(self):
        if self._destroyed:
            return
        self._cancel_focus_check()
        self._visible = False
        try:
            self.window.withdraw()
        except tk.TclError:
            pass

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        self._visible = False
        self._cancel_focus_check()
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def refresh(self):
        settings = getattr(self.app, "settings", None)
        name = settings.get("name", "Kömür") if settings is not None else "Kömür"
        self.name_var.set(f"🐾 {name or 'Kömür'}")

        brain = getattr(self.app, "brain", None)
        mood = getattr(brain, "mood", "Keyifli") if brain is not None else "Keyifli"
        self.mood_var.set(str(mood))

        affection = getattr(self.app, "affection", None)
        if affection is not None:
            level = int(getattr(affection, "level", 1))
            xp = int(getattr(affection, "xp", 0))
        elif settings is not None:
            xp = int(settings.get("affection_xp", 0) or 0)
            level = int(settings.get("affection_level", 1 + xp // XP_PER_LEVEL) or 1)
        else:
            level, xp = 1, 0

        progress = max(0, min(XP_PER_LEVEL, xp % XP_PER_LEVEL))
        self.affection_label_var.set(f"♥ Dostluk Sv.{level}")
        self.affection_xp_var.set(f"{progress} / {XP_PER_LEVEL} XP")
        fill_w = round(self._xp_bar_width * (progress / XP_PER_LEVEL))
        self.xp_canvas.coords(self._xp_fill_item, 0, 0, fill_w, 7)

        laser_on = bool(getattr(getattr(self.app, "physics", None), "chasing_laser", False))
        if "laser" in self.action_buttons:
            self.action_buttons["laser"].configure(
                text="🔴 Lazer Kapat" if laser_on else "🔴 Lazer Aç"
            )

    def _on_focus_out(self, event):
        if event.widget is not self.window or not self._visible:
            return
        self._cancel_focus_check()
        try:
            self._focus_check_id = self.window.after(60, self._check_focus_lost)
        except tk.TclError:
            pass

    def _check_focus_lost(self):
        self._focus_check_id = None
        if not self._visible or self._destroyed:
            return
        try:
            if self.window.focus_get() is None:
                self.hide()
        except tk.TclError:
            self.hide()

    def _cancel_focus_check(self):
        if self._focus_check_id is not None:
            try:
                self.window.after_cancel(self._focus_check_id)
            except tk.TclError:
                pass
            self._focus_check_id = None

    # -- action dispatch ----------------------------------------------------
    def _run_and_hide(self, fn):
        self.hide()
        fn()

    def _say(self, text: str, seconds: float = 4.0):
        say_fn = getattr(self.app, "say", None)
        if callable(say_fn) and text:
            say_fn(text, seconds)

    def _run_command(self, name: str):
        cmd_fn = getattr(self.app, "command", None)
        if callable(cmd_fn):
            cmd_fn(name)

    def _action_fish(self):
        pond = getattr(self.app, "fish_pond", None)
        if pond is None:
            self._say("Balık havuzu şu an hazır değil.", 3)
            return
        tasks = pond.list_tasks()
        if tasks:
            brain = getattr(self.app, "brain", None)
            cx = getattr(brain, "x", 0.0)
            cy = getattr(brain, "y", 0.0)
            result = pond.complete_task(tasks[0]["id"], cat_x=cx, cat_y=cy)
            if result.get("ok"):
                self._run_command("play")
                self._say(result["message"], 6)
                return
        pond.add_task("Odak Görevi")
        self._say("🐟 Yeni görev balığı havuza bırakıldı! Yakalamak için tekrar tıkla.", 5)

    def _action_box(self):
        for attr in ("spawn_box", "toggle_box_prop"):
            fn = getattr(self.app, attr, None)
            if callable(fn):
                fn()
                return

    def _action_laser(self):
        fn = getattr(self.app, "toggle_laser", None)
        if callable(fn):
            fn()

    def _action_perch(self):
        fn = getattr(self.app, "perch_active_window", None)
        if callable(fn):
            fn()
            return
        self._run_command("perch")

    def _action_accessory(self):
        settings = getattr(self.app, "settings", None)
        current = settings.get("accessory", None) if settings is not None else None
        idx = ACCESSORY_ORDER.index(current) if current in ACCESSORY_ORDER else 0
        nxt = ACCESSORY_ORDER[(idx + 1) % len(ACCESSORY_ORDER)]
        if settings is not None and callable(getattr(settings, "set", None)):
            settings.set("accessory", nxt)
        renderer = getattr(self.app, "renderer", None)
        if renderer is not None:
            renderer.accessory = nxt
        label = ACCESSORY_LABELS.get(nxt, str(nxt))
        self._say(f"Kostüm: {label}", 3)

    def _action_lofi_focus(self):
        lofi_fn = getattr(self.app, "toggle_lofi", None)
        if callable(lofi_fn):
            lofi_fn()
            return
        ambience_fn = getattr(self.app, "toggle_lofi_ambience", None)
        if callable(ambience_fn):
            ambience_fn()
        focus_fn = getattr(self.app, "toggle_focus", None)
        if callable(focus_fn):
            focus_fn()

    def _action_rubber_duck(self):
        fn = getattr(self.app, "toggle_rubber_duck", None)
        if callable(fn):
            fn()

    def _action_panel(self):
        fn = getattr(self.app, "show_panel", None)
        if callable(fn):
            fn()

    def _action_hide(self):
        fn = getattr(self.app, "toggle_boss_key", None)
        if callable(fn):
            fn()
            return
        root = getattr(self.app, "root", None)
        if root is not None:
            try:
                root.withdraw()
            except tk.TclError:
                pass

    def _action_close(self):
        self.hide()
        fn = getattr(self.app, "close", None)
        if callable(fn):
            fn()
