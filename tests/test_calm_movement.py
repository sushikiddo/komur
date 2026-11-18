import math

from behavior import Bounds
from needs import HungryCatBrain

BOUNDS = Bounds(0, 0, 1700, 800)


def _run(activity, seed, minutes=30):
    b = HungryCatBrain(BOUNDS, width=130, height=140, seed=seed, activity=activity)
    px, py, dt = b.x, b.y, 1 / 30
    moving = dist = far = 0.0
    for _ in range(int(minutes * 60 / dt)):
        b.step(dt)
        d = math.hypot(b.x - px, b.y - py)
        px, py = b.x, b.y
        dist += d
        moving += dt if d > 0.01 else 0
        far = max(far, math.hypot(b.x - b.home_x, b.y - b.home_y))
    return moving / (minutes * 60), dist / minutes, far


def test_calm_is_default_and_barely_moves():
    assert HungryCatBrain(BOUNDS, seed=0).activity == "sakin"
    for seed in range(3):
        share, per_min, _ = _run("sakin", seed)
        assert share <= 0.06
        assert per_min <= 150


def test_calm_wander_stays_near_home():
    for seed in range(3):
        assert _run("sakin", seed)[2] <= 251


def test_drag_drop_sets_new_home():
    b = HungryCatBrain(BOUNDS, width=130, height=140, seed=1)
    b.move_to(100, 600)
    assert (b.home_x, b.home_y) == (100, 600)


def test_explicit_wander_roams_whole_screen_at_old_speed():
    b = HungryCatBrain(BOUNDS, width=130, height=140, seed=2)
    b.move_to(100, 600)
    b.command("wander")
    assert b._free_roam
    b.target_x = b.x + 500   # uzak yatay hedef: tam hız ölçülür
    x0, y0 = b.x, b.y
    b.step(0.1)
    assert b.y == y0          # serbest gezinme de yalnız yatay
    moved = math.hypot(b.x - x0, b.y - y0)
    assert moved == 0 or abs(moved - 5.2) < 0.01  # 52 px/s, not calm 30 px/s


def test_normal_profile_moves_more_than_calm():
    assert _run("normal", 0, minutes=10)[0] > _run("sakin", 0, minutes=10)[0] * 5


def test_unsolicited_speech_has_one_global_gap():
    from types import SimpleNamespace
    import cat
    said = []
    fake = SimpleNamespace(UNSOLICITED_GAP=900.0, say=lambda text, seconds: said.append(text))
    speak = lambda text: cat.DesktopCat.say_unsolicited(fake, text, 5)
    assert speak("video") is True
    assert speak("alışkanlık") is False      # farklı kaynak da aynı sınıra takılır
    assert said == ["video"]
