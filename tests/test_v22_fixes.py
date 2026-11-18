"""Hedefe yürüme, yatay gezinme, oyuncak ilgisi, pencere kilidi ve hava ilk mesajı (saf mantık)."""
import gc
import threading
import types

import pytest

import window_utils
from behavior import Bounds, CatBrain, GOAL_SPEED
from desktop_physics import DesktopPhysics
from desktop_toys import ToyBrain
from weather import WeatherWatcher, draw_weather


def _brain(**kw):
    return CatBrain(Bounds(0, 0, 2000, 800), seed=3, **kw)


def test_go_to_uses_goal_speed_and_arrives():
    b = _brain()
    b.move_to(100, 700)
    assert b.go_to(1100, 700)
    assert b._goal and b._duration >= 1000 / GOAL_SPEED
    for _ in range(int(1000 / GOAL_SPEED * 10) + 40):
        b.step(0.1)
        if b.state != "wander":
            break
    assert b.state == "sit" and abs(b.x - 1100) <= 2 and not b._goal


def test_goal_flag_cleared_by_state_change():
    b = _brain()
    b.go_to(900, b.y)
    b.command("play")
    assert not b._goal


def test_spontaneous_wander_is_horizontal_only():
    b = _brain()
    b.move_to(500, 600)
    for _ in range(40):
        b._pick_wander_target()
        assert b.target_y == b.y


def test_vertical_gap_closed_fast_without_diagonal_walk():
    b = _brain()
    b.move_to(500, 100)
    b.go_to(700, 700)
    b.step(0.1)
    assert b.y - 100 >= 39 and b.x - 500 <= GOAL_SPEED * 0.1 + 1e-6


def test_toy_brain_user_placed_goes_then_uses_and_repeats():
    t = ToyBrain()
    toys = {"post": (800, 700)}
    t.user_placed("post", 10)
    assert t.decide(11, (100, 640), True, 0, toys)["action"] == "go"
    assert t.decide(12, (100, 640), True, 0, toys) is None          # go bekleme süresi
    assert t.decide(16, (790, 640), True, 0, toys)["action"] == "scratch"
    assert t.decide(17, (790, 640), True, 0, toys) is None          # ilgi bitti
    assert t.decide(17 + t.SCRATCH_EVERY + 1, (790, 640), True, 0, toys)["action"] == "scratch"


def test_toy_brain_box_event_has_stay():
    t = ToyBrain()
    t.user_placed("box", 0)
    ev = t.decide(1, (500, 650), True, 0, {"box": (510, 700)})
    assert ev["action"] == "box" and t.BOX_STAY[0] <= ev["stay"] <= t.BOX_STAY[1]


def test_perch_locks_hwnd_and_follows_its_rect(monkeypatch):
    rects = {7: (100, 300, 700, 600)}
    monkeypatch.setattr(window_utils, "window_rect", lambda h: rects.get(h))
    monkeypatch.setattr(window_utils, "active_window_rect", lambda *a, **k: (0, 0, 50, 50))
    p = DesktopPhysics(cat_w=100, cat_h=100, bounds=(0, 0, 1920, 1080))
    assert p.perch_on_window(rects[7], cat_x=200, hwnd=7)
    p.step(0.016, 200, 200, taskbar_rect=None, has_toast=False)
    assert p.perched and p.y == 200
    rects[7] = (110, 310, 710, 610)                       # pencere taşındı: kedi izler
    p.step(0.016, p.x, p.y, taskbar_rect=None, has_toast=False)
    assert p.perched and p.y == 210 and p.x == 210
    del rects[7]                                          # pencere kapandı: düşer
    p.step(0.016, p.x, p.y, taskbar_rect=None, has_toast=False)
    assert p.falling and not p.perched and p.perch_hwnd is None


def test_perch_jump_arc_reaches_top():
    p = DesktopPhysics(cat_w=100, cat_h=100, bounds=(0, 0, 1920, 1080))
    rect = (0, 300, 800, 700)
    p.x, p.y = 100.0, 200.0                 # aynı yükseklikten: yay tepe yapar
    p.perch_on_window(rect, cat_x=300, hwnd=1, animate=True)
    peak = 1e9
    for _ in range(40):
        p.step(0.016, p.x, p.y, window_rect=rect, taskbar_rect=None, has_toast=False)
        peak = min(peak, p.y)
    assert abs(p.y - 200) < 1e-6 and abs(p.x - 300) < 1e-6 and p.perched and peak < 150


def test_active_window_rect_ignores_own_process(monkeypatch):
    if not window_utils.IS_WINDOWS:
        pytest.skip("Windows")
    monkeypatch.setattr(window_utils, "_is_own_window", lambda u, h: True)
    monkeypatch.setattr(window_utils.ctypes.windll.user32, "GetForegroundWindow", lambda: 123, raising=False)
    assert window_utils.foreground_hwnd() is None
    assert window_utils.active_window_rect() is None


def test_weather_announces_first_result_once_and_describes():
    w = WeatherWatcher(fetch=lambda c: ("clear", 18.4, "Antalya"))
    w.set_city("Antalya")
    w._refresh("Antalya")
    assert w.take_announcement() == "Antalya: 18°C, açık ☀️"
    assert w.take_announcement() is None
    w.request_announce()
    assert w.take_announcement() == "Antalya: 18°C, açık ☀️"


class _R:
    def __init__(self):
        self.calls = 0

    def _oval(self, *a, **k):
        self.calls += 1

    _line = _oval


@pytest.mark.parametrize("kind", ["clear", "cloudy", "hot", "cold", "rain"])
def test_draw_weather_draws_for_all_conditions(kind):
    r = _R()
    draw_weather(r, kind, 1.0)
    assert r.calls > 0


def test_click_pets_and_middle_click_opens_chat(monkeypatch, tmp_path):
    import cat
    from settings import Settings
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(cat.DesktopCat, "_register_hotkey", lambda self: None)
    monkeypatch.setattr(cat, "Tray", lambda **kw: types.SimpleNamespace(
        poll_show=lambda: False, poll_quit=lambda: False, close=lambda: None))
    monkeypatch.setattr(cat.Settings, "load", lambda: Settings({"sound": False, "ai_backend": "offline"}))
    gc.collect()
    app = cat.DesktopCat()
    try:
        shown = []
        app.assistant.show = lambda *a, **k: shown.append(1)
        app.drag_origin = (0, 0, 0, 0)
        app.dragged = False
        app._release(types.SimpleNamespace())
        assert not shown and app.brain.state == "sit"
        app.open_chat()
        assert shown
        assert not hasattr(app, "dev_bridge") and not hasattr(app, "rubber_duck")
    finally:
        app.close()
        gc.collect()
