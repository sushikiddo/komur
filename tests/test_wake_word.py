import sys
import threading
import time
import types

import numpy as np
import pytest

import voice


FAST = dict(window_seconds=0.1, hop_seconds=0.05, cooldown_seconds=5.0)


class FakeAudio:
    """Stands in for sounddevice and faster_whisper; never touches a real microphone."""

    def __init__(self):
        self.lock = threading.Lock()
        self.open_count = 0
        self.max_open = 0
        self.opened_total = 0
        self.open_error = None
        self.text = ""
        self.transcribe_calls = 0

    def stream_factory(self, **kwargs):
        return FakeStream(self, **kwargs)


class FakeStream:
    def __init__(self, audio, **kwargs):
        self.audio = audio

    def __enter__(self):
        if self.audio.open_error is not None:
            raise self.audio.open_error
        with self.audio.lock:
            self.audio.open_count += 1
            self.audio.opened_total += 1
            self.audio.max_open = max(self.audio.max_open, self.audio.open_count)
        return self

    def __exit__(self, *args):
        with self.audio.lock:
            self.audio.open_count -= 1
        return False

    def read(self, size):
        time.sleep(0.003)
        return np.full((size, 1), 0.1, dtype=np.float32), False


def wait_for(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def audio(monkeypatch):
    state = FakeAudio()

    class FakeModel:
        def __init__(self, path, **kwargs):
            assert kwargs["local_files_only"] is True

        def transcribe(self, data, **kwargs):
            assert kwargs["language"] == "tr"
            state.transcribe_calls += 1
            return [types.SimpleNamespace(text=state.text)], None

    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(InputStream=state.stream_factory))
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    monkeypatch.setattr(voice.VoiceService, "status", lambda self: {"stt_available": True})
    return state


@pytest.fixture
def services():
    """Every service created in a test is closed afterwards, so no listener thread leaks."""
    created = []
    yield created
    for service in created:
        service.close()


def make_service(tmp_path, created, **kwargs):
    service = voice.VoiceService(tmp_path, **kwargs)
    created.append(service)
    return service


def test_wake_listener_is_off_by_default(audio, tmp_path, services):
    service = make_service(tmp_path, services)
    threads_before = threading.active_count()
    assert service._wake_thread is None
    assert audio.opened_total == 0
    assert threading.active_count() == threads_before


def test_missing_model_raises_turkish_error_and_starts_no_thread(tmp_path, services, monkeypatch):
    monkeypatch.setattr(voice, "_turkish_voice_token", lambda: None)
    service = make_service(tmp_path, services)
    with pytest.raises(voice.VoiceError, match="ses modeli"):
        service.start_wake_listener(lambda: None)
    assert service._wake_thread is None


def test_wake_phrase_matching_is_turkish_and_tolerant():
    assert voice.is_wake_phrase("Hey Kömür.")
    assert voice.is_wake_phrase("komur")
    assert voice.is_wake_phrase("KÖMÜR!")
    assert voice.is_wake_phrase("hey, kömür, nasılsın")
    assert not voice.is_wake_phrase("")
    assert not voice.is_wake_phrase("merhaba dünya")
    assert not voice.is_wake_phrase("kömürlük")


def test_matching_phrase_fires_once_during_cooldown(audio, tmp_path, services):
    service = make_service(tmp_path, services)
    audio.text = "Hey Kömür"
    fired = threading.Event()
    calls = []

    def on_wake():
        calls.append(1)
        fired.set()

    service.start_wake_listener(on_wake, **FAST)
    assert fired.wait(3)
    time.sleep(0.3)
    service.stop_wake_listener()
    assert len(calls) == 1


def test_non_matching_speech_never_fires(audio, tmp_path, services):
    service = make_service(tmp_path, services)
    audio.text = "merhaba dünya"
    calls = []
    service.start_wake_listener(lambda: calls.append(1), **FAST)
    assert wait_for(lambda: audio.transcribe_calls >= 3)
    service.stop_wake_listener()
    assert calls == []


def test_push_to_talk_pauses_listener_so_microphone_never_overlaps(audio, tmp_path, services):
    service = make_service(tmp_path, services)
    audio.text = "merhaba"
    service.start_wake_listener(lambda: None, **FAST)
    assert wait_for(lambda: audio.open_count == 1)

    record_stop = threading.Event()
    result = {}
    opened_before_record = audio.opened_total
    worker = threading.Thread(
        target=lambda: result.update(text=service.record_and_transcribe(record_stop, max_seconds=5)))
    worker.start()
    assert wait_for(lambda: audio.opened_total > opened_before_record)
    time.sleep(0.1)
    record_stop.set()
    worker.join(5)
    assert not worker.is_alive()

    assert audio.max_open == 1
    assert result["text"] == "merhaba"
    # Listener resumes after push-to-talk finishes.
    assert wait_for(lambda: audio.open_count == 1)
    assert service._wake_thread.is_alive()
    service.stop_wake_listener()


def test_stop_releases_microphone_and_ends_thread(audio, tmp_path, services):
    service = make_service(tmp_path, services)
    service.start_wake_listener(lambda: None, **FAST)
    assert wait_for(lambda: audio.open_count == 1)
    thread = service._wake_thread
    service.stop_wake_listener()
    assert not thread.is_alive()
    assert audio.open_count == 0


def test_close_stops_wake_listener(audio, tmp_path, services):
    service = make_service(tmp_path, services)
    service.start_wake_listener(lambda: None, **FAST)
    assert wait_for(lambda: audio.open_count == 1)
    thread = service._wake_thread
    service.close()
    thread.join(3)
    assert not thread.is_alive()
    assert audio.open_count == 0


def test_closed_service_refuses_to_start_listener(audio, tmp_path, services):
    service = make_service(tmp_path, services)
    service.close()
    with pytest.raises(voice.VoiceError):
        service.start_wake_listener(lambda: None, **FAST)
    assert service._wake_thread is None


def test_microphone_error_ends_listener_quietly(audio, tmp_path, services):
    service = make_service(tmp_path, services)
    audio.open_error = OSError("access denied")
    service.start_wake_listener(lambda: None, **FAST)
    thread = service._wake_thread
    thread.join(3)
    assert not thread.is_alive()
    assert "mikrofon" in service.wake_error


def test_wake_callback_error_does_not_kill_listener(audio, tmp_path, services):
    service = make_service(tmp_path, services)
    audio.text = "kömür"
    calls = []

    def broken():
        calls.append(1)
        raise RuntimeError("boom")

    service.start_wake_listener(broken, window_seconds=0.1, hop_seconds=0.05, cooldown_seconds=0.0)
    assert wait_for(lambda: len(calls) >= 2)
    assert service._wake_thread.is_alive()
    assert "hata" in service.wake_error
    service.stop_wake_listener()
