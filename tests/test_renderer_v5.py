"""v5 renderer additions: accessories, time of day, popcorn tub."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from renderer import CatRenderer


class RecCanvas:
    def __init__(self):
        self.calls = []

    def delete(self, *a):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("create_"):
            def rec(*a, **kw):
                self.calls.append((name, a, tuple(sorted(kw.items()))))
                return len(self.calls)
            return rec
        raise AttributeError(name)

    def bbox(self, *a):
        return (0, 0, 10, 10)

    def tag_lower(self, *a):
        pass


STATES = ("sit", "wander", "play", "sleep", "stretch", "hiss", "roll", "yawn", "groom")


def frame(state="sit", t=1.0, **kw):
    c = RecCanvas()
    r = CatRenderer(c)
    brain = SimpleNamespace(state=state, facing=1, low_light=False,
                            activity_reaction=kw.pop("reaction", "none"))
    r.draw(brain, t, **kw)
    return c.calls, r


@pytest.mark.parametrize("state", STATES)
def test_defaults_unchanged_by_new_params(state):
    base, _ = frame(state)
    explicit, _ = frame(state, accessory=None, time_of_day="day")
    assert base == explicit


@pytest.mark.parametrize("acc", ["bow", "scarf", "hat", "glasses"])
@pytest.mark.parametrize("state", STATES)
def test_accessory_adds_items_in_every_pose(acc, state):
    base, _ = frame(state)
    with_acc, r = frame(state, accessory=acc)
    assert len(with_acc) > len(base)
    assert r.accessory is None  # per-frame override restored


def test_accessory_attribute_and_unknown_ignored():
    c = RecCanvas()
    r = CatRenderer(c)
    brain = SimpleNamespace(state="sit", facing=1)
    r.draw(brain, 1.0)
    n = len(c.calls)
    r.accessory = "bow"
    r.draw(brain, 1.0)
    assert len(c.calls) > n
    r.accessory = "nonsense"
    r.draw(brain, 1.0)
    assert len(c.calls) == n


def test_night_tints_and_restores_palette():
    day, _ = frame("sit")
    night, r = frame("sit", time_of_day="night")
    assert day != night
    assert len(day) == len(night)
    assert "FUR" not in r.__dict__ and "WHITE" not in r.__dict__
    assert r.WHITE == CatRenderer.WHITE


def test_evening_differs_from_day():
    assert frame("sit")[0] != frame("sit", time_of_day="evening")[0]


def test_popcorn_visible_and_paws_on_rim():
    # Video reaction uses a calm realistic watching posture (no cartoon popcorn bucket).
    base, _ = frame("sit", reaction="none")
    watch, _ = frame("sit", reaction="video")
    assert watch != base
    flat = repr(watch)
    assert CatRenderer.CORN_BUCKET not in flat and CatRenderer.CORN_STRIPE not in flat


def test_dance_tilts_head_only_for_music():
    a, _ = frame("sit", t=0.3, reaction="none")
    b, _ = frame("sit", t=0.3, reaction="music")
    assert a != b
