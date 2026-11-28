"""Gerçekçi kedi ses oynatıcı ve stdlib-only WAV sentezi.

`assets/` altında gerçek kedi kaydından üretilmiş WAV dosyası varsa onu
(isteğe bağlı pitch-shift ve 2D stereo pan ile) oynatır; step/ambiyans gibi
prosedürel sesler veya eksik varlıklar için bellek içi WAV sentezine düşer.
Windows'ta winsound, macOS'ta CoreAudio afplay üzerinden UI'ı bloklamadan çalar.
"""
from __future__ import annotations

import io
import logging
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave

from acoustic_engine import (
    generate_lofi_ambience_samples,
    generate_step_desktop_samples,
    generate_step_window_samples,
    pan_volumes,
    pan_wav_stereo,
    pitch_shift_samples,
    pitch_shift_wav,
    random_pitch_factor,
)

try:
    import winsound  # type: ignore
except Exception:  # pragma: no cover - non-Windows
    winsound = None

# macOS: winsound yok; sistemle gelen afplay ile çalınır.
AFPLAY = shutil.which("afplay") if sys.platform == "darwin" else None
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
MIN_PLAY_GAP_SEC = 0.45

_REAL_WAV_VARIANTS: dict[str, tuple[str, ...]] = {
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


_AFPLAY_SLOTS = threading.BoundedSemaphore(3)
AFPLAY_TIMEOUT = 6


def play_wav_bytes(data, volume=None, pan_x=None, screen_w=None):
    """WAV baytlarını afplay ile çal (bloklar; arka plan iş parçacığında çağır).

    Eşzamanlı afplay sayısı sınırlıdır; meşgulse ses atlanır.
    """
    if not AFPLAY:
        return
    if not _AFPLAY_SLOTS.acquire(blocking=False):
        return
    tmp_path = None
    try:
        payload = data
        if pan_x is not None:
            payload = pan_wav_stereo(payload, pan_x, screen_w or 1920, master_vol=1.0)
        with tempfile.NamedTemporaryFile(prefix="komur-", suffix=".wav", delete=False) as handle:
            handle.write(payload)
            tmp_path = handle.name
        command = [AFPLAY, tmp_path]
        if volume is not None:
            command += ["-v", f"{max(0.0, min(1.0, float(volume))):.2f}"]
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=AFPLAY_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=1)
            except Exception:
                pass
    finally:
        _AFPLAY_SLOTS.release()
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

RATE = 22050
_cache = {}
_real_cache: dict[str, bytes] = {}
_last_variant: dict[str, str] = {}
_last_play_time = 0.0
_lock = threading.Lock()


def _wav(samples, left_vol=None, right_vol=None):
    """16-bit mono (or stereo when left_vol/right_vol are provided) WAV bytes from float samples in [-1, 1]."""
    buf = io.BytesIO()
    stereo = left_vol is not None or right_vol is not None
    with wave.open(buf, "wb") as w:
        w.setnchannels(2 if stereo else 1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        if stereo:
            lv = 1.0 if left_vol is None else float(left_vol)
            rv = 1.0 if right_vol is None else float(right_vol)
            w.writeframes(
                b"".join(
                    struct.pack(
                        "<hh",
                        int(max(-1.0, min(1.0, s * lv)) * 32000),
                        int(max(-1.0, min(1.0, s * rv)) * 32000),
                    )
                    for s in samples
                )
            )
        else:
            w.writeframes(
                b"".join(
                    struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples
                )
            )
    return buf.getvalue()


def _envelope(n, attack=0.02, decay=0.1, sustain=0.7, release=0.15):
    """ADSR envelope, values in [0, 1], length n."""
    out = []
    last = max(1, n - 1)
    for i in range(n):
        t = i / last
        if t < attack:
            out.append(t / attack if attack > 0 else 1.0)
        elif t < attack + decay:
            out.append(1.0 - (1.0 - sustain) * (t - attack) / decay)
        elif t < 1.0 - release:
            out.append(sustain)
        else:
            rel_t = (t - (1.0 - release)) / release if release > 0 else 1.0
            out.append(sustain * (1.0 - rel_t))
    return out


def _meow(duration=0.55, base=1.0):
    """Pitch rises then falls ("mi-yav") with harmonics, formant, and vibrato."""
    n = int(RATE * duration)
    out, phase = [], 0.0
    env = _envelope(n)
    last = max(1, n - 1)
    for i in range(n):
        t = i / last
        freq = base * (480 + 420 * math.sin(math.pi * min(1, t * 1.4)) - 120 * t)
        phase += 2 * math.pi * freq / RATE
        open_mouth = 0.4 + 0.6 * math.sin(math.pi * t)
        vib = 1.0 + 0.02 * math.sin(2 * math.pi * 6 * t)
        s = (
            math.sin(phase)
            + open_mouth * 0.55 * math.sin(2 * phase)
            + open_mouth * 0.3 * math.sin(3 * phase)
            + 0.12 * math.sin(4 * phase)
        ) * vib
        out.append(0.42 * env[i] * s)
    return out


def _purr(duration=1.1):
    """Rumbly ~26 Hz purr with low-frequency noise and gentle envelope."""
    rng = random.Random(3)
    n = int(RATE * duration)
    out, low = [], 0.0
    env = _envelope(n, attack=0.05, decay=0.2, sustain=1.0, release=0.3)
    last = max(1, n - 1)
    for i in range(n):
        t = i / RATE
        low = 0.92 * low + 0.08 * rng.uniform(-1, 1)
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * 26 * t)
        out.append(env[i] * pulse * (2.4 * low + 0.25 * math.sin(2 * math.pi * 52 * t)))
    return out


def _purr_long(duration=3.0):
    return _purr(duration)


def _chirp(duration=0.18):
    """Short high-pitched chirp ("mır, mır!")."""
    n = int(RATE * duration)
    out, phase = [], 0.0
    env = _envelope(n, attack=0.01, decay=0.05, sustain=0.9, release=0.1)
    last = max(1, n - 1)
    for i in range(n):
        t = i / last
        freq = 900 + 300 * math.sin(math.pi * t)
        phase += 2 * math.pi * freq / RATE
        s = math.sin(phase) + 0.4 * math.sin(2 * phase)
        out.append(0.35 * env[i] * s)
    return out


def _hiss(duration=0.6):
    """Fifışma — filtered noise burst."""
    rng = random.Random(7)
    n = int(RATE * duration)
    out, env = [], _envelope(n, attack=0.02, decay=0.1, sustain=0.8, release=0.2)
    last = max(1, n - 1)
    for i in range(n):
        t = i / last
        noise = rng.uniform(-1, 1)
        band = 0.5 * math.sin(2 * math.pi * 120 * t) + 0.3 * math.sin(2 * math.pi * 300 * t)
        out.append(env[i] * (1.5 * noise + band) * 0.3)
    return out


def _sneeze(duration=0.25):
    """Hapşırma — quick burst with decaying tone."""
    n = int(RATE * duration)
    out, env = [], _envelope(n, attack=0.005, decay=0.05, sustain=0.6, release=0.2)
    last = max(1, n - 1)
    for i in range(n):
        t = i / last
        burst = math.exp(-((t - 0.08) / 0.03) ** 2)
        tone = math.sin(2 * math.pi * 400 * t) * 0.5
        out.append(env[i] * (burst + tone) * 0.4)
    return out


def _play(duration=0.35, base=1.3):
    """Two rapid meows for play state."""
    return _meow(duration, base) + _meow(duration, base * 1.1)


_MAKERS = {
    "meow": lambda: _meow(),
    "purr": _purr,
    "purr_long": _purr_long,
    "play": lambda: _play(),
    "sleep": lambda: _meow(0.8, 0.75),
    "chirp": _chirp,
    "hiss": _hiss,
    "sneeze": _sneeze,
    "step_window": generate_step_window_samples,
    "step_desktop": generate_step_desktop_samples,
    "lofi_ambience": generate_lofi_ambience_samples,
}


def _select_real_wav_path(name, pick_random=False):
    """Return an existing real-cat WAV asset path for *name*, or None."""
    variants = _REAL_WAV_VARIANTS.get(name)
    if not variants:
        return None
    existing = [
        fn for fn in variants
        if os.path.exists(os.path.join(ASSETS_DIR, fn))
    ]
    if not existing:
        return None
    if not pick_random or len(existing) == 1:
        chosen = existing[0]
    else:
        with _lock:
            prev = _last_variant.get(name)
            pool = [fn for fn in existing if fn != prev] or existing
            chosen = random.choice(pool)
            _last_variant[name] = chosen
    return os.path.join(ASSETS_DIR, chosen)


def _load_real_wav_bytes(path):
    with _lock:
        cached = _real_cache.get(path)
    if cached is not None:
        return cached
    with open(path, "rb") as f:
        data = f.read()
    with _lock:
        _real_cache[path] = data
    return data


def _clip(name, pitch_shift=None, pan_x=None, screen_w=1920, pick_random=False):
    real_path = _select_real_wav_path(name, pick_random=pick_random)
    if real_path is not None:
        data = _load_real_wav_bytes(real_path)
        if pitch_shift is not None:
            factor = (
                random_pitch_factor(low=0.95, high=1.05)
                if pitch_shift == "auto"
                else float(pitch_shift)
            )
            if abs(factor - 1.0) > 1e-4:
                data = pitch_shift_wav(data, factor)
        if pan_x is not None:
            data = pan_wav_stereo(data, pan_x, screen_w or 1920, master_vol=1.0)
        return data

    if name not in _MAKERS:
        return None
    if pitch_shift is not None or pan_x is not None:
        samples = _MAKERS[name]()
        if pitch_shift is not None:
            factor = random_pitch_factor() if pitch_shift == "auto" else float(pitch_shift)
            samples = pitch_shift_samples(samples, factor)
        if pan_x is not None:
            lv, rv = pan_volumes(pan_x, screen_w or 1920)
            return _wav(samples, left_vol=lv, right_vol=rv)
        return _wav(samples)
    with _lock:
        if name not in _cache:
            _cache[name] = _wav(_MAKERS[name]())
        return _cache[name]


def _run(name, pitch_shift=None, pan_x=None, screen_w=1920):
    try:
        clip = _clip(
            name,
            pitch_shift=pitch_shift,
            pan_x=pan_x,
            screen_w=screen_w,
            pick_random=True,
        )
        if clip is None:
            return
        if winsound is not None:
            winsound.PlaySound(clip, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
        elif AFPLAY:
            play_wav_bytes(clip)
    except Exception:
        logging.exception("sound playback failed")


def play(name="meow", enabled=True, pitch_shift=None, pan_x=None, screen_w=1920):
    """Play a named clip without blocking the UI, preferring real cat WAV assets."""
    global _last_play_time
    if not (enabled and available() and (name in _MAKERS or name in _REAL_WAV_VARIANTS)):
        return
    now = time.monotonic()
    with _lock:
        if (now - _last_play_time) < MIN_PLAY_GAP_SEC:
            return
        _last_play_time = now
    if (pitch_shift is None or pitch_shift == "auto") and name in _REAL_WAV_VARIANTS:
        pitch_shift = random_pitch_factor(low=0.95, high=1.05)
    elif name == "meow" and pitch_shift is None:
        pitch_shift = random_pitch_factor(low=0.95, high=1.05)
    threading.Thread(
        target=_run, args=(name, pitch_shift, pan_x, screen_w), daemon=True
    ).start()


def available():
    return (winsound is not None and sys.platform == "win32") or bool(AFPLAY)
