"""Tests for renderer.py with effect orchestrator integration."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from renderer import CatRenderer
from behavior import CatBrain, Bounds
from effect_orchestrator import EffectOrchestrator


def test_renderer_draws_all_states():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=260, height=280)
    r = CatRenderer(canvas, 260, 280)
    brain = CatBrain(Bounds(0, 0, 400, 400), seed=4)
    for state in CatBrain.STATES:
        brain.state = state
        r.draw(brain, 1.0, "test")
        assert len(canvas.find_all()) > 10
    root.destroy()


def test_renderer_draws_with_effect_orchestrator():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=260, height=280)
    r = CatRenderer(canvas, 260, 280)
    eo = EffectOrchestrator(canvas, 260, 280, sound_enabled=False)
    brain = CatBrain(Bounds(0, 0, 400, 400), seed=1)
    r.draw(brain, 1.0, "test", effect_orchestrator=eo)
    assert len(canvas.find_all()) > 10
    root.destroy()


def test_renderer_set_effect_orchestrator():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=260, height=280)
    r = CatRenderer(canvas, 260, 280)
    assert r.effect_orchestrator is None
    eo = EffectOrchestrator(canvas, 260, 280, sound_enabled=False)
    r.set_effect_orchestrator(eo)
    assert r.effect_orchestrator is eo
    root.destroy()


def test_renderer_breathing_sleep():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=260, height=280)
    r = CatRenderer(canvas, 260, 280)
    brain = CatBrain(Bounds(0, 0, 400, 400), seed=1)
    brain.state = "sleep"
    r.draw(brain, 1.0, "test")
    root.destroy()
