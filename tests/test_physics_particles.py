"""Tests for physics_particles.py — physics motorlu partikül sistemi."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from physics_particles import PhysicsParticleSystem


def test_physics_particles_emit_and_step():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=200, height=200)
    ps = PhysicsParticleSystem(canvas, 200, 200, quality="high")
    ps.emit("breath", 100, 100)
    assert len(ps.particles) > 0
    ps.step(0.016)
    assert all(p.life < p.max_life for p in ps.particles)
    root.destroy()


def test_physics_particles_gravity_and_wind():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=200, height=200)
    ps = PhysicsParticleSystem(canvas, 200, 200, quality="high")
    ps.emit("heart", 100, 100, count=20)
    # Heart particles should launch upward (negative vy in screen coords)
    assert any(p.vy < -30 for p in ps.particles)
    assert ps.particles[0].ay < 0  # upward gravity for heart
    root.destroy()


def test_physics_particle_cap():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    ps = PhysicsParticleSystem(canvas, 100, 100, quality="high")
    for i in range(1000):
        ps.emit("heart", 50, 50)
    assert len(ps.particles) <= 1200
    root.destroy()


def test_physics_particles_fade_and_remove():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=100, height=100)
    ps = PhysicsParticleSystem(canvas, 100, 100, quality="high")
    ps.emit("breath", 50, 50)
    for _ in range(500):
        ps.step(0.01)
    assert len(ps.particles) == 0
    root.destroy()


def test_physics_particles_draw():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=200, height=200)
    ps = PhysicsParticleSystem(canvas, 200, 200, quality="high")
    ps.emit("heart", 100, 100)
    ps.draw()
    assert len(canvas.find_all()) > 0
    root.destroy()
