"""Tests for sound.py backward compatibility with audio.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sound
import audio


def test_sound_play_delegates_to_audio():
    assert hasattr(sound, "play")
    assert hasattr(sound, "available")
    sound.play("meow", enabled=True)


def test_sound_available_matches_audio():
    assert sound.available() == audio.available()
