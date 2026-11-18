import io
import json
import sqlite3

import pytest

from memory_store import MemoryStore
from persona_dreams import (
    DreamEngine,
    GitTerminalWatcher,
    HardwareMind,
    MeowTranslator,
    PERSONA_TEMPLATES,
    RubberDuckDebugger,
    build_persona_prompt,
    get_persona,
    list_personas,
    translate_meow,
)


# ---------------------------------------------------------------------------
# MemoryStore — Dilim 4 tabloları ve user_version uyumluluğu
# ---------------------------------------------------------------------------
def test_memory_store_preserves_user_version_and_adds_slice4_tables(tmp_path):
    path = tmp_path / "memory.sqlite3"
    store = MemoryStore(path)
    with store.connection() as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row["name"]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert version == 3
    assert {"messages", "notes", "reminders", "habits", "dreams", "affection", "fish_tasks"} <= tables


def test_dreams_crud_and_redaction(tmp_path):
    path = tmp_path / "memory.sqlite3"
    store = MemoryStore(path)
    assert store.latest_dream() is None

    id1 = store.add_dream("Somon yağmuru gördüm", source_summary="balık")
    id2 = store.add_dream("Gizli sk-abcdefghijklmnop rüyası", source_summary="not")
    assert id2 > id1

    reopened = MemoryStore(path)
    latest = reopened.latest_dream()
    assert latest is not None
    assert latest["id"] == id2
    assert "sk-abcdefghijklmnop" not in latest["dream_text"]
    assert "[anahtar gizlendi]" in latest["dream_text"]
    assert len(reopened.dreams(limit=1)) == 1
    assert len(reopened.dreams(limit=10)) == 2


def test_affection_xp_and_leveling(tmp_path):
    path = tmp_path / "memory.sqlite3"
    store = MemoryStore(path)
    initial = store.get_affection()
    assert initial["id"] == 1
    assert initial["xp"] == 0
    assert initial["level"] == 1

    res1 = store.add_affection_xp(40)
    assert res1["xp"] == 40
    assert res1["level"] == 1
    assert res1["leveled_up"] is False

    res2 = store.add_affection_xp(75)
    assert res2["xp"] == 115
    assert res2["level"] == 2
    assert res2["leveled_up"] is True

    reopened = MemoryStore(path)
    assert reopened.get_affection()["xp"] == 115
    assert reopened.get_affection()["level"] == 2

    with pytest.raises(ValueError):
        store.add_affection_xp(-5)


def test_fish_tasks_lifecycle(tmp_path):
    path = tmp_path / "memory.sqlite3"
    store = MemoryStore(path)
    t1 = store.add_fish_task("Testleri yeşil yap")
    t2 = store.add_fish_task("Commit at")

    pending = store.pending_fish_tasks()
    assert [t["title"] for t in pending] == ["Testleri yeşil yap", "Commit at"]

    assert store.complete_fish_task(t1) is True
    assert store.complete_fish_task(t1) is False

    reopened = MemoryStore(path)
    pending_after = reopened.pending_fish_tasks()
    assert [t["id"] for t in pending_after] == [t2]


# ---------------------------------------------------------------------------
# HardwareMind
# ---------------------------------------------------------------------------
def test_hardware_mind_thermal_bask_and_safe_failures():
    hot = HardwareMind(temp_probe=lambda: 75.0)
    res = hot.evaluate()
    assert res == {
        "pose": "thermal_bask",
        "message": "İşlemci sıcacık, tam yatmalık!",
        "temp": 75.0,
    }

    warm = HardwareMind(temp_probe=lambda: 83.46)
    assert warm.evaluate()["temp"] == 83.5

    cool = HardwareMind(temp_probe=lambda: 62.0)
    assert cool.evaluate() is None

    broken = HardwareMind(temp_probe=lambda: 1 / 0)
    assert broken.read_cpu_temp() is None
    assert broken.evaluate() is None

    invalid = HardwareMind(temp_probe=lambda: float("nan"))
    assert invalid.read_cpu_temp() is None


# ---------------------------------------------------------------------------
# DreamEngine
# ---------------------------------------------------------------------------
def test_dream_engine_time_window_and_offline_fallback(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.remember("Python testlerini bitir")
    store.add_message("user", "Bugün pytest hata verdi")

    def failing_opener(req, timeout=5.0):
        raise OSError("Ollama offline")

    engine = DreamEngine(store, opener=failing_opener)

    # Gündüz uyanıkken rüya üretmez
    assert engine.generate_dream(is_sleeping=False, hour=14) is None

    # Uyurken üretir ve kaydeder
    result = engine.generate_dream(is_sleeping=True, hour=14)
    assert result is not None
    assert result["bubble"].startswith("💭 Rüyasında: ")
    assert store.latest_dream()["dream_text"] == result["dream_text"]
    assert engine.dream_bubble() == result["bubble"]

    # Gece saatinde uyanık olsa da gece rüyası tetiklenebilir
    assert DreamEngine.is_dream_time(is_sleeping=False, hour=23) is True
    assert DreamEngine.is_dream_time(is_sleeping=False, hour=3) is True
    assert DreamEngine.is_dream_time(is_sleeping=False, hour=10) is False


def test_dream_engine_uses_callback_and_ollama_when_available(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.add_message("user", "Kahve içiyorum")

    cb_engine = DreamEngine(store, ai_callback=lambda prompt: "Süt köpüğü denizinde yüzüyordum.")
    res_cb = cb_engine.generate_dream(is_sleeping=True)
    assert res_cb["dream_text"] == "Süt köpüğü denizinde yüzüyordum."
    assert res_cb["bubble"] == "💭 Rüyasında: Süt köpüğü denizinde yüzüyordum."

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def ok_opener(req, timeout=5.0):
        body = json.dumps({"response": "Klavyenin üstünde balık sayıyordum."}).encode("utf-8")
        return FakeResp(body)

    ollama_engine = DreamEngine(store, opener=ok_opener)
    res_ol = ollama_engine.generate_dream(is_sleeping=True)
    assert res_ol["dream_text"] == "Klavyenin üstünde balık sayıyordum."
    assert store.latest_dream()["dream_text"] == "Klavyenin üstünde balık sayıyordum."


# ---------------------------------------------------------------------------
# PERSONA_TEMPLATES
# ---------------------------------------------------------------------------
def test_persona_templates_and_prompt_builder():
    assert set(PERSONA_TEMPLATES.keys()) == {"asil_tembel", "hiperaktif_yavru", "bilge_yazilimci"}
    assert PERSONA_TEMPLATES["asil_tembel"]["mbti"] == "INTJ"
    assert PERSONA_TEMPLATES["hiperaktif_yavru"]["mbti"] == "ENFP"
    assert PERSONA_TEMPLATES["bilge_yazilimci"]["mbti"] == "INTP"

    assert len(list_personas()) == 3
    assert get_persona("unknown")["id"] == "asil_tembel"
    prompt = build_persona_prompt("bilge_yazilimci", "Sen Kömür'sün.")
    assert "Sen Kömür'sün." in prompt
    assert "INTP" in prompt


# ---------------------------------------------------------------------------
# RubberDuckDebugger
# ---------------------------------------------------------------------------
def test_rubber_duck_debugger_socratic_flow():
    duck = RubberDuckDebugger()
    assert duck.active is False

    # Normal mesajda tetiklenmez
    idle_res = duck.process_message("Selam Kömür, nasılsın?")
    assert idle_res["active"] is False
    assert idle_res["question"] is None

    # Tetikleyiciler
    for phrase in ("lastik ördek", "Rubber Duck", "Bu kod neden çalışmıyor?", "Hatayı bulamıyorum"):
        assert RubberDuckDebugger.is_trigger(phrase) is True

    res1 = duck.process_message("Lastik ördek aç, bu kod neden çalışmıyor?")
    assert res1["active"] is True
    assert res1["triggered"] is True
    assert res1["step"] == 1
    assert "?" in res1["question"]
    assert "ASLA doğrudan hazır kod" in res1["system_prompt"]

    res2 = duck.process_message("Liste boş dönüyor sanırım")
    assert res2["active"] is True
    assert res2["triggered"] is False
    assert res2["step"] == 2
    assert res2["question"] != res1["question"]

    res_exit = duck.process_message("Tamam hatayı buldum!")
    assert res_exit["active"] is False
    assert res_exit["closed"] is True


# ---------------------------------------------------------------------------
# GitTerminalWatcher
# ---------------------------------------------------------------------------
def test_git_terminal_watcher_commit_dance_and_test_fail_hiss(tmp_path):
    git_logs = tmp_path / ".git" / "logs"
    git_logs.mkdir(parents=True)
    head_file = git_logs / "HEAD"
    head_file.write_text(
        "0000000 1111111 Dev <d@example.com> 1700000000 +0300\tcommit (initial): init\n",
        encoding="utf-8",
    )

    watcher = GitTerminalWatcher(tmp_path)
    # İlk kontrol taban çizgisini alır
    assert watcher.check_git() is None
    assert watcher.check_git() is None

    # Yeni commit eklendiğinde dans olayı döner
    with head_file.open("a", encoding="utf-8") as fh:
        fh.write("1111111 2222222 Dev <d@example.com> 1700000100 +0300\tcommit: feat slice4\n")

    dance = watcher.check_git()
    assert dance == {
        "event": "commit_dance",
        "state": "dance",
        "emote": "heart",
        "message": "Yeni commit! Kodlar tertemiz, kutlama dansı!",
    }
    assert watcher.check_git() is None

    # Terminal hata algılama
    for sample in (
        ("FAIL: test_x", ""),
        ("", "ValueError: something went wrong\nError"),
        ("", "Traceback (most recent call last):\n  File 'a.py'"),
        ("pytest failed (2 errors)", ""),
    ):
        hiss = watcher.check_terminal(title=sample[0], output=sample[1])
        assert hiss == {
            "event": "test_fail_hiss",
            "state": "hiss",
            "emote": "anger",
            "message": "Fısss! Testler patlamış, bir bug kokusu alıyorum!",
        }

    assert watcher.check_terminal(title="PowerShell", output="6 passed in 0.12s") is None


# ---------------------------------------------------------------------------
# MeowTranslator
# ---------------------------------------------------------------------------
def test_meow_translator_subtitles():
    translator = MeowTranslator()

    hungry = translator.translate_meow("miyav", state="idle", mood=60, hunger=85, hour=14)
    assert "balık" in hungry.lower() or "mama" in hungry.lower()

    purr_warm = translate_meow("purr", state="thermal_bask", mood=90, hunger=10, hour=15)
    assert "işlemci" in purr_warm.replace("İ", "i").lower()

    hiss_err = translate_meow("hiss", state="hiss", mood=30, hunger=20, hour=16)
    assert "bug" in hiss_err.lower() or "tıss" in hiss_err.lower()

    night_meow = translate_meow("meow", state="idle", mood=70, hunger=20, hour=2)
    assert "gece" in night_meow.lower() or "3.00" in night_meow

    dance_meow = translate_meow("miyav", state="dance", mood=95, hunger=10, hour=12)
    assert "zafer" in dance_meow.lower() or "yeşil" in dance_meow.lower()
