"""Kömür ses seti üretici (tekrar üretilebilir).

Gerçek kayıtlardan (assets/miyavlama.mp3, assets/mırrlama.mp3) türetilmiş
varyantlar ve birkaç sentezlenmiş efekt (tıslama, hapşırık, çıtırtı, trill)
üretir; hepsini 22050 Hz / mono / 16-bit WAV olarak assets/ altına yazar.

    python generate_sounds.py            # üret + ölçümleri yazdır + spektrogram
    python generate_sounds.py --check    # yalnızca mevcut WAV'ları doğrula

MP3 çözümleme pygame.mixer (SDL dummy sürücü, ses kartı gerekmez) ile
yapılır; tüm sinyal işleme numpy'dadır. scipy / matplotlib gerekmez.
"""
from __future__ import annotations

import argparse
import math
import os
import struct
import sys
import wave
import zlib

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
PREVIEW_DIR = os.path.join(HERE, "docs", "previews")
SRC_RATE = 44100
OUT_RATE = 22050
SEED = 20261116
PEAK = 0.80

SOURCE_MEOW = "miyavlama.mp3"
SOURCE_PURR = "mırrlama.mp3"

# Ölçüm sınıfları: hangi dosyada hangi objektif kontrol yapılacak.
MEOW_CLASS = {
    "meow_a", "meow_b", "meow_c", "mew_a", "mew_b", "question_a", "question_b",
    "hungry_a", "hungry_b", "sleepy_a", "sleepy_b", "greet_a",
}
HISS_CLASS = {"hiss_a", "hiss_b"}
PURR_CLASS = {"purr_loop", "purr_short", "purr_long"}

# Spektrogram karosu sırası (docs/previews/sounds.png)
PREVIEW_ORDER = [
    "meow_a", "meow_b", "meow_c", "mew_a", "mew_b", "question_a", "question_b",
    "hungry_a", "hungry_b", "sleepy_a", "sleepy_b", "greet_a", "trill_a", "trill_b",
    "purr_loop", "purr_short", "purr_long", "hiss_a", "hiss_b", "growl_hiss",
    "sneeze_a", "sneeze_b", "yawn_a", "yawn_b", "nom_a", "nom_b", "feed_a", "feed_b",
    "pounce_a", "pounce_b",
]


# --------------------------------------------------------------------------
# temel yardımcılar
# --------------------------------------------------------------------------
def load_mp3(name, rate=SRC_RATE):
    """MP3 → float32 mono numpy dizisi (pygame ile çözümlenir)."""
    import pygame
    import pygame.sndarray

    if pygame.mixer.get_init() is None:
        pygame.mixer.init(frequency=rate, size=-16, channels=1, buffer=512)
    snd = pygame.mixer.Sound(os.path.join(ASSETS, name))
    arr = pygame.sndarray.array(snd).astype(np.float32) / 32768.0
    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    return arr


def write_wav(path, x, rate=OUT_RATE):
    x = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0)
    data = (x * 32767.0).astype("<i2").tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data)


def read_wav(path):
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
        ch = w.getnchannels()
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, rate


def fft_filter(x, sr, mask_fn):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    X *= mask_fn(f)
    return np.fft.irfft(X, n)


def highpass(x, sr, fc, order=2):
    return fft_filter(x, sr, lambda f: 1.0 / np.sqrt(1.0 + (fc / np.maximum(f, 1e-6)) ** (2 * order)))


def lowpass(x, sr, fc, order=2):
    return fft_filter(x, sr, lambda f: 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * order)))


def bandpass(x, sr, lo, hi, order=2):
    return lowpass(highpass(x, sr, lo, order), sr, hi, order)


def peak_eq(x, sr, fc, gain_db, width_oct=1.0):
    """Log-frekans ekseninde Gauss biçimli tepe/çukur EQ."""
    g = 10 ** (gain_db / 20.0)

    def mask(f):
        lf = np.log2(np.maximum(f, 1.0) / fc)
        return 1.0 + (g - 1.0) * np.exp(-(lf ** 2) / (2 * (width_oct / 2.355) ** 2))

    return fft_filter(x, sr, mask)


def resample(x, ratio):
    """ratio > 1 → daha tiz ve daha kısa (bant hızı değişimi gibi)."""
    n_out = max(2, int(round(len(x) / ratio)))
    src = np.linspace(0, len(x) - 1, n_out)
    return np.interp(src, np.arange(len(x)), x)


def to_rate(x, sr_in, sr_out):
    if sr_in == sr_out:
        return x.copy()
    y = lowpass(x, sr_in, 0.45 * sr_out, order=8)
    n_out = int(round(len(y) * sr_out / sr_in))
    src = np.linspace(0, len(y) - 1, n_out)
    return np.interp(src, np.arange(len(y)), y)


def time_stretch(x, factor, sr, grain_ms=40.0, search_ms=6.0):
    """WSOLA zaman esnetme: perde sabit, süre × factor."""
    if abs(factor - 1.0) < 1e-3:
        return x.copy()
    N = int(sr * grain_ms / 1000.0)
    N -= N % 2
    half = N // 2
    win = np.hanning(N)
    out_len = int(len(x) * factor)
    out = np.zeros(out_len + N)
    norm = np.zeros(out_len + N)
    search = int(sr * search_ms / 1000.0)
    xp = np.concatenate([x, np.zeros(N + search + 1)])
    prev_in = 0
    k = 0
    while k * half < out_len:
        out_pos = k * half
        in_pos = int(out_pos / factor)
        if k > 0:
            target = xp[prev_in + half: prev_in + half + half]
            best, best_c = in_pos, -np.inf
            for d in range(-search, search + 1, 2):
                c = in_pos + d
                if c < 0:
                    continue
                corr = float(np.dot(xp[c: c + half], target))
                if corr > best_c:
                    best_c, best = corr, c
            in_pos = best
        grain = xp[in_pos: in_pos + N] * win
        out[out_pos: out_pos + N] += grain
        norm[out_pos: out_pos + N] += win
        prev_in = in_pos
        k += 1
    return out[:out_len] / np.maximum(norm[:out_len], 1e-3)


def pitch_shift(x, semitones, sr):
    """Süreyi koruyarak perde kaydırma (resample + WSOLA)."""
    r = 2 ** (semitones / 12.0)
    return time_stretch(resample(x, r), r, sr)


def variable_pitch(x, ratio_fn, extra_len=1.0):
    """Zamanla değişen perde; ratio_fn(t∈[0,1]) → perde çarpanı."""
    probe = ratio_fn(np.linspace(0, 1, 256))
    n_out = max(2, int(len(x) / float(np.mean(probe)) * extra_len))
    t = np.linspace(0, 1, n_out)
    r = ratio_fn(t)
    pos = np.cumsum(r) - r[0]
    pos *= (len(x) - 1) / max(pos[-1], 1e-9)
    return np.interp(pos, np.arange(len(x)), x)


def vibrato(x, sr, rate_hz, depth_semitones, phase=0.0):
    dur = len(x) / sr

    def ratio(t):
        return 2 ** (depth_semitones * np.sin(2 * np.pi * rate_hz * t * dur + phase) / 12.0)

    return variable_pitch(x, ratio)


def fade(x, sr, attack_ms=8.0, release_ms=8.0, curve="lin"):
    y = x.copy()
    a = min(len(y) // 2, int(sr * attack_ms / 1000.0))
    r = min(len(y) // 2, int(sr * release_ms / 1000.0))
    if a > 0:
        ramp = np.linspace(0, 1, a)
        if curve == "sin":
            ramp = np.sin(ramp * np.pi / 2)
        y[:a] *= ramp
    if r > 0:
        ramp = np.linspace(1, 0, r)
        if curve == "sin":
            ramp = np.sin(ramp * np.pi / 2)
        y[-r:] *= ramp
    return y


def finalize(x, sr, peak=PEAK, edge_ms=8.0):
    y = np.asarray(x, dtype=np.float64)
    y = y - y.mean()
    y = fade(y, sr, edge_ms, edge_ms)
    m = float(np.max(np.abs(y)))
    if m > 1e-9:
        y *= peak / m
    return y


def silence(sr, seconds):
    return np.zeros(int(sr * seconds))


def concat(sr, *parts, gap=0.0):
    out = []
    for i, p in enumerate(parts):
        if i and gap:
            out.append(silence(sr, gap))
        out.append(p)
    return np.concatenate(out)


def crossfade_join(a, b, sr, ms=30.0):
    n = min(len(a), len(b), int(sr * ms / 1000.0))
    if n <= 0:
        return np.concatenate([a, b])
    t = np.linspace(0, 1, n)
    fi, fo = np.sin(t * np.pi / 2), np.cos(t * np.pi / 2)
    mid = a[-n:] * fo + b[:n] * fi
    return np.concatenate([a[:-n], mid, b[n:]])


def env_adsr(n, sr, attack, decay, sustain, release):
    t = np.arange(n) / sr
    total = n / sr
    e = np.ones(n) * sustain
    a = attack
    d = decay
    e[t < a] = t[t < a] / max(a, 1e-9)
    m = (t >= a) & (t < a + d)
    e[m] = 1.0 - (1.0 - sustain) * (t[m] - a) / max(d, 1e-9)
    rel = t > total - release
    e[rel] *= np.clip((total - t[rel]) / max(release, 1e-9), 0, 1)
    return e


def synth_voiced(sr, dur, f0_fn, harmonics):
    """Toplamsal harmonik sentez; f0_fn(t∈[0,1]) → Hz."""
    n = int(sr * dur)
    t = np.linspace(0, 1, n, endpoint=False)
    f0 = f0_fn(t)
    phase = 2 * np.pi * np.cumsum(f0) / sr
    out = np.zeros(n)
    for k, amp in enumerate(harmonics, start=1):
        out += amp * np.sin(k * phase)
    return out


# --------------------------------------------------------------------------
# kaynak kesitleri
# --------------------------------------------------------------------------
def extract_meow(m, sr):
    """Kayıttaki tek temiz miyav (≈1.95–2.55 s). Gürültü/vınlama temizlenir."""
    seg = m[int(1.93 * sr): int(2.60 * sr)]
    seg = highpass(seg, sr, 180, order=3)
    seg = lowpass(seg, sr, 9000, order=4)
    seg = peak_eq(seg, sr, 2600, 1.5, 1.2)     # hafif "presence"
    seg = fade(seg, sr, 12, 60)
    return seg - seg.mean()


def extract_purr_loop(p, sr, loop_s=3.0, xfade_s=0.25):
    """Kayıttan en dengeli pencereyi seçer, eşit-güç çapraz geçişle döngü yapar."""
    p = highpass(p, sr, 40, order=2)
    p = lowpass(p, sr, 6000, order=4)
    hop = sr // 100
    env = np.array([np.sqrt(np.mean(p[i:i + hop] ** 2)) for i in range(0, len(p) - hop, hop)])
    win_frames = int(loop_s * 100)
    need = int((loop_s + xfade_s) * sr)
    best, best_cv = 0, np.inf
    for start in range(0, len(env) - win_frames - int(xfade_s * 100), 10):
        w = env[start: start + win_frames]
        mean = w.mean()
        if mean < np.percentile(env, 35):
            continue
        cv = w.std() / max(mean, 1e-9)
        if cv < best_cv:
            best_cv, best = cv, start
    s0 = best * hop
    seg = p[s0: s0 + need]
    L = int(loop_s * sr)
    X = int(xfade_s * sr)
    t = np.linspace(0, 1, X)
    fi, fo = np.sin(t * np.pi / 2), np.cos(t * np.pi / 2)
    loop = seg[:L].copy()
    loop[:X] = seg[:X] * fi + seg[L: L + X] * fo
    loop -= loop.mean()
    return loop, best / 100.0, best_cv


def tile_loop(loop, seconds, sr):
    reps = int(math.ceil(seconds * sr / len(loop))) + 1
    return np.tile(loop, reps)[: int(seconds * sr)]


# --------------------------------------------------------------------------
# sentezler
# --------------------------------------------------------------------------
def synth_trill(sr, rng, dur=0.30, f_start=480, f_end=820, am_hz=27.0):
    f0 = lambda t: f_start * (f_end / f_start) ** (t ** 0.8)
    x = synth_voiced(sr, dur, f0, [1.0, 0.65, 0.4, 0.22, 0.12, 0.06])
    n = len(x)
    t = np.arange(n) / sr
    am = 1.0 - 0.75 * (0.5 + 0.5 * np.cos(2 * np.pi * am_hz * t)) * np.clip(1.6 - 2.2 * t / dur, 0, 1)
    x *= am
    x = peak_eq(x, sr, 1100, 4.0, 0.8)
    x = peak_eq(x, sr, 2600, 3.0, 0.8)
    breath = bandpass(rng.standard_normal(n), sr, 2000, 6000, 2) * 0.04
    x = x + breath * (1 + 0.5 * np.sin(2 * np.pi * am_hz * t))
    x *= env_adsr(n, sr, 0.015, 0.05, 0.85, 0.07)
    return x


def synth_hiss(sr, rng, dur=0.8, spit=True):
    n = int(sr * dur)
    t = np.arange(n) / sr
    noise = rng.standard_normal(n)
    body = bandpass(noise, sr, 2000, 8000, order=3)
    body = peak_eq(body, sr, 4500, 3.0, 1.0)
    env = env_adsr(n, sr, 0.012, 0.08, 0.8, dur * 0.28)
    trem = 1.0 + 0.12 * np.sin(2 * np.pi * 9.0 * t) + 0.06 * rng.standard_normal(n)
    x = body * env * trem
    if spit:
        burst_n = int(0.035 * sr)
        burst = bandpass(rng.standard_normal(burst_n), sr, 1000, 9000, 2)
        burst *= np.exp(-np.arange(burst_n) / (0.010 * sr)) * 2.4
        x[:burst_n] += burst
    return x


def synth_growl(sr, rng, dur=0.45, f0=55.0):
    n = int(sr * dur)
    t = np.arange(n) / sr
    f = f0 * (1 + 0.08 * np.sin(2 * np.pi * 3 * t))
    phase = 2 * np.pi * np.cumsum(f) / sr
    x = np.zeros(n)
    for k in range(1, 28):
        x += np.sin(k * phase) / k
    pulse = 0.5 + 0.5 * np.cos(phase)
    noise = bandpass(rng.standard_normal(n), sr, 300, 1500, 2) * pulse * 0.5
    x = lowpass(x + noise, sr, 1800, 3)
    x *= env_adsr(n, sr, 0.06, 0.1, 0.9, 0.1)
    return x


def synth_sneeze(sr, rng, variant=0):
    dur = 0.30 if variant == 0 else 0.26
    n = int(sr * dur)
    t = np.arange(n) / sr
    x = np.zeros(n)
    # nefes alma
    inh_n = int(0.045 * sr)
    inh = bandpass(rng.standard_normal(inh_n), sr, 3000, 7000, 2) * np.linspace(0, 1, inh_n) ** 2 * 0.25
    x[:inh_n] += inh
    # patlama
    b0 = int(0.05 * sr)
    bn = int(0.11 * sr)
    burst = bandpass(rng.standard_normal(bn), sr, 700, 6500, 2)
    burst *= np.exp(-np.arange(bn) / (0.032 * sr)) * 1.0
    x[b0: b0 + bn] += burst
    # minik cıyak
    s0 = int(0.068 * sr)
    sn = int(0.07 * sr)
    f_hi, f_lo = (2300, 1400) if variant == 0 else (2600, 1700)
    sq = synth_voiced(sr, sn / sr, lambda u: f_hi * (f_lo / f_hi) ** u, [1.0, 0.35, 0.15])
    sq *= env_adsr(sn, sr, 0.004, 0.02, 0.6, 0.03) * 0.35
    x[s0: s0 + sn] += sq
    # gövde "tuk"
    th = np.sin(2 * np.pi * 120 * t) * np.exp(-np.maximum(t - 0.05, 0) / 0.03) * (t > 0.05) * 0.3
    x += th
    return x


def synth_nom(sr, rng, pattern):
    """pattern: [(zaman_s, genlik)] çıtırtı listesi."""
    dur = pattern[-1][0] + 0.12
    n = int(sr * dur)
    x = np.zeros(n)
    for t0, amp in pattern:
        s0 = int(t0 * sr)
        cn = int(0.07 * sr)
        crunch = bandpass(rng.standard_normal(cn), sr, 900, 4500, 2)
        crunch *= np.exp(-np.arange(cn) / (0.016 * sr))
        # ikinci küçük çıtırtı (kırılma)
        c2 = int(0.022 * sr)
        crunch[c2:] += bandpass(rng.standard_normal(cn - c2), sr, 1500, 6000, 2) \
            * np.exp(-np.arange(cn - c2) / (0.008 * sr)) * 0.6
        thump = np.sin(2 * np.pi * 140 * np.arange(cn) / sr) * np.exp(-np.arange(cn) / (0.025 * sr)) * 0.35
        x[s0: s0 + cn] += (crunch + thump) * amp
    return x


def synth_pounce(sr, rng, variant=0):
    dur = 0.32
    n = int(sr * dur)
    whoosh_n = int(0.14 * sr)
    whoosh = bandpass(rng.standard_normal(whoosh_n), sr, 300, 2500, 2)
    whoosh *= np.sin(np.linspace(0, np.pi, whoosh_n)) ** 2 * 0.5
    x = np.zeros(n)
    x[:whoosh_n] += whoosh
    t0 = 0.12 if variant == 0 else 0.10
    th_n = n - int(t0 * sr)
    tt = np.arange(th_n) / sr
    f = 95 * np.exp(-tt / 0.08) + 45
    phase = 2 * np.pi * np.cumsum(f) / sr
    thump = np.sin(phase) * np.exp(-tt / 0.07)
    click = bandpass(rng.standard_normal(th_n), sr, 800, 5000, 2) * np.exp(-tt / 0.006) * 0.6
    x[int(t0 * sr):] += thump + click
    return x


# --------------------------------------------------------------------------
# set üretimi
# --------------------------------------------------------------------------
def build_all(sr=SRC_RATE):
    rng = np.random.default_rng(SEED)
    m = load_mp3(SOURCE_MEOW, sr)
    p = load_mp3(SOURCE_PURR, sr)
    meow = extract_meow(m, sr)
    purr_loop, purr_start, purr_cv = extract_purr_loop(p, sr)
    print(f"purr loop window start={purr_start:.2f}s cv={purr_cv:.3f}")

    out = {}

    # --- miyavlar (gerçek kayıttan) ---
    out["meow_a"] = meow
    out["meow_b"] = resample(meow, 2 ** (1.5 / 12))
    out["meow_c"] = vibrato(time_stretch(resample(meow, 2 ** (-1.0 / 12)), 1.1, sr), sr, 5.5, 0.35)

    head = meow[: int(0.30 * sr)]
    out["mew_a"] = fade(resample(head, 2 ** (4.0 / 12)), sr, 5, 60)
    out["mew_b"] = fade(resample(meow[: int(0.34 * sr)], 2 ** (2.5 / 12)), sr, 5, 80)

    q_body = time_stretch(meow, 1.15, sr)
    q_a = variable_pitch(q_body, lambda t: 2 ** ((-1.0 + 7.0 * t ** 1.4) / 12))
    trill_pre = synth_trill(sr, rng, dur=0.14, f_start=420, f_end=520, am_hz=28) * 0.5
    out["question_a"] = crossfade_join(trill_pre, q_a, sr, 25)
    out["question_b"] = variable_pitch(meow, lambda t: 2 ** ((0.0 + 4.5 * t ** 1.2) / 12))

    h1 = vibrato(time_stretch(resample(meow, 2 ** (-1.0 / 12)), 1.55, sr), sr, 6.0, 0.4)
    h2 = time_stretch(resample(meow, 2 ** (1.0 / 12)), 1.3, sr)
    out["hungry_a"] = concat(sr, h1, h2, gap=0.16)
    out["hungry_b"] = vibrato(time_stretch(resample(meow, 2 ** (0.5 / 12)), 1.8, sr), sr, 5.0, 0.3)

    s1 = lowpass(time_stretch(resample(meow, 2 ** (-3.0 / 12)), 1.35, sr), sr, 2600, 2)
    out["sleepy_a"] = fade(s1, sr, 80, 120, "sin")
    s2 = lowpass(time_stretch(resample(meow, 2 ** (-4.0 / 12)), 1.2, sr), sr, 2200, 2)
    out["sleepy_b"] = fade(s2, sr, 100, 150, "sin")

    # --- trill / cıvıltı ---
    out["trill_a"] = synth_trill(sr, rng, 0.30, 480, 820, 27.0)
    out["trill_b"] = synth_trill(sr, rng, 0.26, 520, 950, 30.0)
    out["greet_a"] = concat(sr, out["trill_b"] * 0.8, resample(meow[: int(0.36 * sr)], 2 ** (2.0 / 12)), gap=0.04)

    # --- mırlama ---
    out["purr_loop"] = purr_loop
    out["purr_short"] = fade(tile_loop(purr_loop, 1.6, sr), sr, 150, 400, "sin")
    out["purr_long"] = fade(tile_loop(purr_loop, 4.0, sr), sr, 300, 700, "sin")

    # --- tıslama / hırlama ---
    out["hiss_a"] = synth_hiss(sr, rng, 0.80)
    out["hiss_b"] = synth_hiss(sr, rng, 0.95)
    out["growl_hiss"] = crossfade_join(synth_growl(sr, rng, 0.45) * 0.9, synth_hiss(sr, rng, 0.7, spit=False), sr, 60)

    # --- hapşırık ---
    out["sneeze_a"] = synth_sneeze(sr, rng, 0)
    out["sneeze_b"] = synth_sneeze(sr, rng, 1)

    # --- esneme (inen yumuşak cıyak, gerçek miyavdan) ---
    def yawn(stretch, st_from, st_to, lp):
        base = time_stretch(meow, stretch, sr)
        y = variable_pitch(base, lambda t: 2 ** ((st_from + (st_to - st_from) * t ** 0.9) / 12))
        y = lowpass(y, sr, lp, 2)
        breath = bandpass(rng.standard_normal(len(y)), sr, 500, 3000, 2) * 0.07
        y = y + breath * env_adsr(len(y), sr, 0.2, 0.1, 0.6, 0.3)
        return fade(y, sr, 120, 200, "sin")

    out["yawn_a"] = yawn(1.6, 1.0, -5.0, 3000)
    out["yawn_b"] = yawn(1.4, 2.0, -4.0, 3400)

    # --- yeme ---
    out["nom_a"] = synth_nom(sr, rng, [(0.0, 1.0), (0.15, 0.7), (0.27, 0.9), (0.43, 0.6)])
    out["nom_b"] = synth_nom(sr, rng, [(0.0, 0.8), (0.12, 1.0), (0.30, 0.65), (0.41, 0.85), (0.55, 0.5)])
    purr_tail = fade(tile_loop(purr_loop, 1.1, sr), sr, 200, 400, "sin") * 0.6
    out["feed_a"] = concat(sr, out["nom_a"], purr_tail, gap=0.08)
    out["feed_b"] = concat(sr, out["nom_b"], purr_tail, gap=0.06)

    # --- atlama ---
    out["pounce_a"] = synth_pounce(sr, rng, 0)
    out["pounce_b"] = synth_pounce(sr, rng, 1)

    # --- ölçeklendir, örnekleme oranına indir, finalize ---
    quiet = {"sleepy_a": 0.55, "sleepy_b": 0.5, "yawn_a": 0.6, "yawn_b": 0.6,
             "purr_loop": 0.7, "purr_short": 0.7, "purr_long": 0.7, "nom_a": 0.7, "nom_b": 0.7,
             "feed_a": 0.7, "feed_b": 0.7, "pounce_a": 0.75, "pounce_b": 0.75}
    final = {}
    for name, x in out.items():
        y = to_rate(x, sr, OUT_RATE)
        edge = 0.0 if name == "purr_loop" else 8.0
        final[name] = finalize(y, OUT_RATE, quiet.get(name, PEAK), edge)
    return final


# --------------------------------------------------------------------------
# objektif ölçümler
# --------------------------------------------------------------------------
def spectral_centroid(x, sr):
    S = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1.0 / sr)
    return float((S * f).sum() / max(S.sum(), 1e-12))


def pitch_track(x, sr, lo=300, hi=1500, win_ms=40, hop_ms=10):
    """Sesli çerçevelerin otokorelasyon perdesi (Hz listesi)."""
    y = highpass(x, sr, 150, 2)
    N = int(sr * win_ms / 1000)
    H = int(sr * hop_ms / 1000)
    out = []
    lag_lo, lag_hi = int(sr / hi), int(sr / lo)
    for s in range(0, len(y) - N, H):
        seg = y[s: s + N]
        rms = np.sqrt(np.mean(seg ** 2))
        if rms < 0.03:
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, "full")[N - 1:]
        if ac[0] <= 0:
            continue
        k = lag_lo + int(np.argmax(ac[lag_lo:lag_hi]))
        if ac[k] / ac[0] < 0.3:
            continue
        out.append(sr / k)
    return out


def am_rate(x, sr, lo=15.0, hi=45.0):
    hop = max(1, sr // 1000)
    env = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x) - hop, hop)])
    env = env - env.mean()
    S = np.abs(np.fft.rfft(env * np.hanning(len(env))))
    f = np.fft.rfftfreq(len(env), hop / sr)
    band = (f >= lo) & (f <= hi)
    return float(f[band][np.argmax(S[band])])


def loop_seam(x, sr, ms=20.0):
    n = int(sr * ms / 1000)
    seam = np.concatenate([x[-n:], x[:n]])
    body = x[len(x) // 2 - n: len(x) // 2 + n]
    d = np.abs(np.diff(seam)).max()
    body_d = np.abs(np.diff(body)).max()
    return float(d), float(body_d), float(np.sqrt(np.mean(seam ** 2)) / max(np.sqrt(np.mean(x ** 2)), 1e-9))


def measure(name, x, sr):
    info = {
        "dur": len(x) / sr,
        "rms": float(np.sqrt(np.mean(x ** 2))),
        "peak": float(np.max(np.abs(x))),
        "dc": float(x.mean()),
        "centroid": spectral_centroid(x, sr),
    }
    if name in MEOW_CLASS or name.startswith("yawn"):
        pt = pitch_track(x, sr)
        info["f0_med"] = float(np.median(pt)) if pt else 0.0
        info["f0_min"] = float(min(pt)) if pt else 0.0
        info["f0_max"] = float(max(pt)) if pt else 0.0
    if name in PURR_CLASS:
        info["am_hz"] = am_rate(x, sr)
    if name == "purr_loop":
        info["seam"] = loop_seam(x, sr)
    return info


def check(files):
    problems = []
    rows = []
    for name, (x, sr) in files.items():
        i = measure(name, x, sr)
        rows.append((name, i))
        if i["peak"] >= 0.98:
            problems.append(f"{name}: clipping (peak {i['peak']:.3f})")
        if abs(i["dc"]) > 0.005:
            problems.append(f"{name}: DC offset {i['dc']:.4f}")
        if i["rms"] < 0.02:
            problems.append(f"{name}: too quiet (rms {i['rms']:.3f})")
        if name in HISS_CLASS and i["centroid"] < 3000:
            problems.append(f"{name}: hiss centroid {i['centroid']:.0f} < 3000")
        if name in MEOW_CLASS and not (400 <= i["f0_med"] <= 1200):
            problems.append(f"{name}: meow f0 median {i['f0_med']:.0f} outside 400-1200")
        if name in PURR_CLASS and not (22 <= i["am_hz"] <= 32):
            problems.append(f"{name}: purr AM {i['am_hz']:.1f} Hz outside 22-32")
        if name == "purr_loop":
            d, body_d, ratio = i["seam"]
            if d > 2.5 * body_d or not (0.5 <= ratio <= 1.6):
                problems.append(f"{name}: loop seam discontinuity {d:.3f} vs body {body_d:.3f}, rms ratio {ratio:.2f}")
    total = sum(os.path.getsize(os.path.join(ASSETS, n + ".wav")) for n in files)
    print(f"{'name':12} {'dur':>5} {'rms':>6} {'peak':>5} {'dc':>7} {'centr':>6}  extra")
    for name, i in rows:
        extra = ""
        if "f0_med" in i:
            extra += f"f0 med={i['f0_med']:.0f} [{i['f0_min']:.0f}-{i['f0_max']:.0f}] "
        if "am_hz" in i:
            extra += f"AM={i['am_hz']:.1f}Hz "
        if "seam" in i:
            extra += f"seam d={i['seam'][0]:.3f}/{i['seam'][1]:.3f} r={i['seam'][2]:.2f}"
        print(f"{name:12} {i['dur']:5.2f} {i['rms']:6.3f} {i['peak']:5.2f} {i['dc']:+7.4f} {i['centroid']:6.0f}  {extra}")
    print(f"total wav bytes: {total} ({total / 1024:.0f} KB)")
    if problems:
        print("PROBLEMS:")
        for pr in problems:
            print("  -", pr)
    else:
        print("all checks passed")
    return problems


# --------------------------------------------------------------------------
# spektrogram PNG (matplotlib gerekmez)
# --------------------------------------------------------------------------
def _png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


def _colormap(v):
    """0..1 → RGB (koyu mavi → mor → turuncu → sarı)."""
    stops = np.array([[10, 10, 40], [70, 20, 110], [190, 60, 90], [245, 150, 40], [255, 240, 150]], dtype=float)
    pos = np.array([0.0, 0.3, 0.55, 0.8, 1.0])
    v = np.clip(v, 0, 1)
    out = np.zeros(v.shape + (3,))
    for c in range(3):
        out[..., c] = np.interp(v, pos, stops[:, c])
    return out.astype(np.uint8)


def spectrogram_tile(x, sr, width=220, height=120, fmax=9000):
    N = 512
    H = max(1, len(x) // width)
    frames = []
    win = np.hanning(N)
    for s in range(0, max(1, len(x) - N), H):
        seg = x[s: s + N]
        if len(seg) < N:
            seg = np.pad(seg, (0, N - len(seg)))
        frames.append(np.abs(np.fft.rfft(seg * win)))
    S = np.array(frames).T  # (freq, time)
    f = np.fft.rfftfreq(N, 1.0 / sr)
    S = S[f <= fmax]
    S = 20 * np.log10(S + 1e-6)
    S = (S - (-40)) / (S.max() - (-40) + 1e-9)
    ti = np.linspace(0, S.shape[1] - 1, width)
    fi = np.linspace(0, S.shape[0] - 1, height)
    S = S[np.round(fi).astype(int)][:, np.round(ti).astype(int)]
    return _colormap(S[::-1])


def save_preview(files, path):
    cols = 5
    names = [n for n in PREVIEW_ORDER if n in files]
    tw, th, pad = 220, 120, 6
    rows = int(math.ceil(len(names) / cols))
    img = np.zeros((rows * (th + pad) + pad, cols * (tw + pad) + pad, 3), dtype=np.uint8) + 30
    for idx, name in enumerate(names):
        r, c = divmod(idx, cols)
        x, sr = files[name]
        tile = spectrogram_tile(x, sr, tw, th)
        y0 = pad + r * (th + pad)
        x0 = pad + c * (tw + pad)
        img[y0: y0 + th, x0: x0 + tw] = tile
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _png(path, img)
    with open(os.path.splitext(path)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write("Spektrogram karoları (soldan sağa, yukarıdan aşağıya; 5 sütun):\n")
        for idx, name in enumerate(names):
            r, c = divmod(idx, cols)
            f.write(f"satır {r + 1} sütun {c + 1}: {name}\n")
    print("preview:", path)


# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="yalnızca mevcut dosyaları doğrula")
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args(argv)

    if args.check:
        files = {}
        for name in PREVIEW_ORDER:
            path = os.path.join(ASSETS, name + ".wav")
            if os.path.exists(path):
                files[name] = read_wav(path)
    else:
        built = build_all()
        os.makedirs(ASSETS, exist_ok=True)
        for name, x in built.items():
            write_wav(os.path.join(ASSETS, name + ".wav"), x, OUT_RATE)
        files = {name: read_wav(os.path.join(ASSETS, name + ".wav")) for name in built}
        print(f"{len(files)} wav yazıldı → {ASSETS}")

    problems = check(files)
    if not args.no_preview and files:
        save_preview(files, os.path.join(PREVIEW_DIR, "sounds.png"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
