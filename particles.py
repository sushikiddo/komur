"""Canvas bazlı parakül sistemi. Fade-out, hareket, sınırlı sayı."""
from __future__ import annotations

import tkinter as tk

MAX_PARTICLES = 200


class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "color", "size", "life", "max_life")

    def __init__(self, x, y, vx, vy, color, size, life):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.life = life
        self.max_life = life


class ParticleSystem:
    def __init__(self, canvas: tk.Canvas, width: int, height: int):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.particles = []
        self._tag = "particles"

    def add(self, x, y, vx, vy, color="#ffffff", size=3, life=0.8):
        if len(self.particles) >= MAX_PARTICLES:
            return
        self.particles.append(_Particle(x, y, vx, vy, color, size, life))

    def step(self, dt):
        dt = min(float(dt), 0.1)
        alive = []
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life -= dt
            if p.life > 0:
                alive.append(p)
        self.particles = alive

    def draw(self):
        self.canvas.delete(self._tag)
        for p in self.particles:
            alpha = p.life / p.max_life
            if alpha <= 0:
                continue
            s = max(1, p.size * alpha)
            x, y = p.x, p.y
            self.canvas.create_oval(
                x - s, y - s, x + s, y + s,
                fill=p.color, outline="", tags=self._tag,
            )

    def clear(self):
        self.canvas.delete(self._tag)
        self.particles.clear()
