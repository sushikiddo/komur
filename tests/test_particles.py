"""Tests for particles.py — canvas particle system."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from particles import ParticleSystem


def test_particle_system_add_and_step():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    ps = ParticleSystem(canvas, 100, 100)
    ps.add(50, 50, 10, 0, "#ff0000", 4, 1.0)
    assert len(ps.particles) == 1
    ps.step(0.1)
    assert ps.particles[0].x == 51.0
    assert ps.particles[0].life < 1.0
    root.destroy()


def test_particle_fades_and_removed():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    ps = ParticleSystem(canvas, 100, 100)
    ps.add(50, 50, 0, 0, "#ff0000", 4, 0.1)
    for _ in range(100):
        ps.step(0.01)
    assert len(ps.particles) == 0
    root.destroy()


def test_particle_cap_enforced():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    ps = ParticleSystem(canvas, 100, 100)
    for i in range(300):
        ps.add(50, 50, 0, 0, "#ff0000", 4, 1.0)
    assert len(ps.particles) <= 200
    root.destroy()
