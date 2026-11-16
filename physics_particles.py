"""Fizik motorlu partikül sistemi: yerçekimi, rüzgâr, türbülans, çarpışma, yaşam döngüsü.
Türler: breath, heart, pawprint, ball_trail, z_raise, fur_ruffle, ear_twitch, whisker_vibrate
"""
from __future__ import annotations

import math
import random
import tkinter as tk

GRAVITY = 9.81 * 30  # piksel/s^2 (ekran ölçeğinde)
AIR_RESISTANCE = 0.98
MAX_PARTICLES = 1200


class _PhysicsParticle:
    __slots__ = (
        "x", "y", "vx", "vy", "ax", "ay", "color", "size",
        "life", "max_life", "kind", "spin", "spin_speed", "tag", "fade_curve",
    )

    def __init__(self, x, y, vx, vy, color, size, life, kind="default"):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.ax = 0.0
        self.ay = GRAVITY
        self.color = color
        self.size = size
        self.life = life
        self.max_life = life
        self.kind = kind
        self.spin = 0.0
        self.spin_speed = random.uniform(-2, 2)
        self.tag = None
        self.fade_curve = "linear"


class PhysicsParticleSystem:
    def __init__(self, canvas: tk.Canvas, width: int, height: int, quality="high"):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.quality = quality
        self.particles = []
        self._tag = "physics_particles"
        self.wind_x = 0.0
        self.wind_y = 0.0
        self.turbulence = 0.0

    def set_environment(self, wind_x=0.0, wind_y=0.0, turbulence=0.0):
        self.wind_x = wind_x
        self.wind_y = wind_y
        self.turbulence = turbulence

    def emit(self, kind, x, y, **params):
        if len(self.particles) >= MAX_PARTICLES:
            return
        count = params.get("count", 1)
        for _ in range(count):
            self._create_particle(kind, x, y, params)

    def _create_particle(self, kind, x, y, params):
        if kind == "breath":
            angle = random.uniform(-0.3, 0.3)
            speed = random.uniform(20, 50)
            p = _PhysicsParticle(
                x, y,
                math.cos(angle) * speed + self.wind_x,
                math.sin(angle) * speed - 30 + self.wind_y,
                "#c8d0d8", random.uniform(6, 12), random.uniform(1.2, 2.0), "breath",
            )
            p.ay = -GRAVITY * 0.3
            p.fade_curve = "sqrt"

        elif kind == "heart":
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(40, 80)
            p = _PhysicsParticle(
                x, y,
                math.cos(angle) * speed,
                math.sin(angle) * speed - 40,
                random.choice(["#ff6b8a", "#ff4757", "#ff3838", "#ffd6e0"]),
                random.uniform(6, 10), random.uniform(1.0, 1.5), "heart",
            )
            p.ay = -GRAVITY * 0.5
            p.spin_speed = random.uniform(-5, 5)

        elif kind == "pawprint":
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(10, 30)
            p = _PhysicsParticle(
                x, y,
                math.cos(angle) * speed,
                math.sin(angle) * speed,
                random.choice(["#ffffff", "#e8e8e8", "#d0d0d0"]),
                random.uniform(4, 8), random.uniform(0.8, 1.3), "pawprint",
            )
            p.ay = GRAVITY * 0.1
            p.fade_curve = "quadratic"

        elif kind == "ball_trail":
            angle = random.uniform(-0.5, 0.5)
            speed = random.uniform(30, 60)
            p = _PhysicsParticle(
                x, y,
                math.cos(angle) * speed,
                math.sin(angle) * speed - 20,
                random.choice(["#e99444", "#d68438", "#c4742c", "#ffda90"]),
                random.uniform(4, 7), random.uniform(0.5, 0.8), "ball_trail",
            )

        elif kind == "z_raise":
            p = _PhysicsParticle(
                x, y - 20,
                0, -15,
                "#ffffff", 12, random.uniform(2.0, 3.0), "z_raise",
            )
            p.ay = -GRAVITY * 0.2

        elif kind == "fur_ruffle":
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(50, 100)
            p = _PhysicsParticle(
                x, y,
                math.cos(angle) * speed + self.wind_x * 2,
                math.sin(angle) * speed + self.wind_y * 2,
                "#39434b", random.uniform(2, 5), random.uniform(0.2, 0.5), "fur_ruffle",
            )
            p.ay = GRAVITY * 0.05

        elif kind == "ear_twitch":
            p = _PhysicsParticle(
                x + random.uniform(-5, 5), y + random.uniform(-5, 5),
                random.uniform(-10, 10), random.uniform(-10, 10),
                "#50606a", random.uniform(0.5, 1.5), random.uniform(0.05, 0.15), "ear_twitch",
            )

        elif kind == "whisker_vibrate":
            p = _PhysicsParticle(
                x + random.uniform(-15, 15), y + random.uniform(-3, 3),
                random.uniform(-5, 5), random.uniform(-5, 5),
                "#ffffff", random.uniform(0.5, 1), random.uniform(0.05, 0.1), "whisker_vibrate",
            )

        else:
            return

        self.particles.append(p)

    def step(self, dt):
        dt = min(float(dt), 0.05)
        alive = []
        for p in self.particles:
            p.vx += p.ax * dt
            p.vy += p.ay * dt

            p.vx += self.wind_x * dt * 0.5
            p.vy += self.wind_y * dt * 0.5

            if self.turbulence > 0:
                p.vx += random.uniform(-1, 1) * self.turbulence * dt * 100
                p.vy += random.uniform(-1, 1) * self.turbulence * dt * 100

            p.vx *= AIR_RESISTANCE
            p.vy *= AIR_RESISTANCE

            p.x += p.vx * dt
            p.y += p.vy * dt

            p.spin += p.spin_speed * dt
            p.life -= dt

            if p.life > 0 and 0 <= p.x <= self.width and 0 <= p.y <= self.height:
                alive.append(p)
        self.particles = alive

    def draw(self):
        self.canvas.delete(self._tag)
        for p in self.particles:
            alpha = p.life / p.max_life
            if alpha <= 0:
                continue

            if p.fade_curve == "sqrt":
                alpha = math.sqrt(alpha)
            elif p.fade_curve == "quadratic":
                alpha = alpha * alpha

            s = max(0.5, p.size * alpha)
            x, y = p.x, p.y

            if p.kind == "z_raise":
                tag = self.canvas.create_text(
                    x, y, text="Z" if alpha > 0.5 else "z",
                    fill=p.color,
                    font=("Arial", max(8, int(16 * alpha)), "bold"),
                    tags=self._tag,
                )
            elif p.kind in ("ear_twitch", "whisker_vibrate"):
                x2 = x + math.cos(p.spin) * s * 3
                y2 = y + math.sin(p.spin) * s * 3
                tag = self.canvas.create_line(
                    x, y, x2, y2, fill=p.color, width=max(1, s),
                    capstyle="round", tags=self._tag,
                )
            elif p.kind == "heart":
                tag = self.canvas.create_polygon(
                    x, y - s * 0.3,
                    x - s, y - s,
                    x - s * 2, y,
                    x, y + s * 1.5,
                    x + s * 2, y,
                    x + s, y - s,
                    fill=p.color, outline="", tags=self._tag,
                )
            else:
                tag = self.canvas.create_oval(
                    x - s, y - s, x + s, y + s,
                    fill=p.color, outline="", tags=self._tag,
                )
            p.tag = tag

    def clear(self):
        self.canvas.delete(self._tag)
        self.particles.clear()
