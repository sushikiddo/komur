"""Gerçekçi kedi sesleri — MP3 dosyaları ile (pygame.mixer üzerinden).
Kullanıcı tarafından sağlanan gerçek kedi kayıtları kullanılır.
"""
from __future__ import annotations

import io
import logging
import os
import sys
import threading

from acoustic_engine import apply_channel_pan, pitch_shift_wav, random_pitch_factor

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
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        _mixer_initialized = True
    except Exception:
        logging.exception("pygame.mixer başlatılamadı")


def _full_path(name):
    filename = SOUND_FILES.get(name)
    if filename is None:
        return None
    return os.path.join(ASSETS_DIR, filename)


def play(
    name="meow",
    enabled=True,
    quality="high",
    volume=70,
    pan_x=None,
    screen_w=None,
    pitch_shift=None,
):
    """Gerçek ses dosyasını oynatır. 2D stereo pan ve pitch_shift destekler; UI'ı bloklamaz."""
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
            factor = random_pitch_factor() if pitch_shift == "auto" else pitch_shift
            if factor is not None and abs(float(factor) - 1.0) > 1e-4:
                with open(path, "rb") as f:
                    shifted = pitch_shift_wav(f.read(), float(factor))
                sound = pygame.mixer.Sound(io.BytesIO(shifted))
            else:
                sound = pygame.mixer.Sound(path)
            master_vol = max(0, min(100, volume)) / 100.0
            if pan_x is not None:
                channel = sound.play()
                apply_channel_pan(channel, pan_x, screen_w or 1920, master_vol)
            else:
                sound.set_volume(master_vol)
                sound.play()
        except Exception:
            logging.exception("Ses oynatma hatası: %s", name)

    threading.Thread(target=_run, daemon=True).start()


def available():
    return sys.platform == "win32"
