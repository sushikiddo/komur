"""Ses + görsel eşlik tetikleyici. Efekt kuyruğu, çakışma önleme."""
from __future__ import annotations

import math
import random

import sounds
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
        self.cat_screen_x = None
        self.screen_w = 1920

    def set_sound(self, enabled):
        self.sound_enabled = bool(enabled)

    def _play_sound(self, name):
        sounds.play(
            name,
            enabled=self.sound_enabled,
            volume=70,
            pan_x=self.cat_screen_x,
            screen_w=self.screen_w,
        )

    def trigger(self, kind, x, y):
        cx = x + self.width / 2
        cy = y + self.height / 2

        if kind == "heart":
            self._play_sound("purr")
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
        elif kind == "yawn":
            self._play_sound("yawn")
            for _ in range(4):
                self.particle_system.add(
                    cx, cy - 12, _random_unif(-8, 8), -12, "#dbeafe", 3, 0.8,
                )
        elif kind == "wake":
            self._play_sound("meow")
            for i in range(8):
                ang = math.pi * 2 * i / 8
                self.particle_system.add(
                    cx, cy, math.cos(ang) * 24, math.sin(ang) * 24, "#fde68a", 3, 0.6,
                )
        elif kind == "breath":
            self.particle_system.add(cx, cy - 10, 0, -10, "#e2e8f0", 3, 0.8)
        elif kind == "z_raise":
            for _ in range(6):
                self.particle_system.add(
                    cx, cy - 30, 0, -15, "#ffffff", 4, 1.2,
                )

    def on_pet(self, x=0, y=0):
        """Sevme efekti: kalp parçacıkları + mırlama sesi."""
        self.trigger("heart", x, y)

    def on_play(self, x=0, y=0):
        """Oyun efekti: yalnız görsel parıltı/toz parçacıkları (SES YOK)."""
        self.trigger("ball_trail", x, y)

    def on_feed(self, x=0, y=0):
        """Mama efekti: yalnız görsel kalp/parçacık (SES YOK)."""
        cx = x + self.width / 2
        cy = y + self.height / 2
        for i in range(8):
            ang = math.pi * 2 * i / 8
            self.particle_system.add(
                cx, cy, math.cos(ang) * 32, math.sin(ang) * 32 - 14, "#ff9eb5", 4, 0.8,
            )

    def on_sleep(self, x=0, y=0):
        """Uyku efekti: yalnız görsel Z parçacıkları (SES YOK; yalnız uyanırken ses çıkar)."""
        self.trigger("z_raise", x, y)

    def on_yawn(self, x=0, y=0):
        """Esneme efekti: nefes parçacığı + esneme sesi."""
        self.trigger("yawn", x, y)

    def on_wake(self, x=0, y=0):
        """Uyanma efekti: görsel parıltı + miyav sesi."""
        self.trigger("wake", x, y)

    def step(self, dt):
        self.particle_system.step(dt)

    def draw(self):
        self.particle_system.draw()

    def clear(self):
        self.particle_system.clear()
