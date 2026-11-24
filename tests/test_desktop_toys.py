from desktop_toys import ToyBrain, YarnPhysics

AREA = (0, 0, 1000, 700)


def _run(ball, seconds, platforms=()):
    for _ in range(int(seconds * 60)):
        ball.step(1 / 60, AREA, platforms)


def test_yarn_bounces_off_walls_and_comes_to_rest_on_floor():
    ball = YarnPhysics(900, 300)
    ball.push(1500, -300)
    _run(ball, 0.5)
    assert ball.vx < 0                          # sağ kenardan sekti
    _run(ball, 12)
    assert ball.resting and abs(ball.y + ball.r - 700) < 1e-6
    assert 0 + ball.r <= ball.x <= 1000 - ball.r


def test_yarn_lands_on_window_top_only_when_falling_onto_it():
    ball = YarnPhysics(500, 100)
    _run(ball, 3, platforms=[(300, 400, 800)])
    assert ball.resting and abs(ball.y + ball.r - 400) < 1e-6
    below = YarnPhysics(500, 600)                # pencere kenarının altında başlayan top yere düşer
    _run(below, 3, platforms=[(300, 400, 800)])
    assert abs(below.y + below.r - 700) < 1e-6


def test_toy_brain_bats_goes_drinks_and_respects_play_window():
    brain = ToyBrain()
    toys = {"yarn": (520, 700)}
    assert brain.decide(10, (100, 640), True, 0, toys) is None      # atılmadan ilgi yok
    brain.user_threw(10)
    assert brain.decide(11, (100, 640), True, 0, toys)["action"] == "go"
    bat = brain.decide(12, (500, 660), False, 0, toys)
    assert bat["action"] == "bat" and bat["vx"] > 0 and bat["vy"] < 0
    assert brain.decide(12.5, (500, 660), False, 0, toys) is None   # pati bekleme süresi
    assert brain.decide(10 + brain.PLAY_WINDOW + 1, (500, 660), True, 0, toys) is None
    bowl = {"bowl": (130, 700)}
    assert brain.decide(100, (100, 640), True, 20, bowl) is None    # tok
    assert brain.decide(100, (100, 640), True, 80, bowl)["action"] == "drink"
    assert brain.decide(101, (100, 640), True, 80, bowl) is None    # bekleme süresi


def test_hungry_cat_brain_activity_states():
    from behavior import Bounds
    from needs import HungryCatBrain

    brain = HungryCatBrain(Bounds(0, 0, 1000, 800), seed=9)
    for state in ("drink", "eat", "scratch", "jump", "box_sit", "laser_chase", "perch"):
        brain._change(state, duration=3.0)
        assert brain.state == state
        assert brain._duration == 3.0
        assert not brain._goal
        brain.command(state)
        assert brain.state == state
        assert brain.message
    # Backwards compatibility: feed keeps entering "sit"
    brain.command("feed")
    assert brain.state == "sit"


def test_perch_clamps_near_screen_top_and_preserves_mid_screen():
    from desktop_physics import DesktopPhysics

    # 13" MacBook Air visibleFrame below menu bar (top=37)
    p = DesktopPhysics(cat_w=143, cat_h=154, bounds=(0, 37, 1440, 860))
    maximized = (0, 37, 1440, 860)
    assert p.perch_on_window(maximized, cat_x=500, hwnd=99, animate=False)
    expected_min_y = 37.0 - 154.0 * 0.08
    assert p.y >= expected_min_y - 1e-6
    assert p.y > 0  # never launched off-screen at -117

    # Animated jump to menu-bar window also lands visibly at clamped y
    p2 = DesktopPhysics(cat_w=143, cat_h=154, bounds=(0, 37, 1440, 860))
    p2.x, p2.y = 400.0, 680.0
    assert p2.perch_on_window(maximized, cat_x=520, hwnd=99, animate=True)
    assert p2._jump is not None
    for _ in range(35):
        p2.step(0.016, p2.x, p2.y, window_rect=maximized, taskbar_rect=None, has_toast=False)
        assert p2.y >= 37.0 - 154.0 * 0.15 - 1e-6
    assert p2._jump is None and p2.perched
    assert abs(p2.y - expected_min_y) < 1e-6

    # Mid-screen window preserves exact rect[1] - cat_h
    mid = (200, 350, 900, 750)
    assert p2.perch_on_window(mid, cat_x=300, hwnd=100, animate=False)
    assert abs(p2.y - (350.0 - 154.0)) < 1e-6


def _max_rgb_channel(color):
    if not color or not color.startswith("#") or len(color) != 7:
        return 255
    return max(int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))


def test_toy_windows_and_laser_dot_draw_without_black_key_colors():
    import tkinter as tk
    from desktop_toys import ToyBox, _LaserDotWindow

    root = tk.Tk()
    root.withdraw()
    box = ToyBox(root)
    dot = _LaserDotWindow(root)
    try:
        for kind in ("yarn", "bowl", "box", "post"):
            assert box.toggle(kind, 300, 400) is True
            toy = box.toys[kind]
            items = toy.canvas.find_all()
            assert len(items) >= 5, f"{kind} should have detailed vector artwork"
            for item in items:
                for opt in ("fill", "outline"):
                    try:
                        col = toy.canvas.itemcget(item, opt)
                    except tk.TclError:
                        continue
                    if col and col.startswith("#"):
                        assert _max_rgb_channel(col) >= 9, f"{kind} used forbidden dark color {col}"

        # Box hides while cat is inside and re-shows on exit_box()
        box._update_box(100.0, {"action": "box", "stay": 25.0})
        assert box.box_until == 125.0
        assert box._box_hidden_for_cat is True
        assert box.toys["box"].win.wm_state() == "withdrawn"
        box.exit_box()
        assert box.box_until == 0.0
        assert box._box_hidden_for_cat is False

        # Laser dot lifecycle & colors
        dot.show(420, 310)
        assert dot.visible is True
        assert dot.x == 420.0 - 13.0 and dot.y == 310.0 - 13.0
        dot.update(500, 360, 0.016)
        assert dot.x == 500.0 - 13.0 and dot.y == 360.0 - 13.0
        for item in dot.canvas.find_all():
            for opt in ("fill", "outline"):
                try:
                    col = dot.canvas.itemcget(item, opt)
                except tk.TclError:
                    continue
                if col and col.startswith("#"):
                    assert _max_rgb_channel(col) >= 9
        dot.hide()
        assert dot.visible is False
    finally:
        dot.destroy()
        box.close()
        root.destroy()


def test_desktop_cat_toy_actions_and_laser_chase_end_to_end(tmp_path, monkeypatch):
    import threading
    import tkinter as tk
    import types
    import cat
    import window_utils

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(cat, "Tray", lambda tooltip="": types.SimpleNamespace(
        available=False, poll_show=lambda: False, poll_quit=lambda: False, close=lambda: None,
    ))

    class FakeShortcut:
        def __init__(self):
            self.requested = threading.Event()
            self.boss_requested = threading.Event()
            self.registered = True

        def close(self):
            pass

    monkeypatch.setattr(cat, "PanelShortcut", FakeShortcut)
    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel(root)
    win.withdraw()
    app = cat.DesktopCat(root=win)
    try:
        # 1. Drink from bowl -> transitions to "drink" & reduces hunger
        app.toggle_toy("bowl")
        bx, bb = app.toybox.anchors()["bowl"]
        app.brain.x, app.brain.y = bx - app.w / 2 - 20, bb - app.h * 0.85
        app.brain.hunger = 80.0
        app.toybox.brain.user_placed("bowl", 10.0)
        app._step_toys(0.016, 11.0)
        assert app.brain.state == "drink"
        assert app.brain.hunger < 80.0
        app.toggle_toy("bowl")

        # 2. Scratch post -> transitions to "scratch"
        app.toggle_toy("post")
        px, pb = app.toybox.anchors()["post"]
        app.brain.x, app.brain.y = px - app.w / 2 - 20, pb - app.h * 0.85
        app.brain.rest()
        app.toybox.brain.user_placed("post", 20.0)
        app._step_toys(0.016, 21.0)
        assert app.brain.state == "scratch"
        app.toggle_toy("post")

        # 3. Bat yarn -> transitions to "play" with hide_internal_ball=True; normal play clears it
        app.toggle_toy("yarn")
        yx, yb = app.toybox.anchors()["yarn"]
        app.brain.x, app.brain.y = yx - app.w / 2 - 10, yb - app.h * 0.85
        app.brain.rest()
        app.toybox.brain.user_threw(30.0)
        app._step_toys(0.016, 31.0)
        assert app.brain.state == "play"
        assert app.brain.hide_internal_ball is True
        app.command("play")
        assert app.brain.hide_internal_ball is False
        app.toggle_toy("yarn")

        # 4. Box sit -> hides static desktop box, early command immediately re-shows it
        app.toggle_toy("box")
        kx, kb = app.toybox.anchors()["box"]
        app.brain.x, app.brain.y = kx - app.w / 2, kb - app.h * 0.85
        app.brain.rest()
        app.toybox.brain.user_placed("box", 40.0)
        app._step_toys(0.016, 41.0)
        assert app.brain.state == "box_sit"
        assert app.toybox._box_hidden_for_cat is True
        app.command("wander")
        assert app.toybox._box_hidden_for_cat is False
        assert app.toybox.box_until == 0.0
        app.toggle_toy("box")

        # 5. Laser chase -> laser_chase while far, pounce play (hide_internal_ball) when within 28px, clean off
        assert app.toggle_laser() is True
        assert app.brain.state == "laser_chase"
        assert app._laser_dot is not None and app._laser_dot.visible is True
        far_ptr = (app.brain.x + app.w * 0.5 + 300, app.brain.y + app.h * 0.5)
        app._step_v2_subsystems(0.016, far_ptr, 50.0)
        assert app.brain.state == "laser_chase"
        assert app.brain.facing == 1
        near_ptr = (app.brain.x + app.w * 0.5 + 5, app.brain.y + app.h * 0.5)
        app._step_v2_subsystems(0.016, near_ptr, 51.0)
        assert app.brain.state == "play"
        assert app.brain.hide_internal_ball is True
        assert app.toggle_laser() is False
        assert app.brain.state == "sit"
        assert app.brain.hide_internal_ball is False
        assert app._laser_dot.visible is False

        # 6. Perch on menu-bar window -> jump -> perch at clamped visible y
        area = app.areas[app.area_index]
        top_rect = (area.left, area.top, area.right, area.bottom)
        monkeypatch.setattr(window_utils, "foreground_hwnd", lambda ignore_hwnds=None: 777)
        monkeypatch.setattr(window_utils, "window_rect", lambda hwnd: top_rect if hwnd == 777 else None)
        assert app.perch_active_window() is True
        assert app.brain.state == "jump"
        for i in range(35):
            app._step_v2_subsystems(0.016, (500, 500), 60.0 + i * 0.016)
        assert app.physics.perched is True
        assert app.brain.state == "perch"
        assert app.brain.y >= area.top - app.h * 0.08 - 1e-6
    finally:
        if not app.closed:
            app.close()
        root.destroy()
