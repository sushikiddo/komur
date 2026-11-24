"""Kontrol paneli — Dark Glassmorphism 4 sekmeli kontrol merkezi ve ayar işleyicileri.

Düz fonksiyonlar ve hafif özel widget'lar; ``app`` DesktopCat örneğidir. Panel penceresi
``app.panel``'de, Tk değişkenleri (name_var, skin_var, ...) DesktopCat'te kalır.
``cat.py`` içe aktarılmaz.
"""
from __future__ import annotations

import os
import types
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import autostart
import skins
import sound
from renderer import CatRenderer
from settings import SIZE_LABELS, SIZE_SCALES
from window_utils import Button

TITLE = "Kömür — Kontrol paneli"

# Dark Glassmorphism renk paleti
BG_DARK = "#0d1117"
CARD_BG = "#161b22"
CARD_BORDER = "#30363d"
ACCENT = "#58a6ff"
ACCENT_HOVER = "#79c0ff"
SUCCESS = "#2ea043"
SURFACE_ALT = "#21262d"
TEXT_MAIN = "#f0f6fc"
TEXT_MUTED = "#8b949e"
DANGER = "#da3633"

COSTUME_LABELS = {
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

PERSONA_LABELS = {
    "asil_tembel": "Asil / Tembel (INTJ)",
    "hiperaktif_yavru": "Hiperaktif Yavru (ENFP)",
}

_PERSONA_FALLBACK_DESC = {
    "asil_tembel": "Ağırbaşlı, biraz üstten bakan ama içten seven asil smokin kedi.",
    "hiperaktif_yavru": "Çok enerjik, her şeye şaşıran, meraklı ve bol oyun isteyen neşeli kedi.",
}


def _draw_rounded_pill(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
                       r: float, fill: str, outline: str = "", width: float = 1.0,
                       tag: str = "shape") -> None:
    """Draw a pixel-clean rounded rectangle / capsule on a Tk Canvas."""
    r = max(1.0, min(r, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    d = r * 2.0
    if outline:
        canvas.create_oval(x1, y1, x1 + d, y1 + d, fill=fill, outline=outline, width=width, tags=tag)
        canvas.create_oval(x2 - d, y1, x2, y1 + d, fill=fill, outline=outline, width=width, tags=tag)
        canvas.create_oval(x1, y2 - d, x1 + d, y2, fill=fill, outline=outline, width=width, tags=tag)
        canvas.create_oval(x2 - d, y2 - d, x2, y2, fill=fill, outline=outline, width=width, tags=tag)
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="", tags=tag)
        canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="", tags=tag)
        canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=tag)
        canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=tag)
        canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=tag)
        canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=tag)
    else:
        canvas.create_oval(x1, y1, x1 + d, y1 + d, fill=fill, outline="", tags=tag)
        canvas.create_oval(x2 - d, y1, x2, y1 + d, fill=fill, outline="", tags=tag)
        canvas.create_oval(x1, y2 - d, x1 + d, y2, fill=fill, outline="", tags=tag)
        canvas.create_oval(x2 - d, y2 - d, x2, y2, fill=fill, outline="", tags=tag)
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="", tags=tag)
        canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="", tags=tag)


class ModernToggle(tk.Canvas):
    """iOS / Windows 11 tarzı yuvarlak kapsül (44x22 px) aç/kapa anahtarı."""

    WIDTH = 44
    HEIGHT = 22

    def __init__(self, parent, variable: tk.BooleanVar | None = None, command=None,
                 on_color: str = SUCCESS, off_color: str = CARD_BORDER,
                 knob_color: str = "#ffffff", bg: str = CARD_BG, disabled: bool = False):
        super().__init__(
            parent,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="arrow" if disabled else "hand2",
        )
        self.variable = variable if variable is not None else tk.BooleanVar(value=False)
        self.command = command
        self.on_color = on_color
        self.off_color = off_color
        self.knob_color = knob_color
        self.disabled = bool(disabled)
        self._anim_job = None
        self._knob_pos = 1.0 if bool(self.variable.get()) else 0.0
        self._trace_id = self.variable.trace_add("write", self._on_var_changed)

        self.bind("<Button-1>", self._on_click)
        self.bind("<Destroy>", self._on_destroy)
        self._draw()

    def set_disabled(self, disabled: bool) -> None:
        self.disabled = bool(disabled)
        self.configure(cursor="arrow" if self.disabled else "hand2")
        self._draw()

    def _on_destroy(self, _event=None) -> None:
        if self._anim_job is not None:
            try:
                self.after_cancel(self._anim_job)
            except tk.TclError:
                pass
            self._anim_job = None
        if self._trace_id is not None:
            try:
                self.variable.trace_remove("write", self._trace_id)
            except tk.TclError:
                pass
            self._trace_id = None

    def _on_var_changed(self, *_args) -> None:
        target = 1.0 if bool(self.variable.get()) else 0.0
        self._animate_to(target)

    def _on_click(self, _event=None) -> None:
        if self.disabled:
            return
        new_val = not bool(self.variable.get())
        self.variable.set(new_val)
        if callable(self.command):
            self.command()

    def _animate_to(self, target: float) -> None:
        if self._anim_job is not None:
            try:
                self.after_cancel(self._anim_job)
            except tk.TclError:
                pass
            self._anim_job = None
        diff = target - self._knob_pos
        if abs(diff) <= 0.25:
            self._knob_pos = target
            self._draw()
            return
        self._knob_pos += diff * 0.45
        self._draw()
        try:
            if self.winfo_exists():
                self._anim_job = self.after(14, lambda: self._animate_to(target))
        except tk.TclError:
            pass

    def _draw(self) -> None:
        if not self.winfo_exists():
            return
        self.delete("toggle")
        is_on = bool(self.variable.get())
        if self.disabled:
            track_color = SURFACE_ALT
            knob_fill = TEXT_MUTED
        else:
            track_color = self.on_color if is_on else self.off_color
            knob_fill = self.knob_color

        _draw_rounded_pill(self, 1, 1, self.WIDTH - 1, self.HEIGHT - 1,
                           r=10, fill=track_color, tag="toggle")
        kx = 3.0 + self._knob_pos * (self.WIDTH - 22.0)
        self.create_oval(kx, 3, kx + 16, 19, fill=knob_fill, outline="", tags="toggle")


class AffectionProgressBar(tk.Canvas):
    """Header üzerinde Canvas tabanlı yuvarlatılmış Dostluk Seviyesi & XP Çubuğu."""

    def __init__(self, parent, width: int = 230, height: int = 28, bg: str = CARD_BG):
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, bd=0)
        self._bar_w = width
        self._bar_h = height
        self._level = 1
        self._xp_mod = 0
        self.update_progress(1, 0)

    def update_progress(self, level: int, total_xp: int) -> None:
        self._level = max(1, int(level or 1))
        self._xp_mod = max(0, int(total_xp or 0)) % 100
        self._draw()

    def _draw(self) -> None:
        if not self.winfo_exists():
            return
        self.delete("xpbar")
        w, h = self._bar_w, self._bar_h
        _draw_rounded_pill(self, 1, 1, w - 1, h - 1, r=12, fill=BG_DARK,
                           outline=CARD_BORDER, width=1.0, tag="xpbar")
        ratio = max(0.0, min(1.0, self._xp_mod / 100.0))
        fill_w = (w - 6) * ratio
        if fill_w >= 8:
            fill_color = SUCCESS if ratio >= 0.8 else ACCENT
            _draw_rounded_pill(self, 3, 3, 3 + fill_w, h - 3, r=10,
                               fill=fill_color, tag="xpbar")
        label = f"♥ Dostluk  Sv.{self._level} • {self._xp_mod} / 100"
        self.create_text(w / 2, h / 2, text=label, fill=TEXT_MAIN,
                         font=("Segoe UI", 9, "bold"), tags="xpbar")


class LivePreviewCanvas(tk.Frame):
    """Görünüm & Kostümler sekmesi sağında 150x165 canlı mini kedi önizlemesi."""

    PREVIEW_W = 150
    PREVIEW_H = 165

    def __init__(self, parent, app):
        super().__init__(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                         highlightthickness=1, padx=10, pady=10)
        self.app = app
        self._t = 0.0
        self._anim_job = None

        tk.Label(self, text="CANLI ÖNİZLEME", bg=CARD_BG, fg=TEXT_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 6))

        self.canvas = tk.Canvas(
            self,
            width=self.PREVIEW_W,
            height=self.PREVIEW_H,
            bg=BG_DARK,
            highlightthickness=1,
            highlightbackground=CARD_BORDER,
        )
        self.canvas.pack()

        self.caption_var = tk.StringVar()
        tk.Label(self, textvariable=self.caption_var, bg=CARD_BG, fg=TEXT_MUTED,
                 font=("Segoe UI", 8), wraplength=150, justify="center").pack(pady=(6, 0))

        self.renderer = CatRenderer(self.canvas, self.PREVIEW_W, self.PREVIEW_H)
        self.brain = types.SimpleNamespace(
            state="sit",
            facing=1,
            elapsed=0.0,
            age_days=7.0,
            paused=False,
            pointer_xy=None,
            pupil_dilation=None,
            low_light=False,
            vx=0.0,
            vy=0.0,
            startled=False,
            use_procedural_springs=False,
            activity_reaction="none",
            emote=None,
            retro_mode=False,
        )
        self.bind("<Destroy>", self._on_destroy)
        self.refresh()
        self._schedule_tick()

    def _draw_backdrop(self) -> None:
        self.canvas.delete("preview_bg")
        self.canvas.create_oval(
            18, 125, self.PREVIEW_W - 18, 155,
            fill="#131922", outline="#1f2937", width=1, tags="preview_bg",
        )

    def refresh(self) -> None:
        if not self.winfo_exists():
            return
        skin = self.app.settings.get("skin", "komur")
        acc = self.app.settings.get("accessory", None)
        retro = bool(self.app.settings.get("retro_mode", False))
        age_days = float(self.app.settings.get("age_days", 7.0) or 7.0)

        self._draw_backdrop()
        skins.apply_skin(self.renderer, skin)
        self.renderer.accessory = acc
        self.renderer.set_retro_mode(retro)
        self.brain.age_days = age_days
        self.brain.retro_mode = retro
        self.renderer.draw(self.brain, self._t)

        skin_lbl = skins.label(skin).split(" (")[0]
        acc_lbl = COSTUME_LABELS.get(acc, str(acc))
        retro_tag = " • Retro" if retro else ""
        self.caption_var.set(f"{skin_lbl} • {acc_lbl}{retro_tag}")

    def _schedule_tick(self) -> None:
        if self._anim_job is not None:
            try:
                self.after_cancel(self._anim_job)
            except tk.TclError:
                pass
            self._anim_job = None
        try:
            if self.winfo_exists():
                self._anim_job = self.after(140, self._tick)
        except tk.TclError:
            pass

    def _tick(self) -> None:
        self._anim_job = None
        if not self.winfo_exists():
            return
        panel = getattr(self.app, "panel", None)
        try:
            if panel is not None and panel.winfo_exists() and panel.state() == "normal":
                self._t += 0.14
                self.refresh()
        except tk.TclError:
            return
        self._schedule_tick()

    def _on_destroy(self, _event=None) -> None:
        if self._anim_job is not None:
            try:
                self.after_cancel(self._anim_job)
            except tk.TclError:
                pass
            self._anim_job = None


# -- Stil ve düzen yardımcıları ---------------------------------------------
def _apply_dark_styles(panel_win: tk.Toplevel) -> None:
    style = ttk.Style(panel_win)
    try:
        if style.theme_use() in ("vista", "xpnative", "winnative", "aqua"):
            style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("Komur.TNotebook", background=BG_DARK, borderwidth=0, tabmargins=(0, 0, 0, 4))
    style.configure(
        "Komur.TNotebook.Tab",
        background=CARD_BG,
        foreground=TEXT_MUTED,
        padding=(12, 7),
        borderwidth=1,
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Komur.TNotebook.Tab",
        background=[("selected", SURFACE_ALT), ("active", "#1c2128")],
        foreground=[("selected", ACCENT), ("active", TEXT_MAIN)],
        bordercolor=[("selected", ACCENT)],
    )
    style.configure("Komur.TFrame", background=BG_DARK)
    style.configure(
        "Komur.TCombobox",
        fieldbackground=BG_DARK,
        background=SURFACE_ALT,
        foreground=TEXT_MAIN,
        arrowcolor=TEXT_MAIN,
        bordercolor=CARD_BORDER,
        lightcolor=CARD_BORDER,
        darkcolor=CARD_BORDER,
        selectbackground=ACCENT,
        selectforeground=BG_DARK,
    )
    style.map(
        "Komur.TCombobox",
        fieldbackground=[("readonly", BG_DARK)],
        foreground=[("readonly", TEXT_MAIN)],
        selectbackground=[("readonly", BG_DARK)],
        selectforeground=[("readonly", TEXT_MAIN)],
    )
    style.configure(
        "Komur.TEntry",
        fieldbackground=BG_DARK,
        foreground=TEXT_MAIN,
        insertcolor=TEXT_MAIN,
        bordercolor=CARD_BORDER,
    )
    style.configure(
        "Komur.TSpinbox",
        fieldbackground=BG_DARK,
        background=SURFACE_ALT,
        foreground=TEXT_MAIN,
        arrowcolor=TEXT_MAIN,
        bordercolor=CARD_BORDER,
    )
    style.configure(
        "Komur.Horizontal.TScale",
        background=CARD_BG,
        troughcolor=BG_DARK,
        bordercolor=CARD_BORDER,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
    )
    panel_win.option_add("*TCombobox*Listbox.background", CARD_BG)
    panel_win.option_add("*TCombobox*Listbox.foreground", TEXT_MAIN)
    panel_win.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    panel_win.option_add("*TCombobox*Listbox.selectForeground", BG_DARK)


def _make_card(parent, title: str | None = None, pady=(0, 10)) -> tk.Frame:
    card = tk.Frame(
        parent,
        bg=CARD_BG,
        highlightbackground=CARD_BORDER,
        highlightthickness=1,
        padx=12,
        pady=10,
    )
    card.pack(fill="x", pady=pady)
    if title:
        tk.Label(card, text=title, bg=CARD_BG, fg=TEXT_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 8))
    return card


def _make_button(parent, text: str, command, accent: bool = False,
                 danger: bool = False, width: int | None = None) -> tk.Widget:
    base_bg = ACCENT if accent else (DANGER if danger else SURFACE_ALT)
    base_fg = BG_DARK if accent else TEXT_MAIN
    hover_bg = ACCENT_HOVER if accent else ("#f85149" if danger else "#30363d")

    btn = Button(
        parent,
        text=text,
        command=command,
        bg=base_bg,
        fg=base_fg,
        activebackground=hover_bg,
        activeforeground=base_fg,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=ACCENT if accent else CARD_BORDER,
        font=("Segoe UI", 9, "bold" if accent else "normal"),
        padx=10,
        pady=6,
        cursor="hand2",
    )
    if width is not None:
        btn.configure(width=width)
    btn.bind("<Enter>", lambda _e: btn.configure(bg=hover_bg))
    btn.bind("<Leave>", lambda _e: btn.configure(bg=base_bg))
    return btn


def _make_toggle_row(parent, title: str, variable: tk.BooleanVar, command,
                     subtitle: str | None = None, on_color: str = SUCCESS,
                     disabled: bool = False) -> ModernToggle:
    row = tk.Frame(parent, bg=CARD_BG)
    row.pack(fill="x", pady=4)
    text_col = tk.Frame(row, bg=CARD_BG)
    text_col.pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Label(text_col, text=title, bg=CARD_BG, fg=TEXT_MAIN,
             font=("Segoe UI", 9, "bold"), anchor="w").pack(anchor="w")
    if subtitle:
        tk.Label(text_col, text=subtitle, bg=CARD_BG, fg=TEXT_MUTED,
                 font=("Segoe UI", 8), anchor="w").pack(anchor="w")
    toggle = ModernToggle(row, variable=variable, command=command,
                          on_color=on_color, bg=CARD_BG, disabled=disabled)
    toggle.pack(side="right", anchor="center")
    return toggle


def _ensure_var(app, attr: str, factory):
    var = getattr(app, attr, None)
    if var is None:
        var = factory()
        setattr(app, attr, var)
    return var


def _get_affection_stats(app) -> tuple[int, int]:
    aff = getattr(app, "affection", None)
    if aff is not None:
        return int(getattr(aff, "level", 1)), int(getattr(aff, "xp", 0))
    return (
        int(app.settings.get("affection_level", 1) or 1),
        int(app.settings.get("affection_xp", 0) or 0),
    )


def _refresh_xp_bar(app) -> None:
    bar = getattr(app, "_panel_xp_bar", None)
    if bar is None:
        return
    try:
        if bar.winfo_exists():
            lvl, xp = _get_affection_stats(app)
            bar.update_progress(lvl, xp)
    except tk.TclError:
        pass


def _refresh_preview(app) -> None:
    preview = getattr(app, "_panel_preview", None)
    if preview is not None:
        try:
            preview.refresh()
        except tk.TclError:
            pass


def _persona_description(persona_id: str) -> str:
    try:
        from persona_dreams import PERSONA_TEMPLATES
        entry = PERSONA_TEMPLATES.get(persona_id)
        if entry and entry.get("description"):
            return str(entry["description"])
    except Exception:
        pass
    return _PERSONA_FALLBACK_DESC.get(persona_id, "")


def _latest_dream_text(app) -> str:
    de = getattr(app, "dream_engine", None)
    if de is not None:
        try:
            latest = de.memory_store.latest_dream()
            if latest and latest.get("dream_text"):
                return f"💭 {latest['dream_text']}"
        except Exception:
            pass
    mem = getattr(getattr(app, "assistant", None), "memory", None)
    if mem is not None and callable(getattr(mem, "latest_dream", None)):
        try:
            latest = mem.latest_dream()
            if latest and latest.get("dream_text"):
                return f"💭 {latest['dream_text']}"
        except Exception:
            pass
    return "Henüz kaydedilmiş bir gece rüyası yok. Uykuya geçtiğinde rüya görecek."


# -- Panel açılışı ve Header -------------------------------------------------
def show_panel(app):
    """Dark Glassmorphism kontrol panelini oluşturur veya öne getirir."""
    if app.panel is not None and app.panel.winfo_exists():
        app.panel.deiconify()
        app.panel.lift()
        app.panel.focus_force()
        _refresh_xp_bar(app)
        _refresh_preview(app)
        refresh_dreams = getattr(app, "_panel_refresh_dream", None)
        if callable(refresh_dreams):
            refresh_dreams()
        refresh_fish = getattr(app, "_panel_refresh_fish", None)
        if callable(refresh_fish):
            refresh_fish()
        app._refresh_status()
        return

    app.panel = tk.Toplevel(app.root)
    app.panel.title(TITLE)
    app.panel.configure(bg=BG_DARK)
    app.panel.resizable(False, False)
    app.panel.attributes("-topmost", True)
    _apply_dark_styles(app.panel)

    _build_header(app, app.panel)

    nb = ttk.Notebook(app.panel, style="Komur.TNotebook")
    nb.pack(fill="both", expand=True, padx=14, pady=(0, 12))

    build_look_tab(app, nb)
    build_persona_tab(app, nb)
    build_audio_tab(app, nb)
    build_productivity_tab(app, nb)

    app.panel.protocol("WM_DELETE_WINDOW", app.panel.withdraw)
    app._refresh_status()
    _refresh_xp_bar(app)


def _build_header(app, parent) -> None:
    header = tk.Frame(
        parent,
        bg=CARD_BG,
        highlightbackground=CARD_BORDER,
        highlightthickness=1,
        padx=14,
        pady=10,
    )
    header.pack(fill="x", padx=14, pady=(12, 10))

    top_row = tk.Frame(header, bg=CARD_BG)
    top_row.pack(fill="x")

    title_col = tk.Frame(top_row, bg=CARD_BG)
    title_col.pack(side="left", fill="x", expand=True)

    name_row = tk.Frame(title_col, bg=CARD_BG)
    name_row.pack(anchor="w")
    tk.Label(name_row, text="🐾", bg=CARD_BG, fg=ACCENT,
             font=("Segoe UI", 14)).pack(side="left", padx=(0, 6))
    tk.Label(name_row, textvariable=app.name_var, bg=CARD_BG, fg=TEXT_MAIN,
             font=("Segoe UI", 15, "bold")).pack(side="left")
    tk.Label(name_row, text="• Kontrol Merkezi", bg=CARD_BG, fg=TEXT_MUTED,
             font=("Segoe UI", 9)).pack(side="left", padx=(8, 0), pady=(3, 0))

    tk.Label(title_col, textvariable=app.status_var, bg=CARD_BG, fg=ACCENT,
             font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

    xp_bar = AffectionProgressBar(top_row, width=225, height=28, bg=CARD_BG)
    xp_bar.pack(side="right", anchor="center", padx=(12, 0))
    app._panel_xp_bar = xp_bar

    aff_var = _ensure_var(app, "affection_var", lambda: tk.StringVar(
        value=f"Sv.{app.settings.get('affection_level', 1)} ({app.settings.get('affection_xp', 0)} XP)"
    ))
    trace_id = aff_var.trace_add("write", lambda *_a: _refresh_xp_bar(app))

    def _cleanup_trace(_e=None):
        try:
            aff_var.trace_remove("write", trace_id)
        except tk.TclError:
            pass
        app._panel_xp_bar = None

    xp_bar.bind("<Destroy>", _cleanup_trace)
    _refresh_xp_bar(app)


# -- Sekme 1: Görünüm & Kostümler -------------------------------------------
def build_look_tab(app, nb: ttk.Notebook):
    tab = ttk.Frame(nb, style="Komur.TFrame", padding=12)
    nb.add(tab, text="🎨 Görünüm & Kostümler")

    columns = tk.Frame(tab, bg=BG_DARK)
    columns.pack(fill="both", expand=True)

    left = tk.Frame(columns, bg=BG_DARK)
    left.pack(side="left", fill="both", expand=True, padx=(0, 12))

    right = tk.Frame(columns, bg=BG_DARK)
    right.pack(side="right", fill="y", anchor="n")

    card_basic = _make_card(left, "KİMLİK & GÖRÜNÜM")
    grid = tk.Frame(card_basic, bg=CARD_BG)
    grid.pack(fill="x")
    grid.columnconfigure(1, weight=1)

    def _lbl(row_idx: int, text: str):
        tk.Label(grid, text=text, bg=CARD_BG, fg=TEXT_MAIN,
                 font=("Segoe UI", 9)).grid(row=row_idx, column=0, sticky="w", pady=5, padx=(0, 10))

    _lbl(0, "İsim")
    name_entry = ttk.Entry(grid, textvariable=app.name_var, width=22, style="Komur.TEntry")
    name_entry.grid(row=0, column=1, sticky="ew", pady=5)
    name_entry.bind("<Return>", lambda _e: on_name_change(app))
    name_entry.bind("<FocusOut>", lambda _e: on_name_change(app))

    _lbl(1, "Tüy Rengi")
    order = skins.skin_order()
    skin_box = ttk.Combobox(grid, state="readonly", width=20, style="Komur.TCombobox",
                            values=[skins.label(k) for k in order])
    cur_skin = app.settings.get("skin")
    skin_box.current(order.index(cur_skin) if cur_skin in order else 0)
    skin_box.grid(row=1, column=1, sticky="ew", pady=5)
    skin_box.bind("<<ComboboxSelected>>",
                  lambda _e: on_skin_change(app, order[skin_box.current()]))

    _lbl(2, "Boyut")
    size_keys = list(SIZE_SCALES.keys())
    size_box = ttk.Combobox(grid, state="readonly", width=20, style="Komur.TCombobox",
                            values=[SIZE_LABELS[k] for k in size_keys])
    cur_size = app.settings.get("size")
    size_box.current(size_keys.index(cur_size) if cur_size in size_keys else 1)
    size_box.grid(row=2, column=1, sticky="ew", pady=5)
    size_box.bind("<<ComboboxSelected>>",
                  lambda _e: on_size_change(app, size_keys[size_box.current()]))

    _lbl(3, "Saydamlık")
    opacity_row = tk.Frame(grid, bg=CARD_BG)
    opacity_row.grid(row=3, column=1, sticky="ew", pady=5)
    opacity_pct = tk.Label(opacity_row, text=f"%{int(app.opacity_var.get())}",
                           bg=CARD_BG, fg=ACCENT, font=("Segoe UI", 9, "bold"), width=5)
    opacity_pct.pack(side="right")

    def _on_opacity(_val):
        opacity_pct.configure(text=f"%{int(app.opacity_var.get())}")
        on_opacity_change(app)

    ttk.Scale(opacity_row, from_=20, to=100, variable=app.opacity_var,
              style="Komur.Horizontal.TScale", command=_on_opacity).pack(side="left", fill="x", expand=True)

    _lbl(4, "Arkadaş Sayısı")
    friends_spin = ttk.Spinbox(grid, from_=0, to=3, width=6, textvariable=app.friends_var,
                               style="Komur.TSpinbox",
                               command=lambda: on_friends_change(app))
    friends_spin.grid(row=4, column=1, sticky="w", pady=5)
    friends_spin.bind("<Return>", lambda _e: on_friends_change(app))
    friends_spin.bind("<FocusOut>", lambda _e: on_friends_change(app))

    card_costume = _make_card(left, "KOSTÜM & RETRO FİLTRE", pady=(0, 0))
    c_grid = tk.Frame(card_costume, bg=CARD_BG)
    c_grid.pack(fill="x", pady=(0, 6))
    c_grid.columnconfigure(1, weight=1)
    tk.Label(c_grid, text="Kostüm / Aksesuar", bg=CARD_BG, fg=TEXT_MAIN,
             font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
    costume_keys = list(COSTUME_LABELS.keys())
    costume_box = ttk.Combobox(c_grid, state="readonly", width=20, style="Komur.TCombobox",
                               values=[COSTUME_LABELS[k] for k in costume_keys])
    cur_acc = app.settings.get("accessory")
    costume_box.current(costume_keys.index(cur_acc) if cur_acc in costume_keys else 0)
    costume_box.grid(row=0, column=1, sticky="ew", pady=4)
    costume_box.bind("<<ComboboxSelected>>",
                     lambda _e: on_accessory_change(app, costume_keys[costume_box.current()]))

    retro_var = _ensure_var(
        app, "retro_var", lambda: tk.BooleanVar(value=bool(app.settings.get("retro_mode", False)))
    )
    _make_toggle_row(
        card_costume,
        "Retro Pixel Modu (90'lar)",
        retro_var,
        lambda: on_retro_change(app),
        subtitle="4px piksel ızgarası & RGB565 tarama çizgileri",
        on_color=ACCENT,
    )

    preview = LivePreviewCanvas(right, app)
    preview.pack(anchor="n")
    app._panel_preview = preview
    preview.bind("<Destroy>", lambda _e: setattr(app, "_panel_preview", None))


# -- Sekme 2: Kişilik & Zeka ------------------------------------------------
def build_persona_tab(app, nb: ttk.Notebook):
    tab = ttk.Frame(nb, style="Komur.TFrame", padding=12)
    nb.add(tab, text="🧠 Kişilik & Zeka")

    card_persona = _make_card(tab, "KİŞİLİK ŞABLONU")
    p_row = tk.Frame(card_persona, bg=CARD_BG)
    p_row.pack(fill="x")
    tk.Label(p_row, text="Karakter", bg=CARD_BG, fg=TEXT_MAIN,
             font=("Segoe UI", 9)).pack(side="left", padx=(0, 12))

    persona_keys = list(PERSONA_LABELS.keys())
    cur_persona = app.settings.get("persona", "asil_tembel")
    if cur_persona not in persona_keys:
        cur_persona = "asil_tembel"
    persona_box = ttk.Combobox(p_row, state="readonly", width=28, style="Komur.TCombobox",
                               values=[PERSONA_LABELS[k] for k in persona_keys])
    persona_box.current(persona_keys.index(cur_persona))
    persona_box.pack(side="left", fill="x", expand=True)

    persona_desc_var = tk.StringVar(value=_persona_description(cur_persona))
    tk.Label(card_persona, textvariable=persona_desc_var, bg=CARD_BG, fg=TEXT_MUTED,
             font=("Segoe UI", 8), wraplength=440, justify="left").pack(anchor="w", pady=(8, 0))

    def _on_select_persona(_e=None):
        pid = persona_keys[persona_box.current()]
        persona_desc_var.set(_persona_description(pid))
        on_persona_change(app, pid)

    persona_box.bind("<<ComboboxSelected>>", _on_select_persona)

    card_modes = _make_card(tab, "ZEKA MODLARI")
    _make_toggle_row(
        card_modes,
        "İhtiyaç & Ruh Hali Sistemi",
        app.needs_var,
        lambda: on_needs_change(app),
        subtitle="Açlık, enerji ve keyif döngüsü kedinin davranışını yönlendirir",
    )

    card_dream = _make_card(tab, "SON GECE RÜYASI & SOHBET", pady=(0, 0))
    dream_var = tk.StringVar(value=_latest_dream_text(app))
    app._panel_refresh_dream = lambda: dream_var.set(_latest_dream_text(app))

    dream_box = tk.Frame(card_dream, bg=BG_DARK, highlightbackground=CARD_BORDER,
                         highlightthickness=1, padx=10, pady=8)
    dream_box.pack(fill="x", pady=(0, 8))
    tk.Label(dream_box, textvariable=dream_var, bg=BG_DARK, fg=TEXT_MAIN,
             font=("Segoe UI", 9, "italic"), wraplength=430, justify="left").pack(anchor="w")

    btn_row = tk.Frame(card_dream, bg=CARD_BG)
    btn_row.pack(fill="x")

    def _dream_now():
        de = getattr(app, "dream_engine", None)
        if de is not None:
            dream = de.generate_dream(is_sleeping=True, force=True)
            if dream and dream.get("dream_text"):
                dream_var.set(f"💭 {dream['dream_text']}")
                app.say(dream["bubble"], 7)
                return
        app.say("💭 Mırıl mırıl... altın balıklar düşledim.", 5)

    _make_button(btn_row, "💭 Şimdi Rüya Gör", _dream_now).pack(side="left", padx=(0, 8))
    _make_button(btn_row, "💬 Kömür ile Konuş", app._on_speak_click, accent=True).pack(side="left")


# -- Sekme 3: Ses & Ambiyans ------------------------------------------------
def build_audio_tab(app, nb: ttk.Notebook):
    tab = ttk.Frame(nb, style="Komur.TFrame", padding=12)
    nb.add(tab, text="🔊 Ses & Ambiyans")

    card_sound = _make_card(tab, "SES & ODAK AMBİYANSI")
    _make_toggle_row(
        card_sound,
        "Sesler (2D Konumsal Stereo)",
        app.sound_var,
        lambda: on_sound_change(app),
        subtitle="Yalnız sevme, esneme ve uyanma anlarında gerçek kedi sesi",
    )

    lofi_var = _ensure_var(
        app, "lofi_var",
        lambda: tk.BooleanVar(value=bool(app.settings.get("lofi_ambience", False))),
    )

    def _on_lofi_toggle():
        if callable(getattr(app, "toggle_lofi_ambience", None)):
            playing = bool(app.toggle_lofi_ambience())
            lofi_var.set(playing)
        else:
            app.settings.set("lofi_ambience", bool(lofi_var.get()))

    _make_toggle_row(
        card_sound,
        "Odak Lofi Ambiyansı (Yağmur + Şömine + Mırıldanma)",
        lofi_var,
        _on_lofi_toggle,
        subtitle="Çalışma sırasında yumuşak sentezlenmiş arka plan ambiyansı",
        on_color=ACCENT,
    )

    card_quality = _make_card(tab, "KALİTE & EFEKT AYARLARI", pady=(0, 0))
    q_grid = tk.Frame(card_quality, bg=CARD_BG)
    q_grid.pack(fill="x")
    q_grid.columnconfigure(1, weight=1)

    tk.Label(q_grid, text="Ses Kalitesi", bg=CARD_BG, fg=TEXT_MAIN,
             font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
    quality_box = ttk.Combobox(q_grid, state="readonly", width=24, style="Komur.TCombobox",
                               values=["Yüksek (Gerçekçi WAV)", "Normal (Senteli)"])
    quality_box.current(0 if app.settings.get("sound_quality") == "high" else 1)
    quality_box.grid(row=0, column=1, sticky="ew", pady=6)
    quality_box.bind("<<ComboboxSelected>>",
                     lambda _e: on_quality_change(app, ["high", "normal"][quality_box.current()]))

    tk.Label(q_grid, text="Efekt Yoğunluğu", bg=CARD_BG, fg=TEXT_MAIN,
             font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)
    density_box = ttk.Combobox(q_grid, state="readonly", width=24, style="Komur.TCombobox",
                               values=["Düşük", "Normal", "Yüksek"])
    density_idx = max(0, min(2, int(app.settings.get("effects_density", 2) or 2) - 1))
    density_box.current(density_idx)
    density_box.grid(row=1, column=1, sticky="ew", pady=6)
    density_box.bind("<<ComboboxSelected>>",
                     lambda _e: on_density_change(app, density_box.current() + 1))

    if getattr(app, "tray", None) and app.tray.available:
        tk.Label(card_quality, text="Sistem tepsisi: etkin (sağ tık: menü)",
                 bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))


# -- Sekme 4: Üretkenlik & Hareketler ---------------------------------------
def _perch_on_active_window(app) -> None:
    fn = getattr(app, "perch_active_window", None)
    if callable(fn):
        fn()
        return
    app.say("Fizik motoru hazır değil.", 3)


def build_productivity_tab(app, nb: ttk.Notebook):
    tab = ttk.Frame(nb, style="Komur.TFrame", padding=12)
    nb.add(tab, text="🎣 Üretkenlik & Hareketler")

    card_actions = _make_card(tab, "HIZLI DAVRANIŞ & FİZİK BUTONLARI")
    grid = tk.Frame(card_actions, bg=CARD_BG)
    grid.pack(fill="x")
    for col in range(3):
        grid.columnconfigure(col, weight=1)

    actions = [
        ("♥ Sev", lambda: app.command("pet"), True),
        ("🍖 Mama Ver", lambda: app.command("feed"), False),
        ("🎾 Topla Oyna", lambda: app.command("play"), False),
        ("🪟 Pencereye Tüne", lambda: _perch_on_active_window(app), False),
        ("📦 Kutu Bırak", lambda: getattr(app, "toggle_box_prop", lambda: None)(), False),
        ("🧶 İplik Yumağı", lambda: getattr(app, "toggle_toy", lambda _k: None)("yarn"), False),
        ("🕵️ Patron Tuşu Gizle", lambda: getattr(app, "toggle_boss_key", lambda: None)(), False),
        ("😴 Uyu / Uyan", lambda: app.command("wake" if app.brain.state == "sleep" else "sleep"), False),
        ("🐾 Gezin", lambda: app.command("wander"), False),
    ]
    for idx, (label, cmd, is_accent) in enumerate(actions):
        _make_button(grid, label, cmd, accent=is_accent).grid(
            row=idx // 3, column=idx % 3, padx=3, pady=3, sticky="ew"
        )

    sub_row = tk.Frame(card_actions, bg=CARD_BG)
    sub_row.pack(fill="x", pady=(6, 0))
    _make_button(sub_row, "⏯ Duraklat / Devam", app.toggle_pause).pack(side="left", fill="x", expand=True, padx=(0, 4))
    _make_button(sub_row, "🖥️ Diğer Ekrana Geç", app.next_monitor).pack(side="left", fill="x", expand=True, padx=(4, 0))

    card_fish = _make_card(tab, "TO-DO BALIK AVLAMA")
    input_row = tk.Frame(card_fish, bg=CARD_BG)
    input_row.pack(fill="x")
    fish_var = tk.StringVar()
    fish_entry = ttk.Entry(input_row, textvariable=fish_var, style="Komur.TEntry")
    fish_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    fish_list_frame = tk.Frame(card_fish, bg=CARD_BG)
    fish_list_frame.pack(fill="x", pady=(6, 0))

    def _refresh_fish():
        if not fish_list_frame.winfo_exists():
            return
        for child in fish_list_frame.winfo_children():
            child.destroy()
        pond = getattr(app, "fish_pond", None)
        if pond is None:
            return
        tasks = pond.list_tasks(include_caught=False)
        if not tasks:
            tk.Label(fish_list_frame, text="Görev ekle; tamamlayınca Kömür balığı yakalasın (+25 XP).",
                     bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 8)).pack(anchor="w")
            return
        for t in tasks[:3]:
            row = tk.Frame(fish_list_frame, bg=BG_DARK, highlightbackground=CARD_BORDER,
                           highlightthickness=1, padx=8, pady=4)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"🐟 {t['title']}", bg=BG_DARK, fg=TEXT_MAIN,
                     font=("Segoe UI", 8), anchor="w").pack(side="left", fill="x", expand=True)

            def _catch(tid=t["id"]):
                res = pond.complete_task(tid, app.brain.x, app.brain.y)
                if res.get("ok"):
                    app.say(res.get("message", "Balık yakalandı!"), 6)
                app._refresh_status()
                _refresh_xp_bar(app)
                _refresh_fish()

            _make_button(row, "✓ Yakala", _catch).pack(side="right")

    def _add_fish(_e=None):
        title = fish_var.get().strip()
        pond = getattr(app, "fish_pond", None)
        if not title or pond is None:
            return
        pond.add_task(title)
        fish_var.set("")
        app.say(f"🐟 Görev havuza bırakıldı: {title}", 4)
        _refresh_fish()

    fish_entry.bind("<Return>", _add_fish)
    _make_button(input_row, "+ Balık Ekle", _add_fish, accent=True).pack(side="right")
    app._panel_refresh_fish = _refresh_fish
    _refresh_fish()

    card_sys = _make_card(tab, "SİSTEM & PENCERE", pady=(0, 0))
    _make_toggle_row(
        card_sys,
        "Oturum Açılınca Başlat",
        app.autostart_var,
        lambda: on_autostart_change(app),
        disabled=not autostart.available(),
    )
    footer_row = tk.Frame(card_sys, bg=CARD_BG)
    footer_row.pack(fill="x", pady=(6, 0))
    _make_button(footer_row, "Paneli Gizle", app.panel.withdraw).pack(side="left", fill="x", expand=True, padx=(0, 4))
    _make_button(footer_row, "Kömür'ü Kapat", app.close, danger=True).pack(side="left", fill="x", expand=True, padx=(4, 0))
    tk.Label(card_sys, text="Günlük: " + str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Komur" / "komur.log"),
             bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 7)).pack(anchor="w", pady=(6, 0))


# Geriye dönük uyumluluk takma adları
build_actions_tab = build_productivity_tab
build_system_tab = build_audio_tab


# -- Panel geri çağırmaları (callbacks) -------------------------------------
def on_name_change(app):
    name = app.name_var.get().strip() or "Kömür"
    app.name_var.set(name)
    app.settings.set("name", name)
    app.say(f"Artık adım {name}!", 4)


def on_skin_change(app, skin):
    app.settings.set("skin", skin)
    app.skin_var.set(skin)
    app._apply_skin()
    for mate in app.companions:
        skins.apply_skin(mate.renderer, skin)
    _refresh_preview(app)
    app.say("Yeni kürk!", 4)


def on_size_change(app, size):
    app.settings.set("size", size)
    app.size_var.set(size)
    app._apply_size()
    app._rebuild_companions()
    app._apply_opacity()


def on_opacity_change(app):
    value = int(app.opacity_var.get())
    app.settings.set("opacity", value)
    app._apply_opacity()


def on_friends_change(app):
    try:
        count = max(0, min(3, int(app.friends_var.get())))
    except (ValueError, tk.TclError):
        count = max(0, min(3, int(app.settings.get("friends") or 0)))
    app.friends_var.set(count)
    app.settings.set("friends", count)
    app._rebuild_companions()
    app._apply_opacity()


def on_sound_change(app):
    enabled = bool(app.sound_var.get())
    app.settings.set("sound", enabled)
    orchestrator = getattr(app, "effect_orchestrator", None)
    if orchestrator is not None:
        if callable(getattr(orchestrator, "set_sound", None)):
            orchestrator.set_sound(enabled)
        else:
            orchestrator.sound_enabled = enabled
    hud = getattr(app, "context_hud", None)
    if hud is not None and callable(getattr(hud, "refresh", None)):
        try:
            hud.refresh()
        except tk.TclError:
            pass


def on_needs_change(app):
    enabled = bool(app.needs_var.get())
    app.settings.set("needs", enabled)
    app.brain.needs_enabled = enabled
    for mate in app.companions:
        mate.brain.needs_enabled = enabled


def on_autostart_change(app):
    want = bool(app.autostart_var.get())
    result = autostart.set_enabled(want)
    app.autostart_var.set(result)
    app.settings.set("autostart", result)


def on_quality_change(app, quality):
    app.settings.set("sound_quality", quality)
    app.quality_var.set(quality)
    app.effect_orchestrator.set_quality(quality)
    app.say(f"Ses kalitesi: {'Yüksek' if quality == 'high' else 'Normal'}", 3)


def on_density_change(app, density):
    app.settings.set("effects_density", density)
    app.density_var.set(density)
    app.effect_orchestrator.particles.MAX_PARTICLES = {1: 300, 2: 600, 3: 1000}[density]
    app.say(f"Efekt yoğunluğu: {'Düşük' if density == 1 else 'Normal' if density == 2 else 'Yüksek'}", 3)


def on_accessory_change(app, accessory):
    app.settings.set("accessory", accessory)
    if getattr(app, "renderer", None) is not None:
        app.renderer.accessory = accessory
    _refresh_preview(app)
    label = COSTUME_LABELS.get(accessory, str(accessory))
    app.say(f"Kostüm: {label}", 3)


def on_retro_change(app):
    enabled = bool(app.retro_var.get())
    app.settings.set("retro_mode", enabled)
    if getattr(app, "renderer", None) is not None and hasattr(app.renderer, "set_retro_mode"):
        app.renderer.set_retro_mode(enabled)
    _refresh_preview(app)
    app.say(f"Retro Pixel modu {'açıldı' if enabled else 'kapandı'}.", 3)


def on_persona_change(app, persona_id):
    app.settings.set("persona", persona_id)
    if hasattr(app, "persona_var"):
        app.persona_var.set(persona_id)
    label = PERSONA_LABELS.get(persona_id, persona_id)
    app.say(f"Kişilik: {label}", 4)
