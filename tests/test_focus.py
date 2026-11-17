"""Tests for focus.py — pomodoro oturumu, kedi durumu, Turkce komut ayristirma."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from focus import FocusSession, MESSAGES, parse_focus_command, phase_to_cat_state


def test_default_sequence_full_cycle():
    s = FocusSession()
    assert s.phase == "idle"
    s.start(now=0)
    assert s.phase == "work"
    assert s.tick(now=0) == ["work_started"]
    assert s.tick(now=0) == []

    t = 0
    # Work 1..3 -> short break -> work
    for i in range(1, 4):
        t += 25 * 60
        assert s.tick(now=t) == ["break_started"]
        assert s.phase == "break"
        assert s.completed_cycles == i
        t += 5 * 60
        assert s.tick(now=t) == ["work_started"]
        assert s.phase == "work"

    # Work 4 -> long break (15 dk)
    t += 25 * 60
    assert s.tick(now=t) == ["long_break_started"]
    assert s.is_long_break is True
    assert s.completed_cycles == 4
    assert s.remaining(now=t) == 15 * 60
    t += 15 * 60
    # Last break ends -> session finished
    assert s.tick(now=t) == ["session_finished"]
    assert s.phase == "idle"
    assert s.remaining(now=t) == 0.0


def test_remaining_counts_down():
    s = FocusSession()
    s.start(work_min=10, break_min=2, cycles=1, now=100)
    assert s.remaining(now=100) == 600
    assert s.remaining(now=160) == 540
    assert s.remaining(now=99999) == 0.0


def test_custom_break_length_and_cycles_one():
    s = FocusSession()
    s.start(work_min=1, break_min=1, cycles=1, now=0)
    s.tick(now=0)
    assert s.tick(now=60) == ["break_started"]
    assert s.remaining(now=60) == 60
    assert s.tick(now=120) == ["session_finished"]
    assert s.phase == "idle"


def test_big_time_jump_emits_all_events_in_order():
    s = FocusSession()
    s.start(work_min=1, break_min=1, cycles=2, now=0)
    # 1 dakika 2 kez is + mola: 60 + 60 + 60 + 60 = 240 saniye sonra bitmis olmali
    events = s.tick(now=240)
    assert events == [
        "work_started",
        "break_started",
        "work_started",
        "break_started",
        "session_finished",
    ]
    assert s.phase == "idle"


def test_schedule_uses_previous_phase_end_not_now():
    s = FocusSession()
    s.start(work_min=1, break_min=1, cycles=2, now=0)
    s.tick(now=0)
    # Work bitis 60; mola 60..120; tick 100'de -> mola devam ediyor
    assert s.tick(now=100) == ["break_started"]
    # Mola bitisi 120 (100'de degil, tick gecikse de 120 sabit)
    assert s.remaining(now=100) == 20
    assert s.tick(now=125) == ["work_started"]
    assert s.remaining(now=125) == 55  # work 120..180


def test_stop_resets_to_idle_and_emits_nothing():
    s = FocusSession()
    s.start(now=0)
    s.stop()
    assert s.phase == "idle"
    assert s.tick(now=10_000) == []


def test_pause_freezes_time_and_resume_continues():
    s = FocusSession()
    s.start(work_min=1, break_min=1, cycles=2, now=0)
    s.tick(now=0)
    s.pause(now=20)
    assert s.phase == "paused"
    assert s.remaining(now=20) == 40
    # Duraklatilmisken zaman gecse de faz ilerlemez
    assert s.tick(now=10_000) == []
    assert s.remaining(now=10_000) == 40
    assert s.phase == "paused"
    s.resume(now=10_000)
    assert s.phase == "work"
    assert s.remaining(now=10_000) == 40
    assert s.tick(now=10_040) == ["break_started"]


def test_pause_during_break_resumes_break():
    s = FocusSession()
    s.start(work_min=1, break_min=2, cycles=2, now=0)
    s.tick(now=0)
    s.tick(now=60)  # break basladi
    s.pause(now=90)
    s.resume(now=500)
    assert s.phase == "break"
    assert s.remaining(now=500) == 90
    assert s.tick(now=590) == ["work_started"]


def test_pause_and_resume_are_noops_when_not_applicable():
    s = FocusSession()
    s.pause(now=0)
    s.resume(now=0)
    assert s.phase == "idle"


def test_pending_work_started_emitted_once():
    s = FocusSession()
    s.start(now=0)
    assert s.tick(now=0) == ["work_started"]
    assert s.tick(now=1) == []


def test_phase_to_cat_state():
    assert phase_to_cat_state("work") == "sleep"
    assert phase_to_cat_state("break") == "stretch"
    assert phase_to_cat_state("idle") is None
    assert phase_to_cat_state("paused") is None


def test_messages_cover_all_events():
    for key in ("work_started", "break_started", "long_break_started", "session_finished"):
        assert MESSAGES[key]
        assert isinstance(MESSAGES[key], str)


@pytest.mark.parametrize(
    "text",
    [
        "pomodoro başlat",
        "POMODORO BAŞLAT",
        "pomodoro baslat",
        "PomodoRo BAŞLAT",
    ],
)
def test_parse_start_defaults(text):
    assert parse_focus_command(text) == {"action": "start", "work_min": 25, "break_min": 5}


@pytest.mark.parametrize("text", ["25 dakika odaklan", "25 DAKİKA ODAKLAN", "25 dakika odaklan"])
def test_parse_minutes(text):
    assert parse_focus_command(text) == {"action": "start", "work_min": 25, "break_min": 5}


@pytest.mark.parametrize("text", ["odak modu 50/10", "ODAK MODU 50/10", "odak modu 50 / 10"])
def test_parse_ratio(text):
    assert parse_focus_command(text) == {"action": "start", "work_min": 50, "break_min": 10}


def test_parse_ratio_with_minutes_word_uses_ratio():
    assert parse_focus_command("pomodoro 30 dakika 6/2")["work_min"] == 6


@pytest.mark.parametrize(
    "text",
    ["pomodoro bitir", "pomodoroyu durdur", "odak modunu kapat", "POMODORO BİTİR", "odak modu iptal"],
)
def test_parse_stop(text):
    assert parse_focus_command(text) == {"action": "stop"}


def test_parse_clamps_values():
    assert parse_focus_command("odak modu 999/999") == {
        "action": "start",
        "work_min": 180,
        "break_min": 60,
    }


@pytest.mark.parametrize(
    "text",
    ["müziği durdur", "25 dakika sonra hatırlat", "merhaba", "", "bitir", "kapat"],
)
def test_parse_unrelated_returns_none(text):
    assert parse_focus_command(text) is None


def test_parse_none_input_safe():
    assert parse_focus_command(None) is None
