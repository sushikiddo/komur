"""Tests for sounds.py — realistic cat sound system."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sounds


def test_sounds_play_meow():
    sounds.play("meow", enabled=True, quality="high")


def test_sounds_play_purr():
    sounds.play("purr", enabled=True, quality="high")


def test_sounds_play_purr_long():
    sounds.play("purr_long", enabled=True, quality="high")


def test_sounds_play_play():
    sounds.play("play", enabled=True, quality="high")


def test_sounds_play_sleep():
    sounds.play("sleep", enabled=True, quality="high")


def test_sounds_play_chirp():
    sounds.play("chirp", enabled=True, quality="high")


def test_sounds_play_hiss():
    sounds.play("hiss", enabled=True, quality="high")


def test_sounds_play_sneeze():
    sounds.play("sneeze", enabled=True, quality="high")


def test_sounds_play_knead():
    sounds.play("knead", enabled=True, quality="high")


def test_sounds_play_happy():
    sounds.play("happy", enabled=True, quality="high")


def test_sounds_play_angry():
    sounds.play("angry", enabled=True, quality="high")


def test_sounds_disabled():
    sounds.play("meow", enabled=False)


def test_sounds_available():
    assert isinstance(sounds.available(), bool)
