import sys
import threading
import types

import numpy as np
import pytest

import voice


def test_missing_model_is_explicit_and_no_download(tmp_path, monkeypatch):
    monkeypatch.setattr(voice, "_turkish_voice_token", lambda: None)
    service = voice.VoiceService(tmp_path)
    result = service.status()
    assert not result["stt_available"]
    assert not result["tts_available"]
    with pytest.raises(voice.VoiceError):
        service.record_and_transcribe(threading.Event())


def test_push_to_talk_stops_and_transcribes_local_audio(tmp_path, monkeypatch):
    event = threading.Event()
    calls = []
    for name in voice._MODEL_FILES:
        (tmp_path / name).touch()
    class Stream:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, size):
            event.set()
            return np.full((size, 1), 0.1, dtype=np.float32), False
    class Model:
        def __init__(self, path, **kwargs):
            assert path == str(tmp_path)
            assert kwargs["local_files_only"] is True
        def transcribe(self, audio, **kwargs):
            assert kwargs["language"] == "tr"
            return [types.SimpleNamespace(text=" Merhaba ")], None
    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(InputStream=Stream))
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    monkeypatch.setattr(voice.VoiceService, "status", lambda self: {"stt_available": True})
    assert voice.VoiceService(tmp_path).record_and_transcribe(event) == "Merhaba"
    assert calls[0]["samplerate"] == 16000


def test_microphone_error_is_user_facing(monkeypatch):
    monkeypatch.setattr(voice.VoiceService, "status", lambda self: {"stt_available": True})
    def denied(**kwargs):
        raise OSError("access denied")
    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(InputStream=denied))
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=object))
    with pytest.raises(voice.VoiceError, match="access denied"):
        voice.VoiceService().record_and_transcribe(threading.Event())


def test_stop_speech_does_not_cancel_recording():
    service = voice.VoiceService()
    service.stop()
    assert not service._stop.is_set()
    service.close()
    assert service._stop.is_set()


def test_speech_unavailable_does_not_start_process(monkeypatch):
    monkeypatch.setattr(voice, "_turkish_voice_token", lambda: None)
    assert not voice.VoiceService().speak("Merhaba")


def test_closed_service_never_starts_recording_or_speech(monkeypatch):
    service = voice.VoiceService()
    service.close()
    monkeypatch.setattr(voice.VoiceService, "status", lambda self: {"stt_available": True})
    monkeypatch.setattr(voice, "_turkish_voice_token", lambda: "test-token")
    def forbidden(*args, **kwargs):
        raise AssertionError("closed service started a process")
    monkeypatch.setattr(voice.subprocess, "Popen", forbidden)
    assert service.record_and_transcribe(threading.Event()) == ""
    assert service.speak("Merhaba") is False
    assert service._stop.is_set()
