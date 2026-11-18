"""Tests for gamification_productivity.py (Dilim 5)."""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamification_productivity import (
    AffectionSystem,
    BossKeyController,
    CatBasketDropTarget,
    HEALTH_REMINDER_MESSAGE,
    HealthWaterGuard,
    TodoFishPond,
    UNLOCK_TABLE,
    enable_file_drop,
    extract_dropped_files,
)
from memory_store import MemoryStore


def _minimal_png_bytes(width: int, height: int) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + b"\x00\x00\x00\x00"


class FakeMemoryStore:
    def __init__(self):
        self.notes: list[str] = []

    def remember(self, text: str) -> str:
        self.notes.append(text)
        return f"saved:{len(self.notes)}"


class FakeSettings:
    def __init__(self, initial=None):
        self.data = dict(initial or {})
        self.calls: list[tuple[str, object, bool | None]] = []

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, save=True):
        self.data[key] = value
        self.calls.append((key, value, save))

    def update(self, **kwargs):
        self.data.update(kwargs)


class FakeWidget:
    def __init__(self, hwnd=12345, exists=True):
        self._hwnd = hwnd
        self._exists = exists
        self.withdrawn = 0
        self.deiconified = 0

    def winfo_id(self):
        return self._hwnd

    def winfo_exists(self):
        return self._exists

    def withdraw(self):
        self.withdrawn += 1

    def deiconify(self):
        self.deiconified += 1


class TestCatBasketDropTarget(unittest.TestCase):
    def test_image_drop_reads_dimensions_and_calls_ai_vision(self):
        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "screen.png"
            img_path.write_bytes(_minimal_png_bytes(64, 32))

            vision_calls = []

            class FakeVisionAI:
                def analyze_image(self, path, prompt=None):
                    vision_calls.append((path, prompt))
                    return "Ekranda bir terminal penceresi görünüyor."

            basket = CatBasketDropTarget()
            res = basket.handle_drop(f'"{img_path}"', ai_client=FakeVisionAI())

            self.assertTrue(res["ok"])
            self.assertEqual(res["action"], "vision_analyze")
            self.assertEqual(res["dimensions"], (64, 32))
            self.assertEqual(res["size_bytes"], img_path.stat().st_size)
            self.assertIn("terminal penceresi", res["summary"])
            self.assertEqual(len(vision_calls), 1)

    def test_image_drop_without_ai_provides_local_summary(self):
        basket = CatBasketDropTarget()
        for ext in (".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
            res = basket.handle_drop(f"C:/fake/photo{ext}")
            self.assertTrue(res["ok"])
            self.assertEqual(res["action"], "vision_analyze")
            self.assertEqual(res["extension"], ext)
            self.assertIn(f"photo{ext}", res["summary"])

    def test_code_file_drop_detects_errors_defs_classes_and_calls_ai(self):
        with tempfile.TemporaryDirectory() as tmp:
            py_path = Path(tmp) / "worker.py"
            py_path.write_text(
                "class JobRunner:\n"
                "    def run(self):\n"
                "        # ERROR simulated\n"
                "        raise ValueError('bad')\n",
                encoding="utf-8",
            )

            class FakeSummaryAI:
                def respond(self, prompt):
                    return SimpleNamespace(reply="JobRunner.run içinde ValueError fırlatılıyor.")

            basket = CatBasketDropTarget()
            res = basket.handle_drop(str(py_path), ai_client=FakeSummaryAI())

            self.assertTrue(res["ok"])
            self.assertEqual(res["action"], "summarize_code_or_log")
            self.assertEqual(res["line_count"], 4)
            self.assertEqual(res["classes"], ["JobRunner"])
            self.assertEqual(res["defs"], ["run"])
            self.assertEqual(res["error_count"] if "error_count" in res else len(res["errors"]), 1)
            self.assertIn("ValueError", res["exceptions"])
            self.assertIn("ValueError", res["summary"])

    def test_multiline_log_text_drop_summarizes_without_ai(self):
        log_payload = (
            "2026-11-17 12:00:00 INFO started\n"
            "2026-11-17 12:00:01 ERROR connection timeout\n"
            "Traceback (most recent call last):\n"
            "RuntimeException: failed\n"
        )
        basket = CatBasketDropTarget()
        res = basket.handle_drop(log_payload)

        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "summarize_code_or_log")
        self.assertEqual(res["line_count"], 4)
        self.assertEqual(len(res["errors"]), 2)
        self.assertIn("RuntimeException", res["exceptions"])
        self.assertIn("4 satır", res["summary"])

    def test_link_drop_saves_to_memory_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.sqlite3")
            basket = CatBasketDropTarget()
            res = basket.handle_drop("Python Docs https://docs.python.org/3/", memory_store=store)

            self.assertTrue(res["ok"])
            self.assertEqual(res["action"], "save_link")
            self.assertTrue(res["saved"])
            self.assertEqual(res["url"], "https://docs.python.org/3/")
            self.assertEqual(res["title"], "Python Docs")
            notes = store.notes()
            self.assertEqual(len(notes), 1)
            self.assertIn("https://docs.python.org/3/", notes[0]["content"])

    def test_empty_drop_returns_noop(self):
        basket = CatBasketDropTarget()
        res = basket.handle_drop("   ")
        self.assertFalse(res["ok"])
        self.assertEqual(res["action"], "noop")

    def test_enable_file_drop_tkdnd_and_win32_mock(self):
        # 1) TkDnD yolu
        bound = {}

        class FakeTkDndWidget:
            def drop_target_register(self, dnd_type):
                bound["type"] = dnd_type

            def dnd_bind(self, event_name, fn):
                bound["event"] = event_name
                bound["fn"] = fn

        received = []
        self.assertTrue(enable_file_drop(FakeTkDndWidget(), received.extend))
        self.assertEqual(bound["type"], "DND_Files")
        bound["fn"](SimpleNamespace(data="C:/a.py"))
        self.assertEqual(received, ["C:/a.py"])

        # 2) Win32 WM_DROPFILES mock yolu
        accepted = []
        finished = []

        class FakeShell32:
            def DragAcceptFiles(self, hwnd, flag):
                accepted.append((hwnd, flag))

            def DragQueryFileW(self, hdrop, idx, buf, size):
                files = ["C:/one.png", "C:/two.log"]
                if idx == 0xFFFFFFFF:
                    return len(files)
                path = files[idx]
                if buf is None:
                    return len(path)
                buf.value = path
                return len(path)

            def DragFinish(self, hdrop):
                finished.append(hdrop)

        class FakeUser32:
            pass

        widget = FakeWidget(hwnd=777)
        dropped_batches = []
        ok = enable_file_drop(widget, dropped_batches.append, user32=FakeUser32(), shell32=FakeShell32())
        self.assertTrue(ok)
        self.assertEqual(accepted, [(777, True)])
        widget._komur_drop_handler(999)
        self.assertEqual(dropped_batches, [["C:/one.png", "C:/two.log"]])
        self.assertEqual(finished, [999])

        # extract_dropped_files doğrudan doğrulama
        paths = extract_dropped_files(111, shell32=FakeShell32())
        self.assertEqual(paths, ["C:/one.png", "C:/two.log"])
        self.assertFalse(enable_file_drop(None, lambda x: None))


class TestTodoFishPond(unittest.TestCase):
    def test_add_step_sinusoidal_and_complete_awards_xp(self):
        affection = AffectionSystem()
        pond = TodoFishPond(affection=affection, bounds=(0, 0, 400, 300), seed=42)

        fish = pond.add_task("Raporu tamamla")
        self.assertEqual(fish["title"], "Raporu tamamla")
        for key in ("id", "x", "y", "vx", "phase", "color", "title"):
            self.assertIn(key, fish)

        self.assertEqual(len(pond.list_tasks()), 1)

        y_samples = []
        x_samples = []
        for _ in range(10):
            updated = pond.step(0.1, (0, 0, 400, 300))
            y_samples.append(updated[0]["y"])
            x_samples.append(updated[0]["x"])

        # Sinüzoidal dalgalanma ve yatay hareket doğrulanır
        self.assertGreater(len(set(round(y, 4) for y in y_samples)), 1)
        self.assertGreater(len(set(round(x, 4) for x in x_samples)), 1)

        res = pond.complete_task(fish["id"], cat_x=50, cat_y=50)
        self.assertTrue(res["ok"])
        self.assertTrue(res["caught"])
        self.assertEqual(res["cat_state"], "pounce")
        self.assertAlmostEqual(res["pounce_target"]["x"], x_samples[-1])
        self.assertAlmostEqual(res["pounce_target"]["y"], y_samples[-1])
        self.assertEqual(res["xp_gained"], 25)
        self.assertEqual(affection.xp, 25)
        self.assertIn("yakaladım", res["message"])
        self.assertEqual(pond.list_tasks(), [])

        # Tekrar tamamlama reddedilir
        again = pond.complete_task(fish["id"], 0, 0)
        self.assertFalse(again["ok"])
        self.assertFalse(again["caught"])

    def test_empty_task_title_raises(self):
        pond = TodoFishPond()
        with self.assertRaises(ValueError):
            pond.add_task("   ")


class TestAffectionSystem(unittest.TestCase):
    def test_levels_unlocks_and_persistence(self):
        settings = FakeSettings()
        memory = FakeMemoryStore()
        aff = AffectionSystem(settings=settings, memory_store=memory)

        self.assertEqual(aff.level, 1)
        self.assertIn("bow", aff.get_unlocks()["accessories"])

        # Çeşitli eylemlerden XP kazanma
        r1 = aff.record_action("pet")       # +10 -> 10
        r2 = aff.record_action("feed")      # +15 -> 25
        r3 = aff.record_action("play")      # +20 -> 45
        r4 = aff.record_action("fish_caught")  # +25 -> 70
        r5 = aff.record_action("pomodoro")  # +35 -> 105 (Level 2!)
        self.assertEqual((r1["amount"], r2["amount"], r3["amount"], r4["amount"], r5["amount"]), (10, 15, 20, 25, 35))
        self.assertEqual(aff.xp, 105)
        self.assertEqual(aff.level, 2)
        self.assertTrue(r5["leveled_up"])
        self.assertIn("winter_set", r5["newly_unlocked"])
        self.assertIn("spin", r5["newly_unlocked"])
        self.assertEqual(settings.get("affection_xp"), 105)
        self.assertEqual(settings.get("affection_level"), 2)
        self.assertEqual(len(memory.notes), 1)

        # Level 3, 4, 5+ ödülleri
        aff.add_xp(100, "oyun maratonu")  # 205 -> Lv 3
        self.assertEqual(aff.level, 3)
        u3 = aff.get_unlocks()
        self.assertIn("headphones", u3["accessories"])
        self.assertIn("high_five", u3["tricks"])

        aff.add_xp(100, "odak")  # 305 -> Lv 4
        self.assertEqual(aff.level, 4)
        u4 = aff.get_unlocks()
        self.assertIn("witch_hat", u4["accessories"])
        self.assertIn("backflip", u4["tricks"])

        aff.add_xp(100, "efsane")  # 405 -> Lv 5
        self.assertEqual(aff.level, 5)
        u5 = aff.get_unlocks()
        self.assertIn("cyberpunk_collar", u5["accessories"])
        self.assertIn("retro_pixel", u5["modes"])
        self.assertIn("laser_master", u5["titles"])
        self.assertIn(1, UNLOCK_TABLE)
        self.assertIn(5, UNLOCK_TABLE)

        # Ayarlardan geri yükleme
        restored = AffectionSystem(settings=settings)
        self.assertEqual(restored.xp, 405)
        self.assertEqual(restored.level, 5)

    def test_negative_xp_raises(self):
        aff = AffectionSystem()
        with self.assertRaises(ValueError):
            aff.add_xp(-5)


class TestBossKeyController(unittest.TestCase):
    def test_toggle_dict_state_hides_mutes_and_restores(self):
        boss = BossKeyController()
        state = {"hidden": False, "muted": False, "sound": True, "speech_bubbles": True, "x": 320, "y": 480}

        res1 = boss.toggle(state)
        self.assertTrue(res1["hidden"])
        self.assertTrue(res1["muted"])
        self.assertTrue(res1["stealth_mode"])
        self.assertTrue(state["hidden"])
        self.assertTrue(state["muted"])
        self.assertFalse(state["sound"])

        # Gizliyken konum/durum değişse bile geri yüklemede eski konum gelir
        state["x"], state["y"] = 0, 0
        res2 = boss.toggle(state)
        self.assertFalse(res2["hidden"])
        self.assertFalse(res2["muted"])
        self.assertFalse(res2["stealth_mode"])
        self.assertEqual((state["x"], state["y"]), (320, 480))
        self.assertTrue(state["sound"])

    def test_toggle_app_object_hides_companions_panel_bubble_and_restores_sound(self):
        boss = BossKeyController()
        root = FakeWidget()
        panel = FakeWidget(exists=True)
        mate_win = FakeWidget()
        bubble_calls = []

        class FakeBubble:
            def hide(self):
                bubble_calls.append("hide")

        class FakeBrain:
            def __init__(self):
                self.x = 640.0
                self.y = 420.0

            def move_to(self, x, y):
                self.x, self.y = x, y

        settings = FakeSettings({"sound": True})
        eo = SimpleNamespace(sound_enabled=True)
        app = SimpleNamespace(
            root=root,
            panel=panel,
            bubble=FakeBubble(),
            companions=[SimpleNamespace(window=mate_win)],
            brain=FakeBrain(),
            settings=settings,
            effect_orchestrator=eo,
        )

        boss.toggle(app)
        self.assertEqual(root.withdrawn, 1)
        self.assertEqual(panel.withdrawn, 1)
        self.assertEqual(mate_win.withdrawn, 1)
        self.assertEqual(bubble_calls, ["hide"])
        self.assertFalse(eo.sound_enabled)
        self.assertFalse(settings.get("sound"))
        self.assertTrue(app.stealth_mode)

        boss.toggle(app)
        self.assertEqual(root.deiconified, 1)
        self.assertEqual(panel.deiconified, 1)
        self.assertEqual(mate_win.deiconified, 1)
        self.assertTrue(eo.sound_enabled)
        self.assertTrue(settings.get("sound"))
        self.assertFalse(app.stealth_mode)
        self.assertEqual((app.brain.x, app.brain.y), (640.0, 420.0))

    def test_hotkey_event_matcher(self):
        self.assertTrue(BossKeyController.is_hotkey_event(SimpleNamespace(keysym="K", state=0x5)))
        self.assertFalse(BossKeyController.is_hotkey_event(SimpleNamespace(keysym="k", state=0x4)))


class TestHealthWaterGuard(unittest.TestCase):
    def test_triggers_at_one_hour_and_respects_cooldown_and_reset(self):
        guard = HealthWaterGuard()

        self.assertIsNone(guard.check(3599, pointer=(500, 300), now=100.0))

        alert = guard.check(3600, pointer=(500, 300), now=200.0)
        self.assertIsNotNone(alert)
        self.assertTrue(alert["triggered"])
        self.assertEqual(alert["target_x"], 440.0)
        self.assertEqual(alert["target_y"], 260.0)
        self.assertIn(alert["state"], ("stretch", "yawn"))
        self.assertEqual(alert["message"], HEALTH_REMINDER_MESSAGE)

        # Bekleme süresi dolmadan tekrar tetiklemez
        self.assertIsNone(guard.check(3610, pointer=(500, 300), now=210.0))

        # 1 saat daha sonra tekrar tetikler
        alert2 = guard.check(7200, pointer=(800, 600), now=3800.0)
        self.assertIsNotNone(alert2)
        self.assertEqual(alert2["target_x"], 740.0)
        self.assertEqual(alert2["target_y"], 560.0)
        self.assertIn(alert2["state"], ("stretch", "yawn"))

        # Mola sonrası step ile sıfırlanma ve yeniden sayma
        self.assertIsNone(guard.step(10.0, is_working=False, pointer=(100, 100), now=3900.0))
        self.assertEqual(guard.continuous_work_seconds, 0.0)
        self.assertIsNone(guard.step(1800.0, is_working=True, pointer=(100, 100), now=5700.0))
        alert3 = guard.step(1800.0, is_working=True, pointer=(260, 140), now=7500.0)
        self.assertIsNotNone(alert3)
        self.assertEqual(alert3["target_x"], 200.0)
        self.assertEqual(alert3["target_y"], 100.0)


if __name__ == "__main__":
    unittest.main()
