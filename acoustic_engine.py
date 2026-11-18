"""Dilim 3: Akustik motor, 2D konumsal ses, dinamik mırıldanma, pitch-shift,
yüzeye göre adım sesi, klavye reaktif sesleri, doğal Türkçe TTS,
lofi odak ambiyansı ve mikrofon gürültüsü tepki sistemi.
"""
from __future__ import annotations

import asyncio
import io
import logging
import math
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile
import threading
import time
from typing import Callable, Iterable, Sequence
import wave

try:
    import pygame.mixer  # type: ignore
except Exception:  # pragma: no cover
    pygame = None  # type: ignore

SAMPLE_RATE = 22050
PURR_MIN_FREQ = 24.0
PURR_MAX_FREQ = 34.0
PURR_MIN_VOL = 0.2
PURR_MAX_VOL = 0.9

EDGE_TTS_VOICES = ("tr-TR-EmelNeural", "tr-TR-AhmetNeural")
DEFAULT_EDGE_VOICE = "tr-TR-EmelNeural"
DEFAULT_EDGE_PITCH = "+15Hz"

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ---------------------------------------------------------------------------
# WAV Yardımcıları (stdlib-only)
# ---------------------------------------------------------------------------

def samples_to_wav(
    samples: Sequence[float],
    sample_rate: int = SAMPLE_RATE,
    channels: int = 1,
) -> bytes:
    """Float örnek dizisinden ([-1, 1]) 16-bit PCM WAV baytları üretir."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        packed = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000))
            for s in samples
        )
        w.writeframes(packed)
    return buf.getvalue()


def stereo_samples_to_wav(
    left_samples: Sequence[float],
    right_samples: Sequence[float],
    sample_rate: int = SAMPLE_RATE,
) -> bytes:
    """Sol ve sağ kanal dizilerinden 16-bit stereo PCM WAV baytları üretir."""
    n = min(len(left_samples), len(right_samples))
    interleaved: list[float] = []
    for i in range(n):
        interleaved.append(left_samples[i])
        interleaved.append(right_samples[i])
    return samples_to_wav(interleaved, sample_rate=sample_rate, channels=2)


def wav_to_channels(wav_bytes: bytes) -> tuple[list[list[float]], int]:
    """16-bit PCM WAV baytlarını kanal başına float örnek listelerine çözer."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        framerate = w.getframerate()
        raw = w.readframes(w.getnframes())
    if sampwidth != 2:
        raise ValueError(f"Desteklenmeyen örnekleme genişliği: {sampwidth}")
    total_samples = len(raw) // 2
    unpacked = struct.unpack(f"<{total_samples}h", raw)
    channels: list[list[float]] = [[] for _ in range(n_channels)]
    for idx, val in enumerate(unpacked):
        channels[idx % n_channels].append(val / 32768.0)
    return channels, framerate


def _adsr_envelope(
    n: int,
    attack: float = 0.02,
    decay: float = 0.1,
    sustain: float = 0.7,
    release: float = 0.15,
) -> list[float]:
    out: list[float] = []
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


# ---------------------------------------------------------------------------
# 1. 2D Konumsal Ses (Spatial Pan)
# ---------------------------------------------------------------------------

def pan_volumes(
    cat_x: float,
    screen_w: float,
    master_vol: float = 1.0,
) -> tuple[float, float]:
    """Kedinin X konumuna ve ekran genişliğine göre (left_vol, right_vol) hesaplar.

    Sabit güçlü (equal-power) stereo pan yasası kullanır:
    - En solda (cat_x=0): (master_vol, 0.0)
    - Ortada (cat_x=screen_w/2): (0.707*master_vol, 0.707*master_vol)
    - En sağda (cat_x=screen_w): (0.0, master_vol)
    """
    vol = max(0.0, min(1.0, float(master_vol)))
    if screen_w <= 0:
        half = round(vol * math.sqrt(0.5), 6)
        return (half, half)
    pos = max(0.0, min(1.0, float(cat_x) / float(screen_w)))
    angle = pos * (math.pi / 2.0)
    left = round(math.cos(angle) * vol, 6)
    right = round(math.sin(angle) * vol, 6)
    return (left, right)


def apply_channel_pan(
    channel,
    cat_x: float,
    screen_w: float,
    master_vol: float = 1.0,
) -> tuple[float, float]:
    """pygame.mixer.Channel üzerinde 2D stereo pan uygular."""
    left, right = pan_volumes(cat_x, screen_w, master_vol)
    if channel is not None:
        channel.set_volume(left, right)
    return (left, right)


def pan_wav_stereo(
    wav_bytes: bytes,
    cat_x: float,
    screen_w: float,
    master_vol: float = 1.0,
) -> bytes:
    """Mono veya stereo WAV verisine 2D X-ekseni stereo pan uygular."""
    left_gain, right_gain = pan_volumes(cat_x, screen_w, master_vol)
    channels, framerate = wav_to_channels(wav_bytes)
    if len(channels) == 1:
        mono = channels[0]
        left = [s * left_gain for s in mono]
        right = [s * right_gain for s in mono]
    else:
        left = [s * left_gain for s in channels[0]]
        right = [s * right_gain for s in channels[1]]
    return stereo_samples_to_wav(left, right, sample_rate=framerate)


# ---------------------------------------------------------------------------
# 2. Dinamik Mırıldanma (Dynamic Purr)
# ---------------------------------------------------------------------------

def compute_purr_params(
    pointer_speed: float,
    max_speed: float = 1500.0,
) -> tuple[float, float]:
    """Fare hızına göre mırıldanma frekansını (24Hz->34Hz) ve sesini (0.2->0.9) hesaplar."""
    if max_speed <= 0:
        ratio = 0.0
    else:
        ratio = max(0.0, min(1.0, float(pointer_speed) / float(max_speed)))
    freq = PURR_MIN_FREQ + (PURR_MAX_FREQ - PURR_MIN_FREQ) * ratio
    volume = PURR_MIN_VOL + (PURR_MAX_VOL - PURR_MIN_VOL) * ratio
    return (round(freq, 4), round(volume, 4))


def generate_dynamic_purr_samples(
    freq: float = 26.0,
    volume: float = 0.5,
    duration: float = 0.5,
    sample_rate: int = SAMPLE_RATE,
) -> list[float]:
    """Verilen temel frekans ve şiddette dinamik kedi mırıldanması örnekleri üretir."""
    rng = random.Random(3)
    n = max(1, int(sample_rate * duration))
    out: list[float] = []
    low = 0.0
    env = _adsr_envelope(n, attack=0.05, decay=0.15, sustain=1.0, release=0.25)
    vol = max(0.0, min(1.0, float(volume)))
    for i in range(n):
        t = i / sample_rate
        low = 0.92 * low + 0.08 * rng.uniform(-1.0, 1.0)
        pulse = 0.5 + 0.5 * math.sin(2.0 * math.pi * freq * t)
        harmonic = 0.25 * math.sin(2.0 * math.pi * (freq * 2.0) * t)
        sample = env[i] * pulse * (2.2 * low + harmonic) * vol
        out.append(max(-1.0, min(1.0, sample)))
    return out


def synthesize_dynamic_purr(
    pointer_speed: float = 0.0,
    duration: float = 0.5,
    sample_rate: int = SAMPLE_RATE,
    max_speed: float = 1500.0,
) -> bytes:
    """Fare hızına bağlı dinamik mırıldanma WAV verisi üretir."""
    freq, volume = compute_purr_params(pointer_speed, max_speed=max_speed)
    samples = generate_dynamic_purr_samples(
        freq=freq,
        volume=volume,
        duration=duration,
        sample_rate=sample_rate,
    )
    return samples_to_wav(samples, sample_rate=sample_rate)


class DynamicPurrController:
    """Fareyle sevme hızına göre mırıldanma frekansı ve ses seviyesini yönetir."""

    def __init__(self, max_speed: float = 1500.0, smoothing: float = 0.35):
        self.max_speed = max_speed
        self.smoothing = max(0.05, min(1.0, float(smoothing)))
        self.smoothed_speed = 0.0
        self.freq = PURR_MIN_FREQ
        self.volume = 0.0
        self.active = False

    def update(self, pointer_speed: float, petting: bool = True) -> dict:
        if not petting:
            self.active = False
            self.smoothed_speed = 0.0
            self.freq = PURR_MIN_FREQ
            self.volume = 0.0
            return {"active": False, "freq": self.freq, "volume": self.volume}

        speed = max(0.0, float(pointer_speed))
        if not self.active:
            self.smoothed_speed = speed
        else:
            self.smoothed_speed = (
                (1.0 - self.smoothing) * self.smoothed_speed
                + self.smoothing * speed
            )
        self.active = True
        self.freq, self.volume = compute_purr_params(
            self.smoothed_speed, max_speed=self.max_speed
        )
        return {"active": True, "freq": self.freq, "volume": self.volume}

    def synthesize(self, duration: float = 0.5, sample_rate: int = SAMPLE_RATE) -> bytes:
        vol = self.volume if self.active else PURR_MIN_VOL
        samples = generate_dynamic_purr_samples(
            freq=self.freq,
            volume=vol,
            duration=duration,
            sample_rate=sample_rate,
        )
        return samples_to_wav(samples, sample_rate=sample_rate)

    def stop(self) -> None:
        self.update(0.0, petting=False)


# ---------------------------------------------------------------------------
# 3. Miyav Pitch-Shift (%5-%10 Doğal Varyasyon)
# ---------------------------------------------------------------------------

def random_pitch_factor(
    rng: random.Random | None = None,
    low: float = 0.90,
    high: float = 1.10,
) -> float:
    """Tekdüzeliği kırmak için [0.90, 1.10] aralığında rastgele perde çarpanı döndürür."""
    generator = rng if rng is not None else random
    return float(generator.uniform(low, high))


def pitch_shift_samples(samples: Sequence[float], factor: float) -> list[float]:
    """Doğrusal enterpolasyon ile örnekleme/perde kaydırma uygular."""
    f = float(factor)
    if f <= 0.0:
        raise ValueError("pitch_shift çarpanı pozitif olmalıdır")
    n = len(samples)
    if n < 2 or abs(f - 1.0) < 1e-6:
        return list(samples)
    new_len = max(1, int(round(n / f)))
    out: list[float] = []
    last_idx = n - 1
    for i in range(new_len):
        pos = i * f
        idx = int(pos)
        if idx >= last_idx:
            out.append(float(samples[last_idx]))
        else:
            frac = pos - idx
            s0 = float(samples[idx])
            s1 = float(samples[idx + 1])
            out.append(s0 + (s1 - s0) * frac)
    return out


def pitch_shift_wav(wav_bytes: bytes, factor: float) -> bytes:
    """16-bit PCM WAV verisine perde kaydırma uygular (orijinal örnekleme hızını korur)."""
    f = float(factor)
    if f <= 0.0:
        raise ValueError("pitch_shift çarpanı pozitif olmalıdır")
    if abs(f - 1.0) < 1e-6:
        return wav_bytes
    channels, framerate = wav_to_channels(wav_bytes)
    shifted = [pitch_shift_samples(ch, f) for ch in channels]
    if len(shifted) == 1:
        return samples_to_wav(shifted[0], sample_rate=framerate, channels=1)
    return stereo_samples_to_wav(shifted[0], shifted[1], sample_rate=framerate)


# ---------------------------------------------------------------------------
# 4. Yüzeye Göre Adım Sesi (Window vs Desktop)
# ---------------------------------------------------------------------------

def step_sound_name(surface: str) -> str:
    """Yüzey adına göre adım sesi kimliğini döndürür."""
    norm = str(surface or "").strip().lower()
    if norm in ("window", "step_window", "pencere"):
        return "step_window"
    return "step_desktop"


def generate_step_window_samples(
    duration: float = 0.055,
    sample_rate: int = SAMPLE_RATE,
) -> list[float]:
    """Pencere üstünde yürüme: yüksek frekanslı kısa tık-tık sesi."""
    rng = random.Random(11)
    n = max(1, int(sample_rate * duration))
    out: list[float] = []
    for i in range(n):
        t = i / sample_rate
        decay = math.exp(-t * 95.0)
        tone = (
            0.55 * math.sin(2.0 * math.pi * 2350.0 * t)
            + 0.35 * math.sin(2.0 * math.pi * 3400.0 * t)
        )
        click = 0.35 * rng.uniform(-1.0, 1.0) * math.exp(-t * 160.0)
        out.append(max(-1.0, min(1.0, 0.45 * decay * (tone + click))))
    return out


def generate_step_desktop_samples(
    duration: float = 0.075,
    sample_rate: int = SAMPLE_RATE,
) -> list[float]:
    """Masaüstünde yürüme: tok ve yumuşak pati pıtırtısı."""
    rng = random.Random(17)
    n = max(1, int(sample_rate * duration))
    out: list[float] = []
    lp = 0.0
    for i in range(n):
        t = i / sample_rate
        decay = math.exp(-t * 55.0)
        attack = min(1.0, t / 0.004)
        lp = 0.88 * lp + 0.12 * rng.uniform(-1.0, 1.0)
        thump = (
            0.65 * math.sin(2.0 * math.pi * 165.0 * t)
            + 0.25 * math.sin(2.0 * math.pi * 245.0 * t)
        )
        out.append(max(-1.0, min(1.0, 0.32 * attack * decay * (thump + 0.8 * lp))))
    return out


def generate_step_wav(
    surface: str = "desktop",
    sample_rate: int = SAMPLE_RATE,
) -> bytes:
    """Yüzeye göre adım sesi WAV baytları üretir."""
    if step_sound_name(surface) == "step_window":
        return samples_to_wav(
            generate_step_window_samples(sample_rate=sample_rate),
            sample_rate=sample_rate,
        )
    return samples_to_wav(
        generate_step_desktop_samples(sample_rate=sample_rate),
        sample_rate=sample_rate,
    )


# ---------------------------------------------------------------------------
# 5. Klavye Reaktif Sesleri
# ---------------------------------------------------------------------------

def generate_keyboard_trill_samples(
    duration: float = 0.22,
    sample_rate: int = SAMPLE_RATE,
) -> list[float]:
    """Hızlı yazı yazarken meraklı kedi mır-trill sesi üretir."""
    n = max(1, int(sample_rate * duration))
    out: list[float] = []
    phase = 0.0
    env = _adsr_envelope(n, attack=0.04, decay=0.12, sustain=0.85, release=0.2)
    last = max(1, n - 1)
    for i in range(n):
        t = i / last
        trill_mod = 0.5 + 0.5 * math.sin(2.0 * math.pi * 28.0 * (i / sample_rate))
        freq = 720.0 + 340.0 * math.sin(math.pi * t)
        phase += 2.0 * math.pi * freq / sample_rate
        s = (math.sin(phase) + 0.45 * math.sin(2.0 * phase)) * (0.55 + 0.45 * trill_mod)
        out.append(max(-1.0, min(1.0, 0.34 * env[i] * s)))
    return out


def generate_keyboard_trill_wav(sample_rate: int = SAMPLE_RATE) -> bytes:
    return samples_to_wav(
        generate_keyboard_trill_samples(sample_rate=sample_rate),
        sample_rate=sample_rate,
    )


class KeyboardReactiveAudio:
    """Kullanıcı hızlı yazı yazarken (keys_per_sec >= 4.0) cooldown ile trill tetikler."""

    def __init__(
        self,
        threshold_kps: float = 4.0,
        cooldown_sec: float = 8.0,
        window_sec: float = 1.0,
    ):
        self.threshold_kps = float(threshold_kps)
        self.cooldown_sec = float(cooldown_sec)
        self.window_sec = max(0.1, float(window_sec))
        self._timestamps: list[float] = []
        self._last_trigger: float | None = None

    def _can_trigger(self, now: float) -> bool:
        if self._last_trigger is None:
            return True
        return (now - self._last_trigger) >= self.cooldown_sec

    def current_kps(self, now: float | None = None) -> float:
        t = time.monotonic() if now is None else float(now)
        cutoff = t - self.window_sec
        self._timestamps = [ts for ts in self._timestamps if ts >= cutoff]
        return len(self._timestamps) / self.window_sec

    def record_keystroke(self, now: float | None = None) -> str | None:
        t = time.monotonic() if now is None else float(now)
        self._timestamps.append(t)
        kps = self.current_kps(now=t)
        return self.evaluate_rate(kps, now=t)

    def evaluate_rate(
        self,
        keys_per_sec: float,
        now: float | None = None,
    ) -> str | None:
        t = time.monotonic() if now is None else float(now)
        if float(keys_per_sec) >= self.threshold_kps and self._can_trigger(t):
            self._last_trigger = t
            return "keyboard_trill"
        return None

    def reset(self) -> None:
        self._timestamps.clear()
        self._last_trigger = None


# ---------------------------------------------------------------------------
# 6. Doğal Türkçe TTS (edge-tts -> piper-tts -> Windows SAPI fallback)
# ---------------------------------------------------------------------------

class NaturalTurkishTTS:
    """Doğal Türkçe TTS zinciri:
    1. Birincil: edge-tts (tr-TR-EmelNeural / tr-TR-AhmetNeural, pitch='+15Hz')
    2. Çevrimdışı yedek: piper-tts CLI
    3. Son çare: Windows SAPI (mevcut VoiceService)
    """

    def __init__(
        self,
        edge_voice: str = DEFAULT_EDGE_VOICE,
        pitch: str = DEFAULT_EDGE_PITCH,
        piper_bin: str = "piper",
        piper_model: str | Path | None = None,
        speech_rate: int = 0,
        sapi_fallback: Callable[[str], bool] | None = None,
        audio_player: Callable[[str], bool] | None = None,
    ):
        self.edge_voice = (
            edge_voice if edge_voice in EDGE_TTS_VOICES else DEFAULT_EDGE_VOICE
        )
        self.pitch = pitch
        self.piper_bin = piper_bin
        self.piper_model = Path(piper_model) if piper_model else None
        self.speech_rate = speech_rate
        self._sapi_fallback = sapi_fallback
        self._audio_player = audio_player
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._sapi_service = None
        self.last_backend: str | None = None

    def _default_play_file(self, path: str) -> bool:
        if pygame is not None:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy() and not self._stop_event.is_set():
                    time.sleep(0.05)
                if self._stop_event.is_set():
                    pygame.mixer.music.stop()
                return True
            except Exception:
                logging.debug("pygame TTS oynatma başarısız", exc_info=True)
        return False

    def _play_file(self, path: str) -> bool:
        if self._audio_player is not None:
            return bool(self._audio_player(path))
        return self._default_play_file(path)

    def _synthesize_edge_tts(self, text: str, output_path: str) -> bool:
        try:
            import edge_tts  # type: ignore
        except Exception:
            return False

        async def _save() -> None:
            comm = edge_tts.Communicate(text, voice=self.edge_voice, pitch=self.pitch)
            await comm.save(output_path)

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(_save())
            else:
                exc_holder: list[BaseException] = []

                def _runner() -> None:
                    try:
                        asyncio.run(_save())
                    except BaseException as exc:
                        exc_holder.append(exc)

                t = threading.Thread(target=_runner, daemon=True)
                t.start()
                t.join(timeout=20)
                if exc_holder:
                    raise exc_holder[0]
            return os.path.isfile(output_path) and os.path.getsize(output_path) > 0
        except Exception:
            logging.debug("edge-tts başarısız oldu, yedeğe geçiliyor", exc_info=True)
            return False

    def _synthesize_piper_tts(self, text: str, output_path: str) -> bool:
        if self.piper_model is None or not self.piper_model.is_file():
            return False
        exe = (
            self.piper_bin
            if os.path.isfile(self.piper_bin)
            else shutil.which(self.piper_bin)
        )
        if not exe:
            return False
        try:
            subprocess.run(
                [exe, "--model", str(self.piper_model), "--output_file", output_path],
                input=text,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=20,
                check=True,
                creationflags=_NO_WINDOW,
            )
            return os.path.isfile(output_path) and os.path.getsize(output_path) > 0
        except Exception:
            logging.debug("piper-tts başarısız oldu, SAPI yedeğine geçiliyor", exc_info=True)
            return False

    def _speak_sapi(self, text: str) -> bool:
        if self._sapi_fallback is not None:
            return bool(self._sapi_fallback(text))
        try:
            from voice import VoiceService

            if self._sapi_service is None:
                self._sapi_service = VoiceService(speech_rate=self.speech_rate)
            return bool(self._sapi_service.speak(text))
        except Exception:
            logging.debug("SAPI fallback başarısız", exc_info=True)
            return False

    def speak_sync(self, text: str) -> str | None:
        """Metni seslendirir ve kullanılan motoru ('edge-tts'|'piper-tts'|'sapi'|None) döndürür."""
        clean = str(text or "").strip()
        if not clean:
            return None
        self._stop_event.clear()

        with tempfile.TemporaryDirectory(prefix="komur_tts_") as tmpdir:
            mp3_path = os.path.join(tmpdir, "speech.mp3")
            if self._synthesize_edge_tts(clean, mp3_path):
                if self._play_file(mp3_path):
                    self.last_backend = "edge-tts"
                    return "edge-tts"

            wav_path = os.path.join(tmpdir, "speech.wav")
            if self._synthesize_piper_tts(clean, wav_path):
                if self._play_file(wav_path):
                    self.last_backend = "piper-tts"
                    return "piper-tts"

        if self._speak_sapi(clean):
            self.last_backend = "sapi"
            return "sapi"

        self.last_backend = None
        return None

    def speak(
        self,
        text: str,
        on_done: Callable[[str | None], None] | None = None,
    ) -> threading.Thread | None:
        """Doğal Türkçe seslendirmeyi UI'ı bloklamadan arka planda başlatır."""
        if not str(text or "").strip():
            return None

        def _worker() -> None:
            backend = self.speak_sync(text)
            if on_done is not None:
                on_done(backend)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop_event.set()
        if pygame is not None:
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
            except Exception:
                pass
        if self._sapi_service is not None:
            try:
                self._sapi_service.stop()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 7. Odak Lofi Ambiyansı (Yağmur + Şömine Çıtırtısı + Hafif Mırıldanma)
# ---------------------------------------------------------------------------

def generate_lofi_ambience_samples(
    duration: float = 4.0,
    sample_rate: int = SAMPLE_RATE,
    seed: int = 42,
) -> list[float]:
    """Pomodoro odak modu için yağmur + şömine çıtırtısı + hafif mırıldanma döngüsü üretir."""
    rng = random.Random(seed)
    n = max(1, int(sample_rate * duration))
    out: list[float] = []
    rain_lp = 0.0
    crackle_env = 0.0
    crackle_tone_phase = 0.0

    for i in range(n):
        t = i / sample_rate
        # Yumuşak yağmur (alçak geçiren filtreli pembe-benzeri gürültü)
        rain_lp = 0.90 * rain_lp + 0.10 * rng.uniform(-1.0, 1.0)
        rain = 0.36 * rain_lp

        # Şömine çıtırtısı (seyrek kısa dürtü patlamaları)
        if rng.random() < 0.0022:
            crackle_env = rng.uniform(0.35, 0.85)
        else:
            crackle_env *= 0.93
        crackle_tone_phase += 2.0 * math.pi * 1650.0 / sample_rate
        crackle = crackle_env * (
            0.6 * rng.uniform(-1.0, 1.0) + 0.4 * math.sin(crackle_tone_phase)
        ) * 0.28

        # Hafif mırıldanma (26Hz temel nabız)
        purr_pulse = 0.5 + 0.5 * math.sin(2.0 * math.pi * 26.0 * t)
        purr = 0.08 * purr_pulse * (
            0.7 * math.sin(2.0 * math.pi * 52.0 * t)
            + 0.3 * math.sin(2.0 * math.pi * 78.0 * t)
        )

        out.append(max(-1.0, min(1.0, rain + crackle + purr)))

    # Döngü birleşiminde tık sesi olmaması için kısa kenar yumuşatması
    fade = min(n // 10, int(sample_rate * 0.05))
    for i in range(fade):
        w = i / max(1, fade)
        out[i] *= w
        out[n - 1 - i] *= w
    return out


def generate_lofi_ambience_wav(
    duration: float = 4.0,
    sample_rate: int = SAMPLE_RATE,
    seed: int = 42,
) -> bytes:
    """Pomodoro odak lofi ambiyansı için 16-bit WAV baytları üretir."""
    samples = generate_lofi_ambience_samples(
        duration=duration,
        sample_rate=sample_rate,
        seed=seed,
    )
    return samples_to_wav(samples, sample_rate=sample_rate)


class LofiAmbiencePlayer:
    """Pomodoro odak modunda lofi ambiyansını döngüde çalar ve durdurur."""

    def __init__(self, duration: float = 4.0, sample_rate: int = SAMPLE_RATE):
        self.duration = duration
        self.sample_rate = sample_rate
        self._wav_bytes: bytes | None = None
        self._channel = None
        self._sound = None
        self._playing = False
        self._lock = threading.Lock()

    @property
    def is_playing(self) -> bool:
        return self._playing

    def _ensure_wav(self) -> bytes:
        if self._wav_bytes is None:
            self._wav_bytes = generate_lofi_ambience_wav(
                duration=self.duration,
                sample_rate=self.sample_rate,
            )
        return self._wav_bytes

    def start(
        self,
        master_vol: float = 0.35,
        cat_x: float | None = None,
        screen_w: float | None = None,
    ) -> bool:
        with self._lock:
            if self._playing:
                return True
            wav_data = self._ensure_wav()
            self._playing = True
            if pygame is None:
                return False
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(
                        frequency=self.sample_rate,
                        size=-16,
                        channels=2,
                        buffer=512,
                    )
                self._sound = pygame.mixer.Sound(io.BytesIO(wav_data))
                self._channel = self._sound.play(loops=-1)
                self.set_volume(master_vol, cat_x=cat_x, screen_w=screen_w)
                return True
            except Exception:
                logging.debug("Lofi ambiyans başlatılamadı", exc_info=True)
                self._playing = False
                return False

    def set_volume(
        self,
        master_vol: float,
        cat_x: float | None = None,
        screen_w: float | None = None,
    ) -> None:
        vol = max(0.0, min(1.0, float(master_vol)))
        if self._channel is not None:
            if cat_x is not None and screen_w is not None:
                apply_channel_pan(self._channel, cat_x, screen_w, vol)
            else:
                self._channel.set_volume(vol)
        elif self._sound is not None:
            self._sound.set_volume(vol)

    def stop(self) -> None:
        with self._lock:
            self._playing = False
            if self._channel is not None:
                try:
                    self._channel.stop()
                except Exception:
                    pass
                self._channel = None
            self._sound = None


# ---------------------------------------------------------------------------
# 8. Mikrofon Gürültüsü Tepkisi (MicNoiseMonitor)
# ---------------------------------------------------------------------------

class MicNoiseMonitor:
    """Mikrofon RMS seviyesini izleyerek tepki durumu döndürür:
    - rms > 0.35 -> "startle" (irkilme)
    - silence_sec >= 180 -> "deep_sleep" (derin uyku)
    - Aksi halde -> None
    """

    def __init__(
        self,
        startle_threshold: float = 0.35,
        silence_threshold: float = 0.02,
        deep_sleep_seconds: float = 180.0,
        startle_cooldown: float = 5.0,
    ):
        self.startle_threshold = float(startle_threshold)
        self.silence_threshold = float(silence_threshold)
        self.deep_sleep_seconds = float(deep_sleep_seconds)
        self.startle_cooldown = float(startle_cooldown)
        self._silence_elapsed = 0.0
        self._last_time: float | None = None
        self._last_startle_time: float | None = None
        self.state = "awake"

    @staticmethod
    def compute_rms(samples: Iterable[float]) -> float:
        """Örnek dizisinin RMS değerini hesaplar (numpy gerektirmez)."""
        total = 0.0
        count = 0
        for s in samples:
            val = float(s)
            total += val * val
            count += 1
        if count == 0:
            return 0.0
        return math.sqrt(total / count)

    @property
    def silence_seconds(self) -> float:
        return self._silence_elapsed

    def process_rms(
        self,
        rms: float,
        now: float | None = None,
        dt: float | None = None,
    ) -> str | None:
        """Hesaplanmış RMS değerini değerlendirir ve gerekiyorsa olay adı döndürür."""
        t = time.monotonic() if now is None else float(now)
        if dt is not None:
            delta = max(0.0, float(dt))
        elif self._last_time is not None:
            delta = max(0.0, t - self._last_time)
        else:
            delta = 0.0
        self._last_time = t

        level = float(rms)
        if level > self.startle_threshold:
            self._silence_elapsed = 0.0
            self.state = "startled"
            if (
                self._last_startle_time is None
                or (t - self._last_startle_time) >= self.startle_cooldown
            ):
                self._last_startle_time = t
                return "startle"
            return None

        if level <= self.silence_threshold:
            self._silence_elapsed += delta
            if self._silence_elapsed >= self.deep_sleep_seconds:
                self.state = "deep_sleep"
                return "deep_sleep"
            return None

        self._silence_elapsed = 0.0
        self.state = "awake"
        return None

    def process_audio(
        self,
        samples: Iterable[float],
        now: float | None = None,
        dt: float | None = None,
    ) -> str | None:
        """Ses örneklerinden RMS hesaplayıp durum değerlendirmesi yapar."""
        rms = self.compute_rms(samples)
        return self.process_rms(rms, now=now, dt=dt)

    def reset(self) -> None:
        self._silence_elapsed = 0.0
        self._last_time = None
        self._last_startle_time = None
        self.state = "awake"
