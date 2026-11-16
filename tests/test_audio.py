"""Tests for audio.py — realistic cat sound synthesis."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio import _wav, _meow, available, _MAKERS


def test_audio_meow_produces_valid_wav():
    data = _wav(_meow(0.5))
    assert data[:4] == b"RIFF"
    assert len(data) > 1000


def test_audio_available_returns_bool():
    assert isinstance(available(), bool)


def test_audio_makers_keys_exist():
    for key in ("meow", "purr", "play", "sleep", "chirp", "hiss", "sneeze"):
        assert key in _MAKERS
