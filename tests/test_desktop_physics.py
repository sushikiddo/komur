import math
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import desktop_physics
import window_utils
from behavior import Bounds
from desktop_physics import DesktopPhysics, desktop_icon_grid
from needs import HungryCatBrain


class WindowUtilsFallbackTests(unittest.TestCase):
    def test_non_windows_fallbacks(self):
        with mock.patch.object(window_utils, "IS_WINDOWS", False):
            self.assertIsNone(window_utils.active_window_rect())
            self.assertIsNone(window_utils.taskbar_rect())
            self.assertFalse(window_utils.has_toast_notification())

    def test_windows_error_fallbacks(self):
        fake_user32 = mock.Mock()
        fake_user32.GetForegroundWindow.side_effect = OSError("win32 failure")
        fake_user32.FindWindowW.side_effect = OSError("win32 failure")
        fake_windll = mock.Mock(user32=fake_user32)
        with mock.patch.object(window_utils, "IS_WINDOWS", True), \
             mock.patch.object(window_utils.ctypes, "windll", fake_windll, create=True):
            self.assertIsNone(window_utils.active_window_rect())
            self.assertIsNone(window_utils.taskbar_rect())
            self.assertFalse(window_utils.has_toast_notification())


class DesktopPhysicsTests(unittest.TestCase):
    def setUp(self):
        self.bounds = (0, 0, 1920, 1080)
        self.physics = DesktopPhysics(cat_w=260, cat_h=280, bounds=self.bounds)

    def test_window_perch_follow_and_fast_shake_fall(self):
        rect = (300, 400, 1000, 900)
        ok = self.physics.perch_on_window(rect, cat_x=450)
        self.assertTrue(ok)
        self.assertTrue(self.physics.perched)
        self.assertFalse(self.physics.falling)
        self.assertEqual(self.physics.surface, "window_top")
        self.assertEqual(self.physics.y, 400 - 280)

        # Gentle move stays perched and shifts cat by (dx, dy)
        moved_rect = (320, 410, 1020, 910)
        x, y = self.physics.step(
            0.1, window_rect=moved_rect, taskbar_rect=None, has_toast=False
        )
        self.assertTrue(self.physics.perched)
        self.assertAlmostEqual(x, 470.0)
        self.assertAlmostEqual(y, 410.0 - 280.0)

        # Fast shake: hypot(200, 0) / 0.1 = 2000 > 900 triggers fall
        shaken_rect = (520, 410, 1220, 910)
        self.physics.step(
            0.1, window_rect=shaken_rect, taskbar_rect=None, has_toast=False
        )
        self.assertFalse(self.physics.perched)
        self.assertTrue(self.physics.falling)
        self.assertTrue(self.physics.startled)

        # Gravity accelerates down until landing on ground
        self.assertAlmostEqual(self.physics.vy, 1800.0 * 0.1)
        vy_after_shake = self.physics.vy
        self.physics.step(
            0.05, window_rect=None, taskbar_rect=None, has_toast=False
        )
        self.assertGreater(self.physics.vy, vy_after_shake)
        for _ in range(30):
            self.physics.step(
                0.05, window_rect=None, taskbar_rect=None, has_toast=False
            )
            if not self.physics.falling:
                break
        self.assertFalse(self.physics.falling)
        self.assertEqual(self.physics.surface, "ground")
        self.assertAlmostEqual(self.physics.y, 1080 - 280)
        self.assertEqual(self.physics.vy, 0.0)

    def test_window_close_triggers_fall(self):
        self.physics.perch_on_window((200, 350, 800, 750), cat_x=300)
        self.physics.step(0.05, window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertFalse(self.physics.perched)
        self.assertTrue(self.physics.falling)
        self.assertGreater(self.physics.vy, 0.0)

    def test_desktop_icon_grid_peek_sit_and_slap(self):
        with mock.patch.object(desktop_physics, "_probe_syslistview_icon_count", return_value=None):
            icons = desktop_icon_grid(self.bounds)
        self.assertGreaterEqual(len(icons), 4)
        self.assertEqual((icons[0].w, icons[0].h), (80, 90))

        slot = self.physics.peek_at_icon(0, icons=icons)
        self.assertIsNotNone(slot)
        self.assertTrue(self.physics.icon_peek)

        self.physics.sit_on_icon(1, icons=icons)
        self.assertEqual(self.physics.surface, "icon")
        self.assertFalse(self.physics.icon_peek)
        self.assertAlmostEqual(self.physics.y, icons[1].y - 280)

        slap_state = self.physics.slap_icon(1, icons=icons)
        self.assertTrue(self.physics.icon_slap)
        self.assertIn(1, self.physics.slapped_icons)
        initial_dy = slap_state["dy"]
        self.physics.step(0.2, window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertGreater(self.physics.slapped_icons[1]["dy"], initial_dy)

        # Eventually recovers after timer expires
        for _ in range(30):
            self.physics.step(0.1, window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertFalse(self.physics.icon_slap)
        self.assertEqual(self.physics.slapped_icons, {})

    def test_taskbar_walk_and_toast_curiosity(self):
        tb = (0, 1032, 1920, 1080)
        ok = self.physics.walk_on_taskbar(tb, cat_x=200)
        self.assertTrue(ok)
        self.assertEqual(self.physics.surface, "taskbar")
        self.assertAlmostEqual(self.physics.y, 1032 - 280)

        start_x = self.physics.x
        self.physics.step(0.5, window_rect=None, taskbar_rect=tb, has_toast=True)
        self.assertTrue(self.physics.toast_curious)
        self.assertGreater(self.physics.x, start_x)
        self.assertEqual(self.physics.surface, "taskbar")

        self.physics.step(0.1, window_rect=None, taskbar_rect=tb, has_toast=False)
        self.assertFalse(self.physics.toast_curious)

    def test_cursor_nap_and_startle(self):
        ptr = (900, 500)
        # Initialize pointer tracking
        self.physics.step(0.1, pointer=ptr, window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertFalse(self.physics.cursor_nap)

        # Hold stationary for 120.0s
        self.physics.step(60.0, pointer=ptr, window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertFalse(self.physics.cursor_nap)
        self.physics.step(60.0, pointer=ptr, window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertTrue(self.physics.cursor_nap)

        # Move cursor -> startled
        self.physics.step(0.1, pointer=(980, 500), window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertFalse(self.physics.cursor_nap)
        self.assertTrue(self.physics.startled)

    def test_props_box_bed_and_laser(self):
        with self.assertRaises(ValueError):
            self.physics.spawn_prop("invalid", 10, 10)

        box = self.physics.spawn_prop("box", 400, 700)
        self.physics.x, self.physics.y = 350.0, 620.0
        self.physics.step(0.1, window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertTrue(self.physics.in_box)
        self.assertEqual(self.physics.surface, "box")
        self.assertEqual(self.physics.active_prop, box)

        self.physics.clear_props("box")
        bed = self.physics.spawn_prop("bed", 500, 720)
        self.physics.x, self.physics.y = 450.0, 630.0
        self.physics.step(0.1, window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertTrue(self.physics.on_bed)
        self.assertEqual(self.physics.surface, "bed")
        self.assertEqual(self.physics.active_prop, bed)

        self.physics.spawn_prop("laser", 1400, 300)
        prev_dist = math.hypot(1400 - (self.physics.x + 130), 300 - (self.physics.y + 140))
        self.physics.step(0.2, pointer=(1400, 300), window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertTrue(self.physics.chasing_laser)
        new_dist = math.hypot(1400 - (self.physics.x + 130), 300 - (self.physics.y + 140))
        self.assertLess(new_dist, prev_dist)

    def test_paw_trails_fade_over_two_seconds(self):
        self.physics.emit_paw_trail(100, 200, facing=-1)
        self.assertEqual(len(self.physics.paw_trails), 1)
        self.assertEqual(
            set(self.physics.paw_trails[0].keys()),
            {"x", "y", "alpha", "facing"},
        )
        self.assertEqual(self.physics.paw_trails[0]["facing"], -1)

        self.physics.step(1.0, window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertEqual(len(self.physics.paw_trails), 1)
        self.assertAlmostEqual(self.physics.paw_trails[0]["alpha"], 0.5, places=4)

        self.physics.step(1.0, window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertEqual(len(self.physics.paw_trails), 0)

        # Moving emits new trails automatically
        self.physics.spawn_prop("laser", 1000, 500)
        self.physics.step(0.2, pointer=(1000, 500), window_rect=None, taskbar_rect=None, has_toast=False)
        self.assertGreaterEqual(len(self.physics.paw_trails), 1)


class NeedsNewStatesTests(unittest.TestCase):
    def test_hungry_cat_brain_supports_new_desktop_states(self):
        brain = HungryCatBrain(Bounds(0, 0, 1000, 800), seed=42)
        new_states = (
            "perch",
            "cursor_nap",
            "icon_peek",
            "icon_slap",
            "box_sit",
            "laser_chase",
            "thermal_bask",
            "startle",
        )
        for state in new_states:
            brain.command(state)
            self.assertEqual(brain.state, state)
            self.assertTrue(brain.message)
            brain._change(state, duration=2.0)
            self.assertEqual(brain.state, state)
            self.assertAlmostEqual(brain._duration, 2.0)

        # Existing commands remain intact
        brain.command("knead")
        self.assertEqual(brain.state, "knead")
        brain.command("feed")
        self.assertEqual(brain.state, "sit")


if __name__ == "__main__":
    unittest.main()
