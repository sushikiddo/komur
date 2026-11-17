"""Tests for procedural_anim, renderer integration, and companion sociality."""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from companion import (
    SOCIAL_DISTANCE,
    apply_social_interaction,
    cat_distance,
)
from procedural_anim import (
    AnimeEmotes,
    EarSpring,
    GazeController,
    GrowthStage,
    LayeredCostumes,
    PawPrintTrail,
    RetroPixelFilter,
    SpringChain2D,
    draw_cardboard_box,
    draw_cat_bed,
    draw_laser_dot,
    draw_task_fish,
)
from renderer import CatRenderer


class FakeCanvas:
    """Minimal headless Tkinter Canvas double for unit tests."""

    def __init__(self):
        self._next_id = 1
        self.items: dict[int, dict] = {}

    def _create(self, kind: str, *coords, **kwargs) -> int:
        item_id = self._next_id
        self._next_id += 1
        tags = kwargs.get("tags", ())
        if isinstance(tags, str):
            tags = (tags,)
        else:
            tags = tuple(tags)
        self.items[item_id] = {
            "type": kind,
            "coords": [float(c) for c in coords],
            "options": dict(kwargs),
            "tags": tags,
        }
        return item_id

    def create_oval(self, *coords, **kwargs):
        return self._create("oval", *coords, **kwargs)

    def create_polygon(self, *coords, **kwargs):
        return self._create("polygon", *coords, **kwargs)

    def create_line(self, *coords, **kwargs):
        return self._create("line", *coords, **kwargs)

    def create_rectangle(self, *coords, **kwargs):
        return self._create("rectangle", *coords, **kwargs)

    def create_text(self, *coords, **kwargs):
        if len(coords) == 1 and isinstance(coords[0], (tuple, list)):
            coords = tuple(coords[0])
        return self._create("text", *coords, **kwargs)

    def delete(self, tag_or_id):
        if tag_or_id == "all":
            self.items.clear()
            return
        to_del = [
            iid for iid, data in self.items.items()
            if iid == tag_or_id or tag_or_id in data["tags"]
        ]
        for iid in to_del:
            del self.items[iid]

    def find_all(self):
        return tuple(self.items.keys())

    def find_withtag(self, tag):
        return tuple(iid for iid, data in self.items.items() if tag in data["tags"])

    def coords(self, item_id, *new_coords):
        if not new_coords:
            return list(self.items[item_id]["coords"])
        self.items[item_id]["coords"] = [float(c) for c in new_coords]
        return None

    def type(self, item_id):
        return self.items[item_id]["type"]

    def itemcget(self, item_id, option):
        return self.items[item_id]["options"].get(option, "")

    def itemconfigure(self, item_id, **kwargs):
        self.items[item_id]["options"].update(kwargs)

    def bbox(self, item_id):
        c = self.items[item_id]["coords"]
        return (c[0] - 10, c[1] - 6, c[0] + 10, c[1] + 6)

    def tag_lower(self, *_args):
        pass


class TestSpringPhysics(unittest.TestCase):
    def test_spring_chain_has_five_joints_and_reacts_to_inertia(self):
        chain = SpringChain2D(num_joints=5)
        pts0 = chain.reset((100.0, 200.0))
        self.assertEqual(len(pts0), 5)
        tip_rest = pts0[-1]

        # Sudden rightward acceleration should whip the tail tip backward (left)
        pts_accel = chain.update(0.02, (104.0, 200.0), vel_xy=(400.0, 0.0))
        self.assertEqual(len(pts_accel), 5)
        self.assertLess(pts_accel[-1][0], tip_rest[0])

        # Settling at zero velocity converges back toward rest shape
        for _ in range(80):
            pts_settled = chain.update(0.02, (104.0, 200.0), vel_xy=(0.0, 0.0))
        self.assertAlmostEqual(pts_settled[0][0], 104.0, places=3)

    def test_ear_spring_startle_and_twitch(self):
        ears = EarSpring()
        calm = ears.update(0.02, speed=0.0, mood="calm", startled=False, t=1.0)
        self.assertEqual(calm.mode, "up")
        self.assertLess(calm.layback, 0.2)

        for _ in range(25):
            scared = ears.update(0.02, speed=300.0, mood="hiss", startled=True, t=0.1)
        self.assertGreaterEqual(scared.layback, 0.8)
        self.assertEqual(scared.mode, "flat")
        # At t=0.07, left ear twitch phase (< 0.28) is active
        twitching = ears.update(0.01, speed=0.0, mood="calm", startled=False, t=0.07)
        self.assertNotEqual(twitching.twitch_left, 0.0)


class TestGazeAndEmotes(unittest.TestCase):
    def test_gaze_lerps_toward_pointer_and_dilates_in_dark(self):
        gc = GazeController()
        gaze1, pupil1 = gc.update(0.05, (100.0, 100.0), (260.0, 140.0), is_dark=False)
        self.assertGreater(gaze1[0], 0.0)
        self.assertGreater(gaze1[1], 0.0)

        for _ in range(30):
            gaze_dark, pupil_dark = gc.update(0.05, (100.0, 100.0), (260.0, 140.0), is_dark=True)
        self.assertGreater(pupil_dark, pupil1 + 0.3)
        self.assertGreater(gaze_dark[0], gaze1[0])

    def test_anime_emotes_draw_all_variants(self):
        canvas = FakeCanvas()
        for emote in AnimeEmotes.EMOTES:
            ids = AnimeEmotes.draw(canvas, (130.0, 100.0), emote, progress=0.25, scale=1.0)
            self.assertGreater(len(ids), 0, f"Emote {emote} created no items")


class TestCostumesGrowthAndRetro(unittest.TestCase):
    def test_layered_costumes_and_backward_compatible_accessories(self):
        for acc in CatRenderer.ALL_ACCESSORIES:
            canvas = FakeCanvas()
            renderer = CatRenderer(canvas)
            brain = SimpleNamespace(state="sit", facing=1)
            renderer.draw(brain, 1.2, accessory=acc)
            self.assertGreater(renderer.item_count, 5, f"Accessory {acc} failed to render")
        self.assertEqual(CatRenderer.ACCESSORIES, (None, "bow", "scarf", "hat", "glasses"))

    def test_growth_stage_kitten_to_adult(self):
        kitten = GrowthStage.evaluate(1.0)
        self.assertEqual(kitten.stage, "kitten")
        self.assertAlmostEqual(kitten.scale, 0.68, places=2)
        self.assertGreater(kitten.head_scale, 1.0)
        self.assertGreater(kitten.wobble, 0.0)

        adult = GrowthStage.evaluate(7.0)
        self.assertEqual(adult.stage, "adult")
        self.assertAlmostEqual(adult.scale, 1.0, places=2)
        self.assertAlmostEqual(adult.head_scale, 1.0, places=2)
        self.assertAlmostEqual(adult.wobble, 0.0, places=2)

        dx, dy, tilt = GrowthStage.step_wobble(0.5, 1.0)
        self.assertTrue(dx != 0.0 or dy != 0.0 or tilt != 0.0)
        self.assertEqual(GrowthStage.step_wobble(0.5, 10.0), (0.0, 0.0, 0.0))

    def test_retro_pixel_filter_quantizes_grid_colors_and_adds_dither(self):
        rpf = RetroPixelFilter(grid_size=4)
        self.assertEqual(rpf.quantize_coords([13.2, 17.9]), [12.0, 16.0])
        self.assertEqual(rpf.quantize_color("#ff8345"), "#f88040")

        canvas = FakeCanvas()
        renderer = CatRenderer(canvas)
        renderer.set_retro_mode(True)
        renderer.draw(SimpleNamespace(state="sit", facing=1, emote="heart"), 0.5)

        dither_lines = canvas.find_withtag("retro_dither")
        self.assertGreater(len(dither_lines), 10)
        stipples = {canvas.itemcget(i, "stipple") for i in dither_lines}
        self.assertTrue({"gray50", "gray25"}.issubset(stipples))

        for iid in canvas.find_all():
            for c in canvas.coords(iid):
                self.assertEqual(c % 4.0, 0.0)

    def test_renderer_preserves_standard_poses(self):
        for state in ("sit", "wander", "follow", "play", "sleep", "roll", "stretch", "hiss", "groom"):
            canvas = FakeCanvas()
            renderer = CatRenderer(canvas)
            brain = SimpleNamespace(
                state=state,
                facing=1,
                age_days=2.0 if state == "wander" else None,
                pointer_xy=(200.0, 90.0) if state == "sit" else None,
            )
            renderer.draw(brain, 1.5, "")
            self.assertGreater(renderer.item_count, 10)


class TestDesktopPropsAndPawPrints(unittest.TestCase):
    def test_desktop_props_and_evaporating_paw_prints(self):
        canvas = FakeCanvas()
        self.assertGreater(len(draw_cardboard_box(canvas, 80, 240)), 0)
        self.assertGreater(len(draw_cat_bed(canvas, 180, 240, occupied=True)), 0)
        self.assertGreater(len(draw_laser_dot(canvas, 120, 140, t=0.4)), 0)
        self.assertGreater(len(draw_task_fish(canvas, 140, 80, t=0.2, label="Task")), 0)

        trail = PawPrintTrail(ttl=1.0)
        trail.add_print(50, 220, angle=0.2)
        items_fresh = trail.draw(canvas)
        self.assertGreater(len(items_fresh), 0)
        self.assertEqual(canvas.itemcget(items_fresh[0], "stipple"), "gray75")

        trail.update(0.85)
        items_fading = trail.draw(canvas)
        self.assertEqual(canvas.itemcget(items_fading[0], "stipple"), "gray12")

        trail.update(0.25)
        self.assertEqual(len(trail.prints), 0)


class TestCompanionSociality(unittest.TestCase):
    def _make_cat(self, x, y, state="sit", energy=80.0):
        brain = SimpleNamespace(x=x, y=y, width=100, height=100, state=state, facing=1, energy=energy)
        return SimpleNamespace(brain=brain, w=100, h=100, social_state=None, social_partner=None)

    def test_social_interactions_trigger_under_90_px(self):
        a = self._make_cat(100, 100, state="sit")
        b = self._make_cat(160, 100, state="sit")
        self.assertLess(cat_distance(a, b), SOCIAL_DISTANCE)

        mode_groom = apply_social_interaction(a, b, dt=0.05)
        self.assertEqual(mode_groom, "mutual_groom")
        self.assertEqual(a.brain.state, "groom")
        self.assertEqual(b.brain.state, "groom")
        self.assertEqual(a.brain.facing, 1)
        self.assertEqual(b.brain.facing, -1)

        a.brain.state = "play"
        mode_ball = apply_social_interaction(a, b, dt=0.05)
        self.assertEqual(mode_ball, "pass_ball")
        self.assertEqual(a.brain.state, "play")
        self.assertEqual(b.brain.state, "play")
        self.assertTrue(hasattr(a.brain, "ball_x"))

        a.brain.state = "sit"
        b.brain.energy = 20.0
        mode_sleep = apply_social_interaction(a, b, dt=0.05)
        self.assertEqual(mode_sleep, "cuddle_sleep")
        self.assertEqual(a.brain.state, "sleep")
        self.assertEqual(b.brain.state, "sleep")

    def test_social_interaction_clears_when_far_apart(self):
        a = self._make_cat(100, 100)
        b = self._make_cat(150, 100)
        self.assertEqual(apply_social_interaction(a, b), "mutual_groom")

        b.brain.x = 300
        self.assertGreaterEqual(cat_distance(a, b), SOCIAL_DISTANCE)
        self.assertIsNone(apply_social_interaction(a, b))
        self.assertIsNone(a.social_state)
        self.assertIsNone(b.social_state)


if __name__ == "__main__":
    unittest.main()
