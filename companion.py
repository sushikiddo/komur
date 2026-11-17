"""İkinci/üçüncü kedi: kendi saydam penceresinde, ana döngüden sürülen hafif arkadaş."""
from __future__ import annotations

import tkinter as tk

import skins
from needs import HungryCatBrain
from renderer import CatRenderer
from window_utils import BG, HEIGHT, WIDTH, make_transparent, movement_bounds, place_window


class Companion:
    """A second (or third…) cat in its own transparent window, driven by the
    main loop. Lighter than the primary cat: no panel, menu or hotkey."""

    def __init__(self, root, area, scale, skin, needs, activity="sakin"):
        self.w = round(WIDTH * scale)
        self.h = round(HEIGHT * scale)
        self.window = tk.Toplevel(root)
        make_transparent(self.window)
        self.canvas = tk.Canvas(self.window, width=self.w, height=self.h,
                                bg=BG, highlightthickness=0, borderwidth=0)
        self.canvas.pack()
        self.brain = HungryCatBrain(movement_bounds(area, self.w, self.h),
                                    width=self.w, height=self.h, needs=needs, activity=activity)
        self.brain.move_to(area.left + 40, area.bottom - self.h - 20)
        self.renderer = skins.apply_skin(CatRenderer(self.canvas, self.w, self.h), skin)
        self.animation_time = 0.0
        self.window.geometry(f"{self.w}x{self.h}+0+0")
        self.window.update_idletasks()
        self._apply_position()

    def _apply_position(self):
        place_window(self.window, self.brain.x, self.brain.y, self.w, self.h)

    def set_opacity(self, value):
        try:
            self.window.attributes("-alpha", max(0.1, min(1.0, value / 100)))
        except tk.TclError:
            pass

    def step(self, dt, pointer):
        if not self.brain.paused:
            self.brain.step(dt, pointer)
            self.animation_time += dt
        self._apply_position()
        self.renderer.draw(self.brain, self.animation_time, "")

    def destroy(self):
        try:
            self.window.destroy()
        except tk.TclError:
            pass
