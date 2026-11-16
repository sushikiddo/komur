import base64
import sys
import threading
import types
from unittest.mock import patch

import voice


def test_input_device_inventory_and_health(monkeypatch):
    fake = types.SimpleNamespace(query_devices=lambda: [
        {'name': 'Speaker', 'max_input_channels': 0},
        {'name': 'USB microphone', 'max_input_channels': 1}])
    monkeypatch.setitem(sys.modules, 'sounddevice', fake)
    monkeypatch.setattr(voice, '_turkish_voice_token', lambda: None)
    monkeypatch.setattr(voice.importlib.util, 'find_spec', lambda name: None)
    service = voice.VoiceService(input_device=1)
    assert service.list_input_devices() == [{'id': 1, 'name': 'USB microphone'}]
    assert service.status()['microphone_available']
    service.input_device = 8
    assert not service.status()['microphone_available']
    fake.query_devices = lambda: (_ for _ in ()).throw(OSError('device error'))
    assert 'device error' in service.status()['microphone_message']


def test_selected_microphone_passed_to_stream(monkeypatch):
    calls = []
    def fail(**kwargs):
        calls.append(kwargs)
        raise OSError('test stop')
    monkeypatch.setitem(sys.modules, 'sounddevice', types.SimpleNamespace(InputStream=fail))
    monkeypatch.setitem(sys.modules, 'faster_whisper', types.SimpleNamespace(WhisperModel=object))
    monkeypatch.setattr(voice.VoiceService, 'status', lambda self: {'stt_available': True})
    try:
        voice.VoiceService(input_device=4).record_and_transcribe(threading.Event())
    except voice.VoiceError:
        pass
    assert calls[0]['device'] == 4


def test_speech_rate_is_bounded(monkeypatch):
    monkeypatch.setattr(voice, '_turkish_voice_token', lambda: 'test')
    captured = []
    class Process:
        def communicate(self, input): pass
        def poll(self): return 0
    def popen(args, **kwargs):
        captured.append(base64.b64decode(args[-1]).decode('utf-16le'))
        return Process()
    monkeypatch.setattr(voice.subprocess, 'Popen', popen)
    assert voice.VoiceService(speech_rate=100).speak('Merhaba')
    assert '$v.Rate=10;' in captured[0]
