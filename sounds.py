"""Gerçekçi kedi sesleri — gerçek kedi kayıtlarından üretilmiş WAV varyantları.

Kullanıcı tarafından sağlanan gerçek kedi kayıtlarından (miyavlama.mp3, mırrlama.mp3)
türetilmiş WAV kliplerini Windows'ta pygame.mixer, macOS'ta CoreAudio afplay ile
2D stereo pan, doğal perde varyasyonu ve üst üste binme korumasıyla oynatır.
"""
from __future__ import annotations

import io
import logging
import os
import random
import sys
import threading
import time

import audio
from acoustic_engine import (
    apply_channel_pan,
    pan_wav_stereo,
    pitch_shift_wav,
    random_pitch_factor,
)

try:
    import pygame.mixer
except Exception:  # pragma: no cover
    pygame = None  # type: ignore

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
MIN_PLAY_GAP_SEC = 0.45

# Geriye dönük uyumluluk için her mantıksal ad için birincil dosya adı (str).
SOUND_FILES: dict[str, str] = {
    "meow": "meow_a.wav",
    "purr": "purr_short.wav",
    "purr_long": "purr_long.wav",
    "purr_loop": "purr_loop.wav",
    "play": "pounce_a.wav",
    "sleep": "sleepy_a.wav",
    "chirp": "trill_a.wav",
    "hiss": "hiss_a.wav",
    "sneeze": "sneeze_a.wav",
    "knead": "purr_short.wav",
    "happy": "feed_a.wav",
    "angry": "growl_hiss.wav",
    "drink": "purr_short.wav",
    "eat": "nom_a.wav",
    "greet": "greet_a.wav",
    "question": "question_a.wav",
    "hungry": "hungry_a.wav",
    "yawn": "yawn_a.wav",
    "mew": "mew_a.wav",
}

# Doğal çeşitlilik için mantıksal ses başına gerçek kedi varyantları.
SOUND_VARIANTS: dict[str, tuple[str, ...]] = {
    "meow": ("meow_a.wav", "meow_b.wav", "meow_c.wav"),
    "purr": ("purr_short.wav", "sleepy_a.wav"),
    "purr_long": ("purr_long.wav", "purr_loop.wav"),
    "purr_loop": ("purr_loop.wav",),
    "play": ("pounce_a.wav", "pounce_b.wav", "mew_b.wav"),
    "sleep": ("sleepy_a.wav", "sleepy_b.wav"),
    "chirp": ("trill_a.wav", "trill_b.wav", "greet_a.wav"),
    "hiss": ("hiss_a.wav", "hiss_b.wav"),
    "sneeze": ("sneeze_a.wav", "sneeze_b.wav"),
    "knead": ("purr_short.wav", "sleepy_a.wav"),
    "happy": ("feed_a.wav", "feed_b.wav", "greet_a.wav"),
    "angry": ("growl_hiss.wav", "hiss_a.wav"),
    "drink": ("purr_short.wav",),
    "eat": ("nom_a.wav", "nom_b.wav", "feed_a.wav"),
    "greet": ("greet_a.wav", "trill_a.wav"),
    "question": ("question_a.wav", "question_b.wav"),
    "hungry": ("hungry_a.wav", "hungry_b.wav"),
    "yawn": ("yawn_a.wav", "yawn_b.wav"),
    "mew": ("mew_a.wav", "mew_b.wav"),
}

_mixer_initialized = False
_lock = threading.Lock()
_last_variant: dict[str, str] = {}
_last_play_time = 0.0


def _init_mixer():
    global _mixer_initialized, _last_play_time
    if pygame is None or _mixer_initialized:
        return
    try:
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        _mixer_initialized = True
        with _lock:
            _last_play_time = 0.0
    except Exception:
        logging.exception("pygame.mixer başlatılamadı")


def reset_throttle():
    """Oynatma aralığı zamanlayıcısını sıfırlar."""
    global _last_play_time
    with _lock:
        _last_play_time = 0.0


def _resolve_pitch_factor(pitch_shift) -> float:
    if pitch_shift is None or pitch_shift == "auto":
        return random_pitch_factor(low=0.95, high=1.05)
    return float(pitch_shift)


def _full_path(name):
    variants = SOUND_VARIANTS.get(name)
    if variants:
        existing = [fn for fn in variants if os.path.exists(os.path.join(ASSETS_DIR, fn))]
        if existing:
            if len(existing) == 1:
                chosen = existing[0]
            else:
                with _lock:
                    prev = _last_variant.get(name)
                    pool = [fn for fn in existing if fn != prev] or existing
                    chosen = random.choice(pool)
                    _last_variant[name] = chosen
            return os.path.join(ASSETS_DIR, chosen)
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
    """Gerçek kedi ses dosyasını oynatır. 2D stereo pan, pitch_shift ve throttling destekler."""
    global _last_play_time
    if not enabled:
        return
    if name not in SOUND_FILES and name not in SOUND_VARIANTS:
        return
    _init_mixer()
    use_afplay = (pygame is None or not _mixer_initialized) and bool(audio.AFPLAY)
    use_winsound = (pygame is None or not _mixer_initialized) and (audio.winsound is not None)
    if not use_afplay and not use_winsound and (pygame is None or not _mixer_initialized):
        return
    path = _full_path(name)
    if path is None or not os.path.exists(path):
        logging.warning("Ses dosyası bulunamadı: %s", path)
        return

    now = time.monotonic()
    with _lock:
        if (now - _last_play_time) < MIN_PLAY_GAP_SEC:
            return
        _last_play_time = now

    master_vol = max(0, min(100, volume)) / 100.0
    factor = _resolve_pitch_factor(pitch_shift)

    if use_afplay or use_winsound:
        def _run_native():
            try:
                with open(path, "rb") as f:
                    data = f.read()
                if abs(factor - 1.0) > 1e-4:
                    data = pitch_shift_wav(data, factor)
                if pan_x is not None:
                    data = pan_wav_stereo(data, pan_x, screen_w or 1920, master_vol=1.0 if use_afplay else master_vol)
                if use_afplay:
                    audio.play_wav_bytes(data, volume=master_vol)
                else:
                    audio.winsound.PlaySound(data, audio.winsound.SND_MEMORY | audio.winsound.SND_ASYNC)
            except Exception:
                logging.exception("Ses oynatma hatası: %s", name)
        threading.Thread(target=_run_native, daemon=True).start()
        return

    def _run():
        try:
            if abs(factor - 1.0) > 1e-4:
                with open(path, "rb") as f:
                    shifted = pitch_shift_wav(f.read(), factor)
                sound = pygame.mixer.Sound(io.BytesIO(shifted))
            else:
                sound = pygame.mixer.Sound(path)
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
    return sys.platform == "win32" or bool(audio.AFPLAY)
