"""Hunger / mood layer on top of the verified CatBrain.

Implemented as a subclass so behavior.py stays byte-for-byte the original. When
``enabled`` is False the extra fields stay inert and the brain behaves exactly
like the base CatBrain.
"""
from __future__ import annotations

import math

from behavior import CatBrain

# hunger runs 0 (full) .. 100 (starving)
HUNGER_RATE = 0.45        # points gained per second
FEED_AMOUNT = 55.0        # points removed per feeding
STARVING = 75.0           # above this, happiness suffers and the cat begs


class HungryCatBrain(CatBrain):
    def __init__(self, *args, needs=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.needs_enabled = needs
        self.hunger = 25.0
        self._beg_cooldown = 0.0
        self._last_idle_purr = 0.0

    def _change(self, state, duration=None):
        """Extend CatBrain._change with new cat states."""
        if state in ("knead", "chirp", "hiss", "sneeze", "purr_idle"):
            ranges = {
                "knead": (4.0, 6.0),
                "chirp": (1.5, 2.5),
                "hiss": (1.0, 2.0),
                "sneeze": (0.8, 1.2),
                "purr_idle": (3.0, 5.0),
            }
            self.state, self.elapsed = state, 0.0
            lo, hi = ranges[state]
            self._duration = duration if duration is not None else self._rng.uniform(lo, hi)
            if state == "knead":
                self.target_x = self._rng.uniform(self.bounds.left, self.bounds.right)
                self.target_y = self._rng.uniform(self.bounds.top, self.bounds.bottom)
            return
        super()._change(state, duration)

    def feed(self):
        self.hunger = max(0.0, self.hunger - FEED_AMOUNT)
        self.happiness = min(100.0, self.happiness + 8)
        self._sleep_requested = False
        self._change("sit")
        self.message = "Nom nom… teşekkürler!"

    def command(self, name):
        name = str(name).lower().strip()
        if name == "feed":
            self.feed()
            return
        if name == "knead":
            self._sleep_requested = False
            self._change("knead", duration=4.0)
            self.message = "Süpürüyorum…"
            return
        if name == "chirp":
            self._sleep_requested = False
            self._change("chirp", duration=2.0)
            self.message = "Mır, mır!"
            return
        if name == "hiss":
            self._sleep_requested = False
            self._change("hiss", duration=1.5)
            self.message = "Fıss!"
            return
        if name == "sneeze":
            self._sleep_requested = False
            self._change("sneeze", duration=1.0)
            self.message = "Hapsışım!"
            return
        if name == "purr_idle":
            self._sleep_requested = False
            self._change("purr_idle")
            self.message = "Mırrrrr…"
            return
        super().command(name)

    @property
    def mood(self):
        """A short Turkish mood word from the current drives."""
        if self.paused:
            return "Duraklatıldı"
        if self.needs_enabled and self.hunger >= STARVING:
            return "Aç"
        if self.energy < 25:
            return "Yorgun"
        if self.happiness >= 75:
            return "Mutlu"
        if self.happiness < 40:
            return "Keyifsiz"
        return "Keyifli"

    def step(self, dt, pointer=None):
        try:
            dt = float(dt)
        except (TypeError, ValueError):
            return
        if not math.isfinite(dt) or dt <= 0:
            return
        dt = min(dt, 0.1)
        super().step(dt, pointer)
        if not self.needs_enabled or self.paused:
            return
        # eating-while-playing is less tiring on the appetite; sleeping too.
        rate = HUNGER_RATE * (0.4 if self.state == "sleep" else 1.0)
        self.hunger = max(0.0, min(100.0, self.hunger + rate * dt))
        if self.hunger >= STARVING:
            self.happiness = max(0.0, self.happiness - 0.3 * dt)
            self._beg_cooldown -= dt
            if self._beg_cooldown <= 0 and self.state not in ("sleep",):
                self.message = "Karnım aç… mama?"
                self._beg_cooldown = 9.0

        # İdle mırlama: mutlu ve tokken kediler periyodik mırıldar
        if (self.happiness > 70 and self.hunger < 30 and
                self.state in ("sit", "look") and not self.paused):
            self._last_idle_purr += dt
            if self._last_idle_purr > 15.0:
                self._last_idle_purr = 0.0
