"""Gerçekçi kedi sesleri — MP3 dosyaları ile (pygame.mixer üzerinden).
Kullanıcı tarafından sağlanan gerçek kedi kayıtları kullanılır.
"""
from __future__ import annotations

import logging
import os
import sys
import threading

try:
    import pygame.mixer
except Exception:  # pragma: no cover
    pygame = None  # type: ignore

# MP3 dosyaları assets klasöründe
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

SOUND_FILES = {
    "meow": "meow_a.wav", "purr": "purr_short.wav", "purr_long": "purr_long.wav",
    "play": "pounce_a.wav", "sleep": "sleepy_a.wav", "chirp": "trill_a.wav",
    "hiss": "hiss_a.wav", "sneeze": "sneeze_a.wav", "knead": "purr_short.wav",
    "happy": "feed_a.wav", "angry": "growl_hiss.wav",
}

_mixer_initialized = False
_lock = threading.Lock()


def _init_mixer():
    global _mixer_initialized
    if pygame is None or _mixer_initialized:
        return
    try:
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        _mixer_initialized = True
    except Exception:
        logging.exception("pygame.mixer başlatılamadı")


def _full_path(name):
    filename = SOUND_FILES.get(name)
    if filename is None:
        return None
    return os.path.join(ASSETS_DIR, filename)


def play(name="meow", enabled=True, quality="high", volume=70):
    """Gerçek MP3 kedi sesini oynatır. UI'ı bloklamaz."""
    if not enabled:
        return
    if name not in SOUND_FILES:
        return
    _init_mixer()
    if pygame is None or not _mixer_initialized:
        return
    path = _full_path(name)
    if path is None or not os.path.exists(path):
        logging.warning("Ses dosyası bulunamadı: %s", path)
        return

    def _run():
        try:
            sound = pygame.mixer.Sound(path)
            sound.set_volume(max(0, min(100, volume)) / 100.0)
            sound.play()
        except Exception:
            logging.exception("Ses oynatma hatası: %s", name)

    threading.Thread(target=_run, daemon=True).start()


def available():
    return sys.platform == "win32"
