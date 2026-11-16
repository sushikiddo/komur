"""Tests for effect_orchestrator.py — ses + görsel eşlik tetikleyici."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from effect_orchestrator import EffectOrchestrator


def test_orchestrator_trigger_heart():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    eo = EffectOrchestrator(canvas, 100, 100, sound_enabled=False)
    eo.trigger("pet", 50, 50)
    assert len(eo.particles.particles) > 0
    root.destroy()


def test_orchestrator_trigger_knead():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    eo = EffectOrchestrator(canvas, 100, 100, sound_enabled=False)
    eo.trigger("knead", 50, 50)
    assert len(eo.particles.particles) > 0
    root.destroy()


def test_orchestrator_trigger_sleep():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    eo = EffectOrchestrator(canvas, 100, 100, sound_enabled=False)
    eo.trigger("sleep", 50, 50)
    assert len(eo.particles.particles) > 0
    root.destroy()


def test_orchestrator_set_sound():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    eo = EffectOrchestrator(canvas, 100, 100, sound_enabled=True)
    eo.set_sound(False)
    assert eo.sound_enabled is False
    root.destroy()


def test_orchestrator_state_enter_exit():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    eo = EffectOrchestrator(canvas, 100, 100, sound_enabled=False)
    eo.trigger_state_enter("sleep", 50, 50)
    assert len(eo.particles.particles) > 0
    eo.trigger_state_exit("sleep", 50, 50)
    root.destroy()
