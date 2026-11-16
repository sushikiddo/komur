"""Tests for effects.py — audio-visual effect trigger."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
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
