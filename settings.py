"""Persistent settings for Kömür, stored as JSON under %LOCALAPPDATA%\\Komur.

Every read/write is defensive: a missing or corrupt file falls back to defaults,
and saving never raises into the UI. Standard library only.
"""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path

APP_DIR_NAME = "Komur"
FILE_NAME = "settings.json"

DEFAULTS = {
    "ai_enabled": True,
    "ai_backend": "local",
    "ai_model": "claude-sonnet-5-5",
    "ai_cli_model": "",
    "ai_api_key": "",
    "ai_openai_model": "gpt-4o-mini",
    "ai_openai_base_url": "https://api.openai.com/v1",
    "ai_local_model": "qwen2.5:7b",
    "ai_local_base_url": "http://127.0.0.1:11434/v1",
    "activity_context": False,
    "activity_reactions": True,
    "focus_mode": True,
    "voice_preview": True,
    "voice_input_device": None,
    "speech_rate": 0,
    "history_enabled": True,
    "voice_replies": False,
    "name": "Kömür",            # cat's name, shown in panel + greetings
    "skin": "komur",            # key into skins.SKINS
    "size": "small",            # small | normal | large | xlarge - default small
    "opacity": 100,             # 10..100 (percent)
    "sound": True,              # meow/purr sound effects
    "needs": True,              # hunger/needs system enabled
    "autostart": False,         # launch with Windows (mirrors the registry)
    "activity_level": "sakin",  # kendiliginden hareket: sakin | normal | hareketli
    "friends": 0,               # number of companion cats (0..3)
    "x": None,                  # last window position (screen px); None = default
    "y": None,
    "area_index": 0,            # last monitor index
    "effects": True,            # görsel efenkler (partiküller, efektler)
    "sound_quality": "high",    # ses sentezi kalitesi: high | normal
    "effects_density": 2,       # efekt yoğunluğu: 1=düşük, 2=normal, 3=yüksek
    "sound_volume": 70,         # ses ses seviyesi: 0..100 (yüzde)
    "speech_bubbles": True,     # konuşma baloncukları etkin mi
    "speech_interval": 3600,      # otomatik konuşma: kapalı (sadece etkileşim)
    "speech_on_wander": False,    # gezirken otomatik konuşma kapalı
    "greeting_on_start": True,    # program açılışında selamla
    "accessory": None,            # None | bow | scarf | hat | glasses
    "day_night": True,            # saate göre gece/akşam tonu
    "wake_word": False,           # "Hey Kömür" dinleme (mikrofon) — varsayılan kapalı
    "user_plugins_enabled": False,  # %LOCALAPPDATA%\Komur\plugins yüklensin mi
    "habit_memory": True,         # alışkanlık sayacı + tek seferlik öneriler
    "update_check": True,         # günde en fazla bir kez GitHub'da yeni sürüm denetle (kurulum onaylı)
    "update_last_check": None,    # son denetim (time.time)
}

SIZE_SCALES = {"small": 0.55, "normal": 1.0, "large": 1.3, "xlarge": 1.6}
SIZE_LABELS = {"small": "Küçük", "normal": "Orta", "large": "Büyük", "xlarge": "Kocaman"}


def config_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / APP_DIR_NAME


def config_path() -> Path:
    return config_dir() / FILE_NAME


class Settings:
    """Dict-backed settings with attribute-style ``get``/``set`` and autosave."""

    def __init__(self, data=None):
        self._data = dict(DEFAULTS)
        if data:
            self._data.update({k: v for k, v in data.items() if k in DEFAULTS})

    @classmethod
    def load(cls):
        try:
            raw = config_path().read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                return cls(data)
        except (OSError, ValueError, TypeError):
            pass
        return cls()

    def save(self):
        try:
            directory = config_dir()
            directory.mkdir(parents=True, exist_ok=True)
            config_path().write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            logging.exception("Could not save settings")

    def get(self, key, default=None):
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value, save=True):
        self._data[key] = value
        if save:
            self.save()

    def update(self, save=True, **kwargs):
        self._data.update(kwargs)
        if save:
            self.save()

    @property
    def scale(self):
        return SIZE_SCALES.get(self.get("size"), 1.0)
