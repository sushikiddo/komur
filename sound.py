"""Backward-compatible sound wrapper. Delegates to audio.py."""
from __future__ import annotations

import audio


def play(name="meow", enabled=True):
    """Play a named clip without blocking the UI."""
    audio.play(name, enabled=enabled)


def available():
    return audio.available()
