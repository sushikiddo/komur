"""Focused regressions for boredom, rolling, and yawning behavior."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from behavior import Bounds, CatBrain
from needs import HungryCatBrain
from renderer import CatRenderer
from effect_orchestrator import EffectOrchestrator
import sounds


class Canvas:
    def __init__(self):
        self.items = []

    def delete(self, _tag):
        self.items.clear()

    def _add(self, kind, args, kwargs):
        self.items.append((kind, args, kwargs))
        return len(self.items)

    def create_oval(self, *args, **kwargs):
        return self._add("oval", args, kwargs)

    def create_polygon(self, *args, **kwargs):
        return self._add("polygon", args, kwargs)

    def create_line(self, *args, **kwargs):
        return self._add("line", args, kwargs)

    def create_text(self, *args, **kwargs):
        return self._add("text", args, kwargs)


def brain(seed=7):
    return HungryCatBrain(Bounds(0, 0, 400, 300), seed=seed)


def test_idle_cat_can_enter_bored_and_roll_states():
    cat = brain()
    cat._change("sit", duration=0.05)
    cat._idle_seconds = 31
    cat.step(0.05)
    assert cat.state in ("bored", "roll")
    assert cat._idle_seconds == 0


def test_roll_is_timed_and_explicit_commands_keep_priority():
    cat = brain()
    cat.command("roll")
    assert cat.state == "roll"
    cat.step(0.1)
    assert cat.state == "roll"

    cat.command("follow")
    cat._idle_seconds = 90
    cat.step(0.1, (300, 200))
    assert cat.state == "follow"

    cat.command("sleep")
    cat._idle_seconds = 90
    cat.step(0.1)
    assert cat.state == "sleep"

    cat.command("play")
    assert cat.state == "play"


def test_bored_and_yawn_commands_clear_pause_and_sleep_request():
    cat = brain()
    cat.command("sleep")
    cat.paused = True
    cat.command("bored")
    assert cat.state == "bored"
    assert not cat.paused and not cat._sleep_requested
    cat.paused = True
    cat.command("yawn")
    assert cat.state == "yawn"
    assert not cat.paused and not cat._sleep_requested


def test_needs_layer_rejects_invalid_dt_without_advancing_either_layer():
    for invalid_dt in (float("inf"), float("-inf"), float("nan"), "invalid", None):
        cat = brain()
        before = (cat.elapsed, cat.hunger, cat.energy, cat.happiness, cat.state)
        cat.step(invalid_dt)
        assert (cat.elapsed, cat.hunger, cat.energy, cat.happiness, cat.state) == before


def test_needs_layer_advances_both_layers_for_finite_dt():
    cat = brain()
    cat.step(0.05)
    assert cat.elapsed == 0.05
    assert cat.hunger == 25.0 + 0.45 * 0.05


def test_existing_yawn_remains_a_finite_natural_pose():
    cat = brain()
    cat._change("yawn", duration=1.5)
    cat.step(0.1)
    assert cat.state == "yawn"
    assert math.isfinite(cat.elapsed)


def test_new_poses_render_at_small_scale_with_tuxedo_white_visible():
    canvas = Canvas()
    renderer = CatRenderer(canvas, width=104, height=112)
    cat = brain()
    for state in ("bored", "roll", "yawn"):
        cat.state = state
        renderer.draw(cat, 1.2)
        assert len(canvas.items) > 10
        assert any(item[2].get("fill") == renderer.WHITE for item in canvas.items)
        coords = [v for _, args, _ in canvas.items for v in args
                  if isinstance(v, (int, float))]
        assert all(math.isfinite(v) for v in coords)


def test_all_poses_stay_inside_small_143_by_154_frame():
    canvas = Canvas()
    width, height = 143, 154
    renderer = CatRenderer(canvas, width=width, height=height)
    cat = brain()
    for state in CatBrain.STATES:
        cat.state = state
        renderer.draw(cat, 1.2)
        for kind, args, _kwargs in canvas.items:
            coords = args[0] if kind == "text" else args
            for index, value in enumerate(coords):
                if isinstance(value, (int, float)):
                    limit = width if index % 2 == 0 else height
                    assert -0.01 <= value <= limit + 0.01, (state, kind, coords)


def test_roll_effect_uses_local_canvas_without_replaying_sound(monkeypatch):
    canvas = Canvas()
    orchestrator = EffectOrchestrator(canvas, width=104, height=112,
                                      sound_enabled=True)
    calls = []
    monkeypatch.setattr(sounds, "play", lambda *args, **kwargs: calls.append(args))
    orchestrator.trigger_state_enter("roll", 0, 0)
    assert orchestrator.particles.particles
    assert not calls
    assert all(0 <= p.x <= 104 and 0 <= p.y <= 112
               for p in orchestrator.particles.particles)

