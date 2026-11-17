"""Explicit, offline push-to-talk and Windows speech output for Kömür."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import threading


MODEL_REPOSITORY = "Systran/faster-whisper-small"
MODEL_REVISION = "536b0662742c02347bc0e980a01041f333bce120"
MODEL_SHA256 = "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"
MODEL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Komur" / "models" / "faster-whisper-small"
_MODEL_FILES = ("model.bin", "config.json", "tokenizer.json")
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_WAKE_BLOCK = 1600
_WAKE_RE = re.compile(r"\bkomur\b")
_TR_FOLD = str.maketrans({"ö": "o", "ü": "u", "ç": "c", "ş": "s", "ğ": "g", "ı": "i"})


class VoiceError(RuntimeError):
    """A user-facing voice error."""


def is_wake_phrase(text):
    """True when recognized text contains the wake word 'kömür'. The text is not kept."""
    folded = str(text).replace("İ", "i").lower().translate(_TR_FOLD)
    return bool(_WAKE_RE.search(folded))


def setup_voice_model(model_dir=MODEL_DIR, progress_callback=None):
    """Explicit setup action; this is the only function that downloads a model."""
    try:
        from huggingface_hub import snapshot_download
        path = Path(model_dir)
        path.mkdir(parents=True, exist_ok=True)
        if progress_callback:
            progress_callback("Ses modeli indiriliyor (yaklaşık 486 MB).")
        snapshot_download(MODEL_REPOSITORY, revision=MODEL_REVISION, local_dir=str(path))
        if not all((path / name).is_file() for name in _MODEL_FILES):
            raise VoiceError("Ses modeli eksik indirildi; kurulumu tekrar deneyin.")
        digest = hashlib.sha256()
        with (path / "model.bin").open("rb") as model:
            for chunk in iter(lambda: model.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != MODEL_SHA256:
            raise VoiceError("Ses modeli doğrulanamadı; kurulumu tekrar deneyin.")
        if progress_callback:
            progress_callback("Ses modeli hazır.")
        return path
    except VoiceError:
        raise
    except Exception as exc:
        raise VoiceError(f"Ses modeli indirilemedi: {exc}") from exc


def _powershell(script, **kwargs):
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                          capture_output=True, text=True, timeout=10, creationflags=_NO_WINDOW, **kwargs)


def _turkish_voice_token():
    if os.name != "nt":
        return None
    try:
        import winreg
        for branch in (r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens",
                       r"SOFTWARE\Microsoft\Speech\Voices\Tokens"):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, branch) as keys:
                    for i in range(winreg.QueryInfoKey(keys)[0]):
                        name = winreg.EnumKey(keys, i)
                        with winreg.OpenKey(keys, name + r"\Attributes") as attributes:
                            language = str(winreg.QueryValueEx(attributes, "Language")[0]).lower()
                        if any(part.strip().lstrip("0") == "41f" for part in language.split(";")):
                            return "HKEY_LOCAL_MACHINE\\" + branch + "\\" + name
            except OSError:
                continue
    except OSError:
        pass
    return None


class VoiceService:
    def __init__(self, model_dir=MODEL_DIR, input_device=None, speech_rate=0):
        self.input_device = input_device
        self.speech_rate = speech_rate
        self.model_dir = Path(model_dir)
        self._model = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._closed = False
        self._speech_process = None
        self._ptt_active = False
        self._wake_thread = None
        self._wake_stop = threading.Event()
        self._wake_resume = threading.Event()
        self._wake_idle = threading.Event()
        self._wake_idle.set()
        self.wake_error = ""

    def list_input_devices(self):
        """Return available input devices as stable PortAudio indices and names."""
        try:
            import sounddevice as sd
            return [{"id": index, "name": str(device["name"])}
                    for index, device in enumerate(sd.query_devices())
                    if device.get("max_input_channels", 0) > 0]
        except Exception as exc:
            self._microphone_error = str(exc)
            return []

    def status(self):
        self._microphone_error = ""
        devices = self.list_input_devices()
        selected = self.input_device
        effective = selected
        if selected is None and devices:
            try:
                import sounddevice as sd
                effective = sd.default.device[0]
            except (AttributeError, IndexError, TypeError):
                effective = None
        mic_available = bool(devices) and (effective is None or any(d["id"] == effective for d in devices))
        mic_message = ("Mikrofon hazır." if mic_available else
                       self._microphone_error or ("Seçilen mikrofon bulunamadı." if selected is not None else "Mikrofon bulunamadı."))
        deps = all(importlib.util.find_spec(name) is not None for name in ("faster_whisper", "sounddevice", "numpy"))
        model = all((self.model_dir / name).is_file() for name in _MODEL_FILES)
        tts = bool(_turkish_voice_token())
        stt_message = ("Sesle yazma hazır." if deps and model else
                       "Ses paketleri kurulu değil." if not deps else
                       "Türkçe ses modeli kurulmamış; önce ses modelini kurun.")
        return {"stt_available": deps and model, "stt_message": stt_message,
                "microphone_available": mic_available, "microphone_message": mic_message,
                "input_device": selected,
                "tts_available": tts,
                "tts_message": "Türkçe ses hazır." if tts else "Windows'ta Türkçe konuşma sesi kurulu değil."}

    def record_and_transcribe(self, stop_event, max_seconds=20):
        """Call in a worker only after the user starts recording; stop_event ends capture."""
        self._pause_wake()
        try:
            return self._record_and_transcribe(stop_event, max_seconds)
        finally:
            self._resume_wake()

    def _record_and_transcribe(self, stop_event, max_seconds):
        status = self.status()
        if not status["stt_available"]:
            raise VoiceError(status["stt_message"])
        with self._lock:
            if self._closed or stop_event.is_set():
                return ""
            self._stop.clear()
        try:
            import numpy as np
            import sounddevice as sd
            from faster_whisper import WhisperModel
            chunks = []
            sample_rate = 16000
            seconds = max(0.1, min(float(max_seconds), 20.0))
            blocksize = 1600
            with self._lock:
                if self._closed or stop_event.is_set():
                    return ""
                stream_options = dict(samplerate=sample_rate, channels=1, dtype="float32", blocksize=blocksize)
                if self.input_device is not None:
                    stream_options["device"] = self.input_device
                stream = sd.InputStream(**stream_options)
                stream.__enter__()
            try:
                for _ in range(max(1, int(seconds * sample_rate / blocksize))):
                    if stop_event.is_set() or self._stop.is_set():
                        break
                    data, overflow = stream.read(blocksize)
                    chunks.append(data.copy())
            finally:
                stream.__exit__(None, None, None)
            if not chunks or self._stop.is_set():
                return ""
            audio = np.concatenate(chunks).reshape(-1)
            if not audio.size or float(np.max(np.abs(audio))) < 0.005:
                return ""
            if self._model is None:
                self._model = WhisperModel(str(self.model_dir), device="cpu", compute_type="int8", local_files_only=True)
            if self._stop.is_set():
                return ""
            segments, _ = self._model.transcribe(audio, language="tr", beam_size=5, vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
            return "" if self._stop.is_set() else text
        except Exception as exc:
            raise VoiceError(f"Ses kaydı veya konuşma tanıma başarısız: {exc}") from exc

    def start_wake_listener(self, on_wake, window_seconds=3.0, hop_seconds=1.0, cooldown_seconds=3.0):
        """Opt-in 'Hey Kömür' listener. Off unless called. on_wake() runs on the listener thread."""
        if not callable(on_wake):
            raise VoiceError("Uyandırma işlevi çağrılabilir olmalı.")
        status = self.status()
        if not status.get("stt_available"):
            raise VoiceError(status.get("stt_message") or "Sesle uyandırma hazır değil.")
        with self._lock:
            if self._closed:
                raise VoiceError("Ses servisi kapatıldı.")
            thread = self._wake_thread
            if thread is not None and thread.is_alive() and not self._wake_stop.is_set():
                return
            self._wake_stop = threading.Event()
            self._wake_resume = threading.Event()
            if not self._ptt_active:
                self._wake_resume.set()
            self._wake_idle = threading.Event()
            self.wake_error = ""
            self._wake_thread = threading.Thread(
                target=self._wake_loop,
                args=(on_wake, window_seconds, hop_seconds, cooldown_seconds),
                daemon=True)
            self._wake_thread.start()

    def stop_wake_listener(self):
        """Stop the wake listener and wait briefly so its microphone is released."""
        thread = self._wake_thread
        self._wake_stop.set()
        self._wake_resume.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)
            self._wake_thread = None

    def _pause_wake(self):
        with self._lock:
            self._ptt_active = True
            thread = self._wake_thread
        if thread is not None and thread.is_alive():
            self._wake_resume.clear()
            self._wake_idle.wait(5)

    def _resume_wake(self):
        with self._lock:
            self._ptt_active = False
            thread = self._wake_thread
        if thread is not None and thread.is_alive() and not self._wake_stop.is_set():
            self._wake_idle.clear()
            self._wake_resume.set()

    def _wake_loop(self, on_wake, window_seconds, hop_seconds, cooldown_seconds):
        try:
            import numpy as np
            import sounddevice as sd
            from faster_whisper import WhisperModel
            if self._model is None:
                self._model = WhisperModel(str(self.model_dir), device="cpu", compute_type="int8", local_files_only=True)
            model = self._model
            window = int(16000 * window_seconds)
            hop = int(16000 * hop_seconds)
            options = dict(samplerate=16000, channels=1, dtype="float32", blocksize=_WAKE_BLOCK)
            if self.input_device is not None:
                options["device"] = self.input_device
            while not self._wake_stop.is_set():
                if not self._wake_resume.is_set():
                    self._wake_idle.set()
                    self._wake_resume.wait(0.2)
                    continue
                self._wake_idle.clear()
                with sd.InputStream(**options) as stream:
                    buffer = np.zeros(0, dtype=np.float32)
                    pending = 0
                    while self._wake_resume.is_set() and not self._wake_stop.is_set():
                        data, _overflow = stream.read(_WAKE_BLOCK)
                        buffer = np.concatenate((buffer, data.reshape(-1)))[-window:]
                        pending += _WAKE_BLOCK
                        if pending < hop or buffer.size < window:
                            continue
                        pending = 0
                        if float(np.max(np.abs(buffer))) < 0.005:
                            continue
                        segments, _ = model.transcribe(buffer, language="tr", beam_size=1, vad_filter=True)
                        if not is_wake_phrase(" ".join(s.text.strip() for s in segments if s.text.strip())):
                            continue
                        buffer = np.zeros(0, dtype=np.float32)
                        try:
                            on_wake()
                        except Exception:
                            self.wake_error = "Uyandırma işlemi hata verdi."
                        self._wake_stop.wait(cooldown_seconds)
        except Exception:
            self.wake_error = "Uyandırma dinleyicisi durdu; mikrofonu ve ses modelini kontrol edin."
        finally:
            self._wake_idle.set()

    def speak(self, text):
        """Start local speech in a background thread; return False if unavailable."""
        token = _turkish_voice_token()
        if not str(text).strip() or not token:
            return False
        self.stop()
        safe_token = token.replace("'", "''")
        try:
            rate = max(-10, min(10, int(self.speech_rate)))
        except (TypeError, ValueError, OverflowError):
            rate = 0
        script = ("[Console]::InputEncoding=[System.Text.Encoding]::UTF8; "
                  "$v=New-Object -ComObject SAPI.SpVoice; $t=New-Object -ComObject SAPI.SpObjectToken; "
                  f"$t.SetId('{safe_token}'); $v.Voice=$t; $v.Rate={rate}; "
                  "$null=$v.Speak([Console]::In.ReadToEnd())")
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        try:
            with self._lock:
                if self._closed:
                    return False
                process = subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                                           stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           creationflags=_NO_WINDOW)
                self._speech_process = process
            def run():
                try:
                    process.communicate(input=str(text).encode("utf-8"))
                finally:
                    with self._lock:
                        if self._speech_process is process:
                            self._speech_process = None
            threading.Thread(target=run, daemon=True).start()
            return True
        except OSError:
            return False

    def stop(self):
        """Stop speech playback without cancelling an active recording."""
        with self._lock:
            process = self._speech_process
            self._speech_process = None
        if process and process.poll() is None:
            process.terminate()

    def close(self):
        """Cancel an active recording and stop speech during shutdown."""
        with self._lock:
            self._closed = True
            self._stop.set()
        self.stop_wake_listener()
        self.stop()
