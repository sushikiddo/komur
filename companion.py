"""İkinci/üçüncü kedi: kendi saydam penceresinde, ana döngüden sürülen hafif arkadaş."""
from __future__ import annotations

import math
import types
try:
    import tkinter as tk
    _TK_ERROR = tk.TclError
except ImportError:
    tk = None
    _TK_ERROR = RuntimeError

import skins
from needs import HungryCatBrain
from renderer import CatRenderer
from window_utils import (
    BG, HEIGHT, IS_MAC, WIDTH, ensure_floating, last_left_click_was_active, mac_app_is_active,
    make_transparent, movement_bounds, place_window, register_mac_right_click,
)

SOCIAL_DISTANCE = 90.0
SOCIAL_INTERACTIONS = ("mutual_groom", "pass_ball", "cuddle_sleep")


def _extract_brain_and_center(cat_or_brain):
    brain = getattr(cat_or_brain, "brain", cat_or_brain)
    x = float(getattr(brain, "x", 0.0))
    y = float(getattr(brain, "y", 0.0))
    w = float(getattr(cat_or_brain, "w", getattr(brain, "width", 0.0)) or 0.0)
    h = float(getattr(cat_or_brain, "h", getattr(brain, "height", 0.0)) or 0.0)
    return brain, (x + w * 0.5, y + h * 0.5)


def cat_distance(cat_a, cat_b) -> float:
    """Return Euclidean center-to-center distance between two cats/brains."""
    _, (ax, ay) = _extract_brain_and_center(cat_a)
    _, (bx, by) = _extract_brain_and_center(cat_b)
    return math.hypot(bx - ax, by - ay)


def select_social_interaction(brain_a, brain_b, preferred: str | None = None) -> str:
    """Pick a social interaction based on moods/states or an explicit preference."""
    if preferred in SOCIAL_INTERACTIONS:
        return preferred
    states = {
        str(getattr(getattr(brain_a, "state", "sit"), "value", getattr(brain_a, "state", "sit"))).lower(),
        str(getattr(getattr(brain_b, "state", "sit"), "value", getattr(brain_b, "state", "sit"))).lower(),
    }
    energy_a = getattr(brain_a, "energy", 100.0)
    energy_b = getattr(brain_b, "energy", 100.0)
    if "sleep" in states or min(float(energy_a), float(energy_b)) < 35.0:
        return "cuddle_sleep"
    if "play" in states or getattr(brain_a, "ball_x", None) is not None or getattr(brain_b, "ball_x", None) is not None:
        return "pass_ball"
    return "mutual_groom"


def apply_social_interaction(cat_a, cat_b, dt: float = 0.016, interaction: str | None = None) -> str | None:
    """Trigger mutual_groom, pass_ball, or cuddle_sleep when distance < 90."""
    brain_a, (ax, ay) = _extract_brain_and_center(cat_a)
    brain_b, (bx, by) = _extract_brain_and_center(cat_b)
    dist = math.hypot(bx - ax, by - ay)

    if dist >= SOCIAL_DISTANCE:
        if getattr(cat_a, "social_partner", None) is cat_b:
            cat_a.social_state = None
            cat_a.social_partner = None
            if getattr(brain_a, "emote", None) in ("heart", "Zzz", "!"):
                brain_a.emote = None
        if getattr(cat_b, "social_partner", None) is cat_a:
            cat_b.social_state = None
            cat_b.social_partner = None
            if getattr(brain_b, "emote", None) in ("heart", "Zzz", "!"):
                brain_b.emote = None
        return None

    mode = select_social_interaction(brain_a, brain_b, preferred=interaction)
    # Face each other
    if bx >= ax:
        brain_a.facing = 1
        brain_b.facing = -1
    else:
        brain_a.facing = -1
        brain_b.facing = 1

    if mode == "mutual_groom":
        brain_a.state = "groom"
        brain_b.state = "groom"
        brain_a.emote = "heart"
        brain_b.emote = "heart"
    elif mode == "pass_ball":
        brain_a.state = "play"
        brain_b.state = "play"
        phase = float(getattr(cat_a, "_ball_pass_phase", 0.0)) + max(0.0, float(dt)) * 2.2
        cat_a._ball_pass_phase = phase
        cat_b._ball_pass_phase = phase
        t_norm = 0.5 + 0.5 * math.sin(phase)
        w_a = float(getattr(brain_a, "width", 260.0) or 260.0)
        w_b = float(getattr(brain_b, "width", 260.0) or 260.0)
        h_a = float(getattr(brain_a, "height", 280.0) or 280.0)
        h_b = float(getattr(brain_b, "height", 280.0) or 280.0)
        direction = 1.0 if math.cos(phase) >= 0 else -1.0
        brain_a.ball_x = w_a * (0.25 + 0.55 * t_norm)
        brain_a.ball_y = h_a * 0.85
        brain_a.ball_vx = direction * 85.0
        brain_b.ball_x = w_b * (0.80 - 0.55 * t_norm)
        brain_b.ball_y = h_b * 0.85
        brain_b.ball_vx = -direction * 85.0
        brain_a.emote = "!"
        brain_b.emote = "!"
    elif mode == "cuddle_sleep":
        brain_a.state = "sleep"
        brain_b.state = "sleep"
        brain_a.emote = "Zzz"
        brain_b.emote = "Zzz"
        if dist > 28.0 and hasattr(brain_a, "x") and hasattr(brain_b, "x"):
            step = min(1.5, (dist - 28.0) * 0.15)
            dx = (bx - ax) / max(dist, 1e-4)
            brain_a.x += dx * step * 0.5
            brain_b.x -= dx * step * 0.5

    cat_a.social_state = mode
    cat_b.social_state = mode
    cat_a.social_partner = cat_b
    cat_b.social_partner = cat_a
    return mode


def step_companions(companions, dt: float, pointer, primary_cat=None) -> list[str | None]:
    """Step all companions and resolve pairwise social interactions."""
    cats = list(companions)
    if primary_cat is not None:
        cats.insert(0, primary_cat)
    results: list[str | None] = []
    for comp in companions:
        peers = [c for c in cats if c is not comp]
        comp.step(dt, pointer, peers=peers)
        results.append(getattr(comp, "social_state", None))
    return results


class Companion:
    """A second (or third…) cat in its own transparent window, driven by the
    main loop. Lighter than the primary cat: no panel, menu or hotkey."""

    def __init__(self, root, area, scale, skin, needs, activity="sakin",
                 start_pos=None, on_menu=None, index=0):
        self.w = round(WIDTH * scale)
        self.h = round(HEIGHT * scale)
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        title = "Kömür — Arkadaş" if index == 0 else f"Kömür — Arkadaş {index + 1}"
        self.window.title(title)
        make_transparent(self.window)
        self.canvas = tk.Canvas(self.window, width=self.w, height=self.h,
                                bg=BG, highlightthickness=0, borderwidth=0)
        self.canvas.pack()
        self.brain = HungryCatBrain(movement_bounds(area, self.w, self.h),
                                    width=self.w, height=self.h, needs=needs, activity=activity)
        if start_pos is not None:
            self.brain.move_to(start_pos[0], start_pos[1])
        else:
            self.brain.move_to(area.left + 40, area.bottom - self.h - 20)
        self.renderer = skins.apply_skin(CatRenderer(self.canvas, self.w, self.h), skin)
        self.animation_time = 0.0
        self.social_state = None
        self.social_partner = None
        self._ball_pass_phase = 0.0
        self._drag_origin = None
        self._dragged = False
        self._pressed_while_active = True
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        if callable(on_menu):
            legacy_aqua = IS_MAC and tk.TkVersion < 8.7
            menu_btn = "<Button-2>" if legacy_aqua else "<Button-3>"
            self.canvas.bind(menu_btn, on_menu)
            self.canvas.bind("<<ContextMenu>>", on_menu)
            if IS_MAC:
                self.canvas.bind("<Control-Button-1>", lambda e: (on_menu(e), "break")[1])
                register_mac_right_click(
                    self.window,
                    lambda sx, sy, fn=on_menu: fn(types.SimpleNamespace(x_root=sx, y_root=sy)),
                )
        self.renderer.draw(self.brain, 0.0, "")
        self.window.geometry(f"{self.w}x{self.h}+{round(self.brain.x)}+{round(self.brain.y)}")
        self.window.update_idletasks()
        self.window.deiconify()
        ensure_floating(self.window)
        self._apply_position()

    def _press(self, event):
        if IS_MAC and (getattr(event, "state", 0) & 0x4):
            return
        self._pressed_while_active = last_left_click_was_active() and mac_app_is_active()
        self._drag_origin = (event.x_root, event.y_root, self.brain.x, self.brain.y)
        self._dragged = False

    def _drag(self, event):
        if self._drag_origin is None:
            return
        px, py, x, y = self._drag_origin
        dx, dy = event.x_root - px, event.y_root - py
        if dx * dx + dy * dy > 25:
            self._dragged = True
        if self._dragged:
            self.brain.move_to(x + dx, y + dy)
            self._apply_position()

    def _release(self, _event):
        if self._drag_origin is None:
            return
        self._drag_origin = None
        pressed_active = getattr(self, "_pressed_while_active", True)
        self._pressed_while_active = True
        if self._dragged:
            self.brain.rest()
        elif pressed_active:
            self.brain.command("pet")

    def _apply_position(self):
        place_window(self.window, self.brain.x, self.brain.y, self.w, self.h)

    def set_opacity(self, value):
        try:
            self.window.attributes("-alpha", max(0.1, min(1.0, value / 100)))
        except _TK_ERROR:
            pass

    def interact_with(self, other, dt: float = 0.016, interaction: str | None = None) -> str | None:
        """Evaluate social interaction with another cat/companion."""
        return apply_social_interaction(self, other, dt=dt, interaction=interaction)

    def step(self, dt, pointer, peers=None, preferred_social=None):
        if not self.brain.paused:
            self.brain.step(dt, pointer)
            self.animation_time += dt
        if peers:
            nearest = min(
                (p for p in peers if p is not self),
                key=lambda p: cat_distance(self, p),
                default=None,
            )
            if nearest is not None:
                self.interact_with(nearest, dt=dt, interaction=preferred_social)
        self._apply_position()
        self.renderer.draw(self.brain, self.animation_time, "")

    def destroy(self):
        try:
            self.window.destroy()
        except _TK_ERROR:
            pass
