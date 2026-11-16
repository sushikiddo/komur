"""Headless tests for the behavior/renderer/needs core — no window required.

Run with ``python -m pytest`` or directly with ``python tests/test_core.py``.
"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from behavior import Bounds, CatBrain
from needs import HungryCatBrain
from renderer import CatRenderer
import skins


def test_brain_is_deterministic():
    a = CatBrain(Bounds(0, 0, 400, 400), seed=7)
    b = CatBrain(Bounds(0, 0, 400, 400), seed=7)
    for _ in range(300):
        a.step(0.033, (200, 200))
        b.step(0.033, (200, 200))
    assert (a.state, round(a.x, 6), round(a.y, 6)) == (b.state, round(b.x, 6), round(b.y, 6))


def test_commands_change_state():
    brain = CatBrain(Bounds(0, 0, 400, 400), seed=1)
    brain.command("sleep")
    assert brain.state == "sleep"
    brain.command("play")
    assert brain.state == "play"
    brain.command("pause")
    assert brain.paused is True
    brain.command("resume")
    assert brain.paused is False


def test_energy_and_happiness_stay_bounded():
    brain = CatBrain(Bounds(0, 0, 400, 400), seed=2)
    for _ in range(5000):
        brain.step(0.05)
    assert 0.0 <= brain.energy <= 100.0
    assert 0.0 <= brain.happiness <= 100.0


def test_hunger_grows_and_feeding_helps():
    brain = HungryCatBrain(Bounds(0, 0, 400, 400), seed=3, needs=True)
    start = brain.hunger
    for _ in range(400):
        brain.step(0.05)
    assert brain.hunger > start
    before = brain.hunger
    brain.feed()
    assert brain.hunger < before


def test_needs_new_commands():
    brain = HungryCatBrain(Bounds(0, 0, 400, 400), seed=1, needs=True)
    brain.command("knead")
    assert brain.state == "knead"
    brain.command("chirp")
    assert brain.state == "chirp"
    brain.command("hiss")
    assert brain.state == "hiss"
    brain.command("sneeze")
    assert brain.state == "sneeze"
    brain.command("purr_idle")
    assert brain.state == "purr_idle"




def test_renderer_draws_all_states():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=260, height=280)
    r = CatRenderer(canvas, 260, 280)
    brain = CatBrain(Bounds(0, 0, 400, 400), seed=4)
    for state in CatBrain.STATES:
        brain.state = state
        r.draw(brain, 1.0, "test")
        assert len(canvas.find_all()) > 10  # a real cat, not an empty frame
    root.destroy()


def test_skins_recolor_without_error():
    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=260, height=280)
    r = CatRenderer(canvas, 260, 280)
    brain = CatBrain(Bounds(0, 0, 400, 400), seed=5)
    for skin in skins.skin_order():
        skins.apply_skin(r, skin)
        r.draw(brain, 0.5, "")
        assert len(canvas.find_all()) > 10
    root.destroy()


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
            passed += 1
    print(f"\n{passed} test geçti.")
