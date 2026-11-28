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
    "activity_context": False,
    "activity_reactions": True,
    "focus_mode": True,
    "history_enabled": True,
    "name": "Kömür",            # cat's name, shown in panel + greetings
    "skin": "komur",            # key into skins.SKINS
    "size": "small",            # small | normal | large | xlarge - default small
    "opacity": 100,             # 10..100 (percent)
    "sound": True,              # meow/purr sound effects
    "needs": True,              # hunger/needs system enabled
    "autostart": False,         # oturum açılınca başlat (Windows kayıt defteri / macOS LaunchAgent)
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
    "accessory": None,            # None | legacy tek aksesuar anahtarı
    "accessories": {},            # v2.5 4-slotlu kombin gardırop: {head, eyes, neck, body}
    "day_night": True,            # saate göre gece/akşam tonu
    "user_plugins_enabled": False,  # %LOCALAPPDATA%\Komur\plugins yüklensin mi
    "habit_memory": True,         # alışkanlık sayacı + tek seferlik öneriler
    "update_check": True,         # günde en fazla bir kez GitHub'da yeni sürüm denetle (kurulum onaylı)
    "update_last_check": None,    # son denetim (time.time)
    "persona": "asil_tembel",     # v2.0 kişilik şablonu
    "retro_mode": False,          # v2.0 90'lar retro pixel filtresi
    "age_days": 7.0,              # v2.0 büyüme/yaşlanma (gün)
    "boss_key_mode": True,        # v2.0 Ctrl+Shift+H patron tuşu modu
    "meow_subtitles": True,       # v2.0 kedi-insan altyazı çevirmeni
    "lofi_ambience": False,       # v2.0 odak lofi ambiyansı
    "affection_xp": 0,            # v2.0 dostluk XP
    "affection_level": 1,         # v2.0 dostluk seviyesi
    "weather_enabled": False,     # v2.2 gerçek hava durumu (açıkken şehir adı Open-Meteo'ya gider)
    "weather_city": "",
    "power_saver": True,          # v2.4 pil tasarrufu: bataryada/uykuda uyarlamalı düşük FPS
    "health_reminders": True,     # v2.5 opsiyonel su iç / gerin hatırlatıcısı
    "focus_sessions_completed": 0, # v2.5 tamamlanan odak (Pomodoro) seansı sayısı
}

SIZE_SCALES = {"small": 0.55, "normal": 1.0, "large": 1.3, "xlarge": 1.6}
SIZE_LABELS = {"small": "Küçük", "normal": "Orta", "large": "Büyük", "xlarge": "Kocaman"}


def config_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / APP_DIR_NAME


def config_path() -> Path:
    return config_dir() / FILE_NAME


def _type_ok(value, default) -> bool:
    """True when ``value`` has a type compatible with the default (None default = anything)."""
    if default is None:
        return True
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


class Settings:
    """Dict-backed settings with attribute-style ``get``/``set`` and autosave."""

    def __init__(self, data=None):
        self._data = dict(DEFAULTS)
        if data:
            self._data.update({k: v for k, v in data.items()
                               if k in DEFAULTS and _type_ok(v, DEFAULTS[k])})
        if self._data.get("persona") not in ("asil_tembel", "hiperaktif_yavru"):
            self._data["persona"] = DEFAULTS["persona"]   # kaldırılan kişilikler (bilge_yazilimci) varsayılana göç eder

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
            target = config_path()
            tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
            try:
                tmp.write_text(
                    json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                os.replace(tmp, target)
            finally:
                if tmp.exists():
                    tmp.unlink()
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
