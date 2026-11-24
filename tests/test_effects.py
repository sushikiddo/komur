"""Tests for effects.py — audio-visual effect trigger."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
import sounds
from effects import EffectManager


def test_effects_trigger_heart():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    em = EffectManager(canvas, 100, 100, sound_enabled=False)
    em.trigger("heart", 50, 50)
    assert len(em.particle_system.particles) > 0
    root.destroy()


def test_effects_trigger_pawprint():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    em = EffectManager(canvas, 100, 100, sound_enabled=False)
    em.trigger("pawprint", 50, 50)
    assert len(em.particle_system.particles) > 0
    root.destroy()


def test_effects_set_sound():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    em = EffectManager(canvas, 100, 100, sound_enabled=True)
    em.set_sound(False)
    assert em.sound_enabled is False
    root.destroy()


def test_effects_strict_sound_whitelist(monkeypatch):
    played = []
    monkeypatch.setattr(sounds, "play", lambda name="meow", **kw: played.append((name, kw.get("enabled"))))
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=100, height=100)
        em = EffectManager(canvas, 100, 100, sound_enabled=True)

        # Silent visual-only events: play, feed, sleep
        em.on_play(10, 10)
        em.on_feed(10, 10)
        em.on_sleep(10, 10)
        em.trigger("ball_trail", 10, 10)
        em.trigger("pawprint", 10, 10)
        em.trigger("z_raise", 10, 10)
        assert played == []
        assert len(em.particle_system.particles) > 0

        # Allowed 3 events: pet -> purr, yawn -> yawn, wake -> meow
        em.on_pet(10, 10)
        em.on_yawn(10, 10)
        em.on_wake(10, 10)
        assert played == [("purr", True), ("yawn", True), ("meow", True)]
    finally:
        root.destroy()
