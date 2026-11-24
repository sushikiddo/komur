"""v5 görev 5: alışkanlık hafızası (yalnız eylem anahtarı + saat + sayaç) ve öneri metni."""
import datetime as dt
import random
import sqlite3

import pytest

from commands import CommandEngine, HABIT_MIN_DAYS
from memory_store import MemoryStore


class Actions:
    def __init__(self):
        self.outcome = "Açtım."

    def describe_for_prompt(self):
        return "test"

    def tool_definitions(self):
        return []

    def execute(self, name, args, confirmed=False):
        return self.outcome


class Clock:
    def __init__(self, when):
        self.when = when

    def __call__(self):
        return self.when


def make(tmp_path, settings=None, when=None):
    store = MemoryStore(tmp_path / "m.sqlite3")
    clock = Clock(when or dt.datetime(2026, 11, 10, 21, 5))
    actions = Actions()
    ai = CommandEngine((settings or {}).get, actions, clock=clock, rng=random.Random(1), habits=store)
    return ai, store, clock, actions


def run_on_days(ai, clock, text, days, hour=21):
    base = clock.when.replace(hour=hour)
    for offset in range(days):
        clock.when = base + dt.timedelta(days=offset)
        ai.respond(text)


def test_store_keeps_only_action_hour_counter_and_counts_a_day_once(tmp_path):
    store = MemoryStore(tmp_path / "m.sqlite3")
    day = dt.date(2026, 11, 10).toordinal()
    assert store.record_habit("lol", 21, day) is True
    assert store.record_habit("lol", 21, day) is False          # aynı gün tekrar sayılmaz
    assert store.record_habit("lol", 21, day + 1) is True
    assert store.habits() == [{"action": "lol", "hour": 21, "count": 2}]
    with sqlite3.connect(store.path) as db:
        columns = [row[1] for row in db.execute("PRAGMA table_info(habits)")]
    assert columns == ["action", "hour", "count", "last_day"]


@pytest.mark.parametrize("action,hour", [("Chrome - Banka", 3), ("lol;drop", 3), ("", 3), ("x" * 33, 3), ("lol", 24)])
def test_store_rejects_free_text_and_bad_hours(tmp_path, action, hour):
    with pytest.raises(ValueError):
        MemoryStore(tmp_path / "m.sqlite3").record_habit(action, hour, 1)


def test_running_a_catalog_app_records_canonical_key_only(tmp_path):
    ai, store, clock, actions = make(tmp_path)
    ai.respond("league of legends aç")
    assert store.habits() == [{"action": "lol", "hour": 21, "count": 1}]
    assert "league" not in str(store.habits())


def test_failed_pending_or_unknown_apps_are_not_recorded(tmp_path):
    ai, store, clock, actions = make(tmp_path)
    actions.outcome = "Olmadı: bulunamadı"
    ai.respond("spotify aç")
    assert store.habits() == []
    ai._record_habit("open_app", {"name": "benim özel gizli programım"})
    ai._record_habit("run_command", {"name": "spotify"})
    assert store.habits() == []


def test_suggestion_after_enough_days_once_per_day(tmp_path):
    ai, store, clock, actions = make(tmp_path)
    run_on_days(ai, clock, "league of legends aç", HABIT_MIN_DAYS)
    assert store.top_habit(21)[0] == "lol"
    clock.when = dt.datetime(2026, 11, 20, 20, 59)
    assert ai.habit_suggestion() is None                   # farklı saat
    clock.when = dt.datetime(2026, 11, 20, 21, 2)
    text = ai.habit_suggestion()
    assert text and "League of Legends" in text and "akşam" in text.lower()
    assert ai.habit_suggestion() is None                   # tek seferlik
    clock.when = dt.datetime(2026, 11, 21, 21, 2)
    assert ai.habit_suggestion() is not None               # ertesi gün yeniden


def test_no_suggestion_before_threshold_or_if_already_done_today(tmp_path):
    ai, store, clock, actions = make(tmp_path)
    run_on_days(ai, clock, "spotify aç", HABIT_MIN_DAYS - 1)
    assert ai.habit_suggestion() is None
    run_on_days(ai, clock, "spotify aç", HABIT_MIN_DAYS + 1)   # günü bugün de yaptı
    assert ai.habit_suggestion() is None


def test_setting_off_stops_recording_and_suggestions(tmp_path):
    ai, store, clock, actions = make(tmp_path, {"habit_memory": False})
    run_on_days(ai, clock, "spotify aç", HABIT_MIN_DAYS + 1)
    assert store.habits() == []
    store.record_habit("spotify", 21, 1)
    store.record_habit("spotify", 21, 2)
    store.record_habit("spotify", 21, 3)
    clock.when = dt.datetime(2026, 12, 1, 21, 0)
    assert ai.habit_suggestion() is None


def test_default_is_on_and_works_without_store(tmp_path):
    ai, store, clock, actions = make(tmp_path)
    assert ai._habits_enabled()
    plain = CommandEngine({}.get, Actions())
    assert plain.habit_suggestion() is None
    plain.respond("spotify aç")                              # hafıza yokken sorunsuz


def test_clear_conversation_also_clears_habits(tmp_path):
    store = MemoryStore(tmp_path / "m.sqlite3")
    store.record_habit("lol", 21, 5)
    store.remember("not")
    store.clear_conversation()
    assert store.habits() == [] and store.notes() == []
