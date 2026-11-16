"""Gelişmiş kedi ses sentezi. winsound üzerinden oynatılır, stdlib-only.

Her klip tek seferlik üretilir, bellekte önbelleğe alınır ve UI'ı bloklamadan
bir daemon thread üzerinden oynatılır. Hiçbir ses dosyası paketlenmez.
"""
from __future__ import annotations

import io
import logging
import math
import random
import struct
import sys
import threading
import wave

try:
    import winsound  # type: ignore
except Exception:  # pragma: no cover - non-Windows
    winsound = None

RATE = 22050
_cache = {}
_lock = threading.Lock()


def _wav(samples):
    """16-bit mono WAV bytes from a list of float samples in [-1, 1]."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
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
}


def _clip(name):
    with _lock:
        if name not in _cache:
            if name not in _MAKERS:
                return None
            _cache[name] = _wav(_MAKERS[name]())
        return _cache[name]


def _run(name):
    try:
        clip = _clip(name)
        if clip is None or winsound is None:
            return
        winsound.PlaySound(clip, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
    except Exception:
        logging.exception("sound playback failed")


def play(name="meow", enabled=True):
    """Play a named clip without blocking the UI."""
    if not (enabled and winsound and name in _MAKERS):
        return
    threading.Thread(target=_run, args=(name,), daemon=True).start()


def available():
    return winsound is not None and sys.platform == "win32"
