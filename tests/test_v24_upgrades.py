"""Tests for v2.4 upgrades: new costumes, peek pose, screen-space eye tracking, social chase, icons & tray."""
from pathlib import Path
import types

import companion
from costumes import COSTUME_LABELS, EXTRA_COSTUMES
from procedural_anim import LayeredCostumes
from renderer import CatRenderer
import skins
from tray import Tray


class _MockCanvas:
    def __init__(self):
        self.items = []

    def delete(self, _tag):
        self.items.clear()

    def create_polygon(self, *coords, **kw):
        self.items.append(("poly", coords, kw))
        return len(self.items)

    def create_oval(self, *coords, **kw):
        self.items.append(("oval", coords, kw))
        return len(self.items)

    def create_line(self, *coords, **kw):
        self.items.append(("line", coords, kw))
        return len(self.items)

    def create_rectangle(self, *coords, **kw):
        self.items.append(("rect", coords, kw))
        return len(self.items)

    def create_text(self, *args, **kw):
        self.items.append(("text", args, kw))
        return len(self.items)


def test_all_19_costumes_render_in_sit_and_walk():
    assert len(EXTRA_COSTUMES) == 10
    for acc in EXTRA_COSTUMES:
        assert acc in LayeredCostumes.ALL_COSTUMES
        assert acc in COSTUME_LABELS
    cv = _MockCanvas()
    r = CatRenderer(cv)
    for acc in LayeredCostumes.ALL_COSTUMES:
        for state in ("sit", "wander"):
            brain = types.SimpleNamespace(state=state, facing=1, elapsed=0.5)
            r.draw(brain, 0.5, accessory=acc)
            assert r.item_count > 10, f"Costume {acc!r} failed in state {state!r}"


def test_peek_pose_renders_cleanly():
    cv = _MockCanvas()
    r = CatRenderer(cv)
    brain = types.SimpleNamespace(state="peek", facing=1, elapsed=1.0)
    r.draw(brain, 1.0)
    assert r.item_count > 15


def test_screen_space_cursor_gaze_tracks_left_and_right():
    cv = _MockCanvas()
    r = CatRenderer(cv)
    # Cat sits at screen x=500, y=500; pointer to the LEFT (x=200) -> negative gaze_x
    brain_left = types.SimpleNamespace(
        state="sit", facing=1, x=500.0, y=500.0, pointer_xy=(200.0, 560.0),
    )
    r.draw(brain_left, 0.1)
    assert r._gaze_override is not None
    assert r._gaze_override[0] < 0.0

    # Pointer to the RIGHT (x=900) -> positive gaze_x
    r2 = CatRenderer(_MockCanvas())
    brain_right = types.SimpleNamespace(
        state="sit", facing=1, x=500.0, y=500.0, pointer_xy=(900.0, 560.0),
    )
    r2.draw(brain_right, 0.1)
    assert r2._gaze_override is not None
    assert r2._gaze_override[0] > 0.0

    # Facing left (flip=True) with pointer to the LEFT -> flipped to +x in local space
    r3 = CatRenderer(_MockCanvas())
    brain_flip = types.SimpleNamespace(
        state="sit", facing=-1, x=500.0, y=500.0, pointer_xy=(200.0, 560.0),
    )
    r3.draw(brain_flip, 0.1)
    assert r3._gaze_override is not None
    assert r3._gaze_override[0] > 0.0


def test_companion_play_chase_social_interaction():
    a = types.SimpleNamespace(
        brain=types.SimpleNamespace(x=100.0, y=200.0, width=140, height=150, state="sit", facing=1, energy=90.0),
        w=140, h=150,
    )
    b = types.SimpleNamespace(
        brain=types.SimpleNamespace(x=140.0, y=200.0, width=140, height=150, state="sit", facing=-1, energy=90.0),
        w=140, h=150,
    )
    mode = companion.apply_social_interaction(a, b, dt=0.016, interaction="play_chase")
    assert mode == "play_chase"
    assert a.brain.state == "play"
    assert b.brain.state == "wander"
    assert a.brain.emote == "!"


def test_tray_action_queue_and_icon_assets():
    tray = Tray.__new__(Tray)
    import queue
    tray._actions = queue.SimpleQueue()
    assert tray.poll_action() is None
    tray._actions.put("feed")
    assert tray.poll_action() == "feed"
    assert tray.poll_action() is None

    assets = Path(__file__).resolve().parents[1] / "assets"
    for fname in ("komur.icns", "komur.ico", "komur_icon_64.png"):
        p = assets / fname
        assert p.is_file() and p.stat().st_size > 1000, f"Missing or empty icon asset: {fname}"


def test_all_7_skins_render_in_walk_and_sit():
    cv = _MockCanvas()
    for skin_key in skins.skin_order():
        r = skins.apply_skin(CatRenderer(cv), skin_key)
        for state in ("sit", "wander", "peek"):
            brain = types.SimpleNamespace(state=state, facing=1, elapsed=0.4)
            r.draw(brain, 0.4)
            assert r.item_count > 10


def test_adaptive_battery_power_intervals():
    from power import PowerMonitor, PowerStatus, frame_interval_ms

    ac = PowerStatus(on_battery=False, low_power_mode=False, percent=100)
    batt = PowerStatus(on_battery=True, low_power_mode=False, percent=70)
    low = PowerStatus(on_battery=True, low_power_mode=True, percent=15)

    # Hidden & paused drop to ultra-low poll rate regardless of power source
    assert frame_interval_ms("wander", status=ac, hidden=True) >= 200
    assert frame_interval_ms("sit", status=ac, paused=True) >= 200

    # Sleep is much slower than active walk, and battery is slower than AC
    assert frame_interval_ms("sleep", status=ac) > frame_interval_ms("sit", status=ac)
    assert frame_interval_ms("sleep", status=batt) > frame_interval_ms("sleep", status=ac)
    assert frame_interval_ms("sleep", status=low) >= frame_interval_ms("sleep", status=batt)

    # Walk stays nimble & fluid even on battery (>= 24 FPS)
    assert frame_interval_ms("wander", status=ac) <= 25
    assert frame_interval_ms("wander", status=batt) <= 35
    assert frame_interval_ms("wander", status=low) <= 45

    # Sit uses significantly fewer FPS on battery than AC
    assert frame_interval_ms("sit", status=batt) > frame_interval_ms("sit", status=ac)
    # Pointer near cat boosts idle responsiveness
    assert frame_interval_ms("sit", status=batt, pointer_active=True) < frame_interval_ms("sit", status=batt)

    # PowerMonitor returns cached status non-blockingly
    mon = PowerMonitor(reader=lambda: batt)
    st = mon.poll()
    assert isinstance(st, PowerStatus)


def test_four_slot_wardrobe_combos_and_render():
    from costumes import (
        normalize_accessories,
        ordered_active_items,
        summary_label,
        toggle_slot_item,
    )

    slots = {}
    slots = toggle_slot_item(slots, "star_sticker")
    slots = toggle_slot_item(slots, "bell_collar")
    slots = toggle_slot_item(slots, "sunglasses")
    slots = toggle_slot_item(slots, "cozy_sweater")
    assert slots == {
        "head": "star_sticker",
        "neck": "bell_collar",
        "eyes": "sunglasses",
        "body": "cozy_sweater",
    }
    # Layer order must be back-to-front: body -> neck -> eyes -> head
    assert ordered_active_items(slots) == [
        "cozy_sweater", "bell_collar", "sunglasses", "star_sticker",
    ]
    assert "(4)" in summary_label(slots)

    # Toggling the same item removes only that slot; swapping keeps other slots
    slots = toggle_slot_item(slots, "sunglasses")
    assert "eyes" not in slots and len(slots) == 3
    slots = toggle_slot_item(slots, "crown")
    assert slots["head"] == "crown" and slots["neck"] == "bell_collar"

    # Legacy single string normalizes cleanly
    assert normalize_accessories("glasses") == {"eyes": "glasses"}

    # Rendering a full 4-slot combo on CatRenderer succeeds without error
    from behavior import Bounds, CatBrain
    canvas = _MockCanvas()
    renderer = CatRenderer(canvas)
    renderer.accessory = slots
    brain = CatBrain(Bounds(0, 0, 1200, 800))
    brain.state = "sit"
    renderer.draw(brain, 1.0)
    assert len(canvas.items) > 40


def test_notch_peek_pose_renders_cleanly():
    from behavior import Bounds, CatBrain
    canvas = _MockCanvas()
    renderer = CatRenderer(canvas)
    brain = CatBrain(Bounds(0, 0, 1200, 800))
    brain.state = "perch"
    brain.visual_pose = "notch_peek"
    brain.visual_pose_duration = 20.0
    brain.elapsed = 1.0
    renderer.draw(brain, 1.5)
    assert len(canvas.items) > 15


def test_fullscreen_video_keeps_cat_sleeping_in_corner():
    from types import SimpleNamespace
    from behavior import Bounds, CatBrain
    import cat as cat_mod

    brain = CatBrain(Bounds(0, 0, 1200, 800))
    brain.x, brain.y = 18.0, 800 - 280 - 10  # already near bottom-left corner
    brain.state = "sit"
    ar = SimpleNamespace(fullscreen_video=True, is_fullscreen=True, current="video")
    topmost_calls = []

    app = cat_mod.DesktopCat.__new__(cat_mod.DesktopCat)
    app.brain = brain
    app.areas = [Bounds(0, 0, 1200, 800)]
    app.area_index = 0
    app.w, app.h = 260, 280
    app.physics = None
    app.root = None
    app.activity_reactions = ar
    app._manual_reaction_until = 0.0
    app._video_corner_sleep = False
    app._notch_perched = False

    orig_topmost = cat_mod.window_utils.ensure_topmost_now
    cat_mod.window_utils.ensure_topmost_now = lambda w=None: topmost_calls.append(True)
    try:
        app._maintain_video_corner_sleep(10.0)
        assert app._video_corner_sleep is True
        assert brain.state == "sleep"
        assert len(topmost_calls) == 1

        # Video ends -> wakes gently with stretch
        ar.fullscreen_video = False
        ar.is_fullscreen = False
        ar.current = "none"
        app._maintain_video_corner_sleep(20.0)
        assert app._video_corner_sleep is False
        assert brain.state == "stretch"
    finally:
        cat_mod.window_utils.ensure_topmost_now = orig_topmost


def test_tray_focus_label_and_health_default():
    import settings
    from tray import Tray

    assert settings.DEFAULTS["health_reminders"] is True
    assert settings.DEFAULTS["accessories"] == {}
    t = Tray.__new__(Tray)
    t._focus_label = "🍅 Odak Başlat (25 dk)"
    t._tk_menu = None
    t._tk_focus_index = None
    t.update_focus_label("🍅 Odak: 24:59 (Durdur)")
    assert t._focus_label == "🍅 Odak: 24:59 (Durdur)"


def test_mac_nonactivating_panel_never_steals_focus():
    import sys
    import tkinter as tk
    import window_utils

    if sys.platform != "darwin":
        return
    host = tk.Tk()
    host.withdraw()
    try:
        panel = window_utils.create_nonactivating_panel(host, name="test_nonact_panel")
        panel.title("Kömür — Test Panel")
        window_utils.make_transparent(panel)
        panel.geometry("80x80+100+100")
        panel.deiconify()
        panel.update()
        window_utils._mac_apply_window_chrome(order_front=False)
        assert window_utils.is_nonactivating_panel(panel) is True
        o = window_utils._objc_runtime()
        w = window_utils._mac_find_nswindow(panel)
        assert w is not None and window_utils._is_tk_nspanel(o, w)
        assert o.get_ulong(w, o.sel("styleMask")) == window_utils._NS_NONACTIVATING_PANEL_MASK
        assert o.get_bool(w, o.sel("isFloatingPanel")) is True
        assert o.get_bool(w, o.sel("canBecomeKeyWindow")) is True
        assert o.get_bool(w, o.sel("becomesKeyOnlyIfNeeded")) is False
        cv = o.send(w, o.sel("contentView"))
        assert o.get_bool_obj(cv, o.sel("acceptsFirstMouse:"), None) is True
        assert o.get_long(w, o.sel("level")) == window_utils._NS_FLOATING_LEVEL
        assert o.get_ulong(w, o.sel("collectionBehavior")) == window_utils._NS_COLLECTION_ALL_SPACES
        panel.destroy()
    finally:
        host.destroy()
