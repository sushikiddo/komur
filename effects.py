"""Ses + görsel eşlik tetikleyici. Efekt kuyruğu, çakışma önleme."""
from __future__ import annotations

import math
import random

import audio
from particles import ParticleSystem


def _random_unif(lo, hi):
    return random.uniform(lo, hi)


class EffectManager:
    def __init__(self, canvas, width, height, sound_enabled=True):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.particle_system = ParticleSystem(canvas, width, height)
        self.sound_enabled = bool(sound_enabled)

    def set_sound(self, enabled):
        self.sound_enabled = bool(enabled)

    def trigger(self, kind, x, y):
        cx = x + self.width / 2
        cy = y + self.height / 2

        if kind == "heart":
            audio.play("purr", enabled=self.sound_enabled)
            for i in range(12):
                ang = math.pi * 2 * i / 12
                self.particle_system.add(
                    cx,
                    cy,
                    math.cos(ang) * 40,
                    math.sin(ang) * 40 - 20,
                    "#ff6b8a",
                    4,
                    0.9,
                )
        elif kind == "pawprint":
            audio.play("meow", enabled=self.sound_enabled)
            for i in range(8):
                ang = math.pi * 2 * i / 8
                self.particle_system.add(
                    cx,
                    cy,
                    math.cos(ang) * 30,
                    math.sin(ang) * 30,
                    "#ffffff",
                    3,
                    0.7,
                )
        elif kind == "ball_trail":
            audio.play("play", enabled=self.sound_enabled)
            for _ in range(5):
                self.particle_system.add(
                    cx,
                    cy,
                    _random_unif(-1, 1) * 20,
                    _random_unif(-1, 1) * 20,
                    "#e99444",
                    3,
                    0.5,
                )
        elif kind == "breath":
            audio.play("purr", enabled=self.sound_enabled)
        elif kind == "z_raise":
            audio.play("sleep", enabled=self.sound_enabled)
            for i in range(6):
                self.particle_system.add(
                    cx, cy - 30, 0, -15, "#ffffff", 4, 1.2,
                )

    def step(self, dt):
        self.particle_system.step(dt)

    def draw(self):
        self.particle_system.draw()

    def clear(self):
        self.particle_system.clear()
