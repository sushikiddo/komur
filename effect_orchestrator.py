"""Ses + Görsel eşzamanlı orkestratör. Durum geçiş animasyonları, mikro hareketler."""
from __future__ import annotations

import random

import sounds
from physics_particles import PhysicsParticleSystem


class EffectOrchestrator:
    def __init__(self, canvas, width, height, sound_enabled=True, quality="high"):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.particles = PhysicsParticleSystem(canvas, width, height, quality)
        self.sound_enabled = sound_enabled
        self.quality = quality
        self.cat_screen_x = None
        self.screen_w = 1920
        self._micro_timers = {}

    def _play_sound(self, name, **extra):
        """Play a sound routed with the cat's current 2D screen X stereo pan."""
        sounds.play(
            name,
            enabled=self.sound_enabled,
            quality=self.quality,
            pan_x=getattr(self, "cat_screen_x", None),
            screen_w=getattr(self, "screen_w", 1920),
            **extra,
        )

    def set_sound(self, enabled):
        self.sound_enabled = bool(enabled)

    def set_quality(self, quality):
        self.quality = quality
        self.particles.quality = quality

    def trigger(self, kind, x, y, **params):
        cx = x + self.width / 2
        cy = y + self.height / 2

        if kind == "pet":
            self._play_sound("purr")
            self.particles.emit("heart", cx, cy, count=30)
            self.particles.emit("fur_ruffle", cx, cy - 30, count=15)
            self._schedule_micro("whisker_vibrate", cx - 20, cy - 10, 0.3, 8)
            self._schedule_micro("whisker_vibrate", cx + 20, cy - 10, 0.3, 8)

        elif kind == "feed":
            self._play_sound("happy")
            self.particles.emit("fur_ruffle", cx, cy - 20, count=18)

        elif kind == "play":
            self._play_sound("play")
            self.particles.emit("ball_trail", cx, cy, count=20)
            self.particles.emit("fur_ruffle", cx, cy, count=12)

        elif kind == "knead":
            self._play_sound("knead")
            self.particles.emit("pawprint", cx, cy + 20, count=15)
            self._schedule_repeat("pawprint", cx, cy + 20, 0.4, 8, count=6)

        elif kind == "chirp":
            self._play_sound("chirp")
            self._schedule_micro("ear_twitch", cx - 25, cy - 35, 0.15, 5)
            self._schedule_micro("ear_twitch", cx + 25, cy - 35, 0.15, 5)

        elif kind == "hiss":
            self._play_sound("hiss")
            self.particles.emit("fur_ruffle", cx, cy, count=25)
            self._schedule_micro("ear_twitch", cx - 30, cy - 40, 0.5, 10)

        elif kind == "sneeze":
            self._play_sound("sneeze")
            self.particles.emit("breath", cx, cy - 30, count=30)
            self._schedule_shake(cx, cy - 20, 0.3, 10)

        elif kind == "sleep":
            self._play_sound("sleep")
            self.particles.emit("z_raise", cx, cy - 40, count=6)
            self._schedule_breathing(cx, cy - 20, 4.0)

        elif kind == "wake":
            self._play_sound("meow", pitch_shift="auto")
            self.particles.emit("fur_ruffle", cx, cy, count=18)
            self._schedule_micro("ear_twitch", cx - 25, cy - 35, 0.2, 6)
            self._schedule_micro("ear_twitch", cx + 25, cy - 35, 0.2, 6)

        elif kind == "follow_start":
            self._play_sound("meow", pitch_shift="auto")
            self.particles.emit("breath", cx, cy, count=10)

        elif kind == "idle_purr":
            self._play_sound("purr")
            self.particles.emit("breath", cx, cy - 15, count=6)

        elif kind == "roll":
            # Use canvas-local coordinates so small canvases keep the effect near
            # the reclining cat. The pose itself is silent; no second sound is
            # layered over the behavior's state audio.
            self.particles.emit("fur_ruffle", cx, cy + self.height * 0.18, count=10)
            self.particles.emit("pawprint", cx - self.width * 0.16,
                                cy + self.height * 0.28, count=4)

        elif kind == "bored":
            self._schedule_micro("ear_twitch", cx - self.width * 0.1,
                                 cy - self.height * 0.12, 0.35, 2)

        elif kind == "yawn":
            self.particles.emit("breath", cx + self.width * 0.12,
                                cy - self.height * 0.12, count=3)

    def trigger_state_enter(self, state, x, y):
        cx = x + self.width / 2
        cy = y + self.height / 2
        if state == "sleep":
            self.trigger("sleep", x, y)
        elif state == "knead":
            self.trigger("knead", x, y)
        elif state == "play":
            self.trigger("play", x, y)
        elif state == "chirp":
            self.trigger("chirp", x, y)
        elif state == "hiss":
            self.trigger("hiss", x, y)
        elif state == "sneeze":
            self.trigger("sneeze", x, y)
        elif state in ("roll", "bored", "yawn"):
            self.trigger(state, x, y)

    def trigger_state_exit(self, state, x, y):
        cx = x + self.width / 2
        cy = y + self.height / 2
        if state == "sleep":
            self.trigger("wake", x, y)
        elif state == "play":
            self.particles.emit("fur_ruffle", cx, cy, count=8)

    def _schedule_micro(self, kind, x, y, interval, count):
        key = f"{kind}_{x}_{y}"
        self._micro_timers[key] = {
            "kind": kind, "x": x, "y": y, "interval": interval,
            "count": count, "timer": 0.0,
        }

    def _schedule_repeat(self, kind, x, y, interval, repeat, count):
        key = f"repeat_{kind}_{x}_{y}"
        self._micro_timers[key] = {
            "kind": kind, "x": x, "y": y, "interval": interval,
            "count": count, "repeat": repeat, "timer": 0.0,
        }

    def _schedule_breathing(self, x, y, duration):
        key = f"breathing_{x}_{y}"
        self._micro_timers[key] = {
            "kind": "breath", "x": x, "y": y, "interval": 1.5,
            "count": 2, "duration": duration, "timer": 0.0,
        }

    def _schedule_shake(self, x, y, duration, intensity):
        key = f"shake_{x}_{y}"
        self._micro_timers[key] = {
            "kind": "shake", "x": x, "y": y, "duration": duration,
            "intensity": intensity, "timer": 0.0,
        }

    def step(self, dt):
        self.particles.step(dt)
        to_remove = []
        for key, timer in self._micro_timers.items():
            timer["timer"] += dt
            if timer["kind"] == "shake":
                if timer["timer"] >= timer["duration"]:
                    to_remove.append(key)
                continue
            if timer["timer"] >= timer["interval"]:
                timer["timer"] = 0.0
                if timer["kind"] == "breath":
                    if "duration" in timer:
                        timer["duration"] -= timer["interval"]
                        if timer["duration"] <= 0:
                            to_remove.append(key)
                            continue
                    self.particles.emit("breath", timer["x"], timer["y"], count=timer["count"])
                elif timer["kind"] in ("whisker_vibrate", "ear_twitch"):
                    self.particles.emit(timer["kind"], timer["x"], timer["y"], count=1)
                    timer["count"] -= 1
                    if timer["count"] <= 0:
                        to_remove.append(key)
                else:
                    self.particles.emit(timer["kind"], timer["x"], timer["y"], count=timer.get("count", 1))
                    if "repeat" in timer:
                        timer["repeat"] -= 1
                        if timer["repeat"] <= 0:
                            to_remove.append(key)
        for key in to_remove:
            del self._micro_timers[key]

    def draw(self):
        self.particles.draw()

    def clear(self):
        self.particles.clear()
        self._micro_timers.clear()
