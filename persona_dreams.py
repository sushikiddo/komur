"""Kömür — Dilim 4: Kişilik şablonları, gece rüya motoru, donanım zihni
ve kedi-insan çevirmeni.
"""
from __future__ import annotations

import datetime as _dt
import math
import re
import sys
from pathlib import Path
from typing import Any, Callable

from memory_store import MemoryStore, redact

IS_WINDOWS = sys.platform == "win32"

# ---------------------------------------------------------------------------
# 1. Kişilik Şablonları (PERSONA_TEMPLATES)
# ---------------------------------------------------------------------------
PERSONA_TEMPLATES: dict[str, dict[str, Any]] = {
    "asil_tembel": {
        "id": "asil_tembel",
        "name": "Asil / Tembel",
        "mbti": "INTJ",
        "description": "Ağırbaşlı, biraz üstten bakan ama içten seven, az hareket eden asil smokin kedi.",
        "traits": ["ağırbaşlı", "seçici", "az hareketli", "gizliden şefkatli", "stratejik"],
        "energy_bias": -15,
        "system_prompt_addition": (
            "Kişilik Modu — Asil / Tembel (INTJ): Ağırbaşlı, hafif kibirli ama kullanıcıya derinden bağlı bir "
            "smokin kedisi gibi konuş. Gereksiz yere heyecanlanma, az kelimeyle keskin gözlemler yap. "
            "Arada mülkün sahibiymişsin gibi davran ama işini sessizce ve kusursuz hallet."
        ),
    },
    "hiperaktif_yavru": {
        "id": "hiperaktif_yavru",
        "name": "Hiperaktif Yavru",
        "mbti": "ENFP",
        "description": "Çok enerjik, her şeye şaşıran, meraklı ve bol oyun isteyen neşeli kedi.",
        "traits": ["enerjik", "meraklı", "oyuncu", "coşkulu", "şaşkın"],
        "energy_bias": 25,
        "system_prompt_addition": (
            "Kişilik Modu — Hiperaktif Yavru (ENFP): Kısa cümlelerinde yüksek enerji ve merak olsun. "
            "Her yeni dosya, pencere veya fikir seni heyecanlandırsın; araya minik oyun davetleri sıkıştır "
            "ama konudan kopma ve yardımcı olmaya devam et."
        ),
    },
}


def get_persona(persona_id: str | None) -> dict[str, Any]:
    """Kayıtlı kişilik şablonunu döndürür; bilinmiyorsa 'asil_tembel' döner."""
    key = (persona_id or "asil_tembel").strip().lower()
    return dict(PERSONA_TEMPLATES.get(key, PERSONA_TEMPLATES["asil_tembel"]))


def list_personas() -> list[dict[str, Any]]:
    """Kullanılabilir tüm kişilik şablonlarını listeler."""
    return [dict(item) for item in PERSONA_TEMPLATES.values()]


def build_persona_prompt(persona_id: str | None, base_prompt: str = "") -> str:
    """Temel sistem istemine seçili kişilik yönergesini ekler."""
    persona = get_persona(persona_id)
    addition = persona["system_prompt_addition"]
    base = (base_prompt or "").strip()
    return f"{base}\n\n{addition}" if base else addition


# ---------------------------------------------------------------------------
# 2. Donanım Sıcaklığı Tepkisi (HardwareMind)
# ---------------------------------------------------------------------------
def _valid_celsius(value: Any) -> float | None:
    try:
        temp = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(temp) or temp < -20.0 or temp > 150.0:
        return None
    return round(temp, 1)


class HardwareMind:
    """CPU sıcaklığını okuyup yüksek sıcaklıkta kedi tepkisi üretir."""

    HOT_THRESHOLD = 75.0
    HOT_MESSAGE = "İşlemci sıcacık, tam yatmalık!"

    def __init__(
        self,
        temp_probe: Callable[[], float | None] | None = None,
        hot_threshold: float = HOT_THRESHOLD,
    ) -> None:
        self._temp_probe = temp_probe
        self.hot_threshold = float(hot_threshold)

    def read_cpu_temp(self) -> float | None:
        """CPU sıcaklığını °C olarak okur; erişilemezse güvenli biçimde None döner."""
        if self._temp_probe is not None:
            try:
                return _valid_celsius(self._temp_probe())
            except Exception:
                return None

        temp = self._read_psutil_temp()
        if temp is not None:
            return temp

        if IS_WINDOWS:
            temp = self._read_windows_wmi_temp()
            if temp is not None:
                return temp

        return None

    @staticmethod
    def _read_psutil_temp() -> float | None:
        try:
            import psutil  # type: ignore

            fn = getattr(psutil, "sensors_temperatures", None)
            if not callable(fn):
                return None
            sensors = fn(fahrenheit=False) or {}
        except Exception:
            return None

        preferred = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz")
        candidates: list[float] = []
        for key in preferred:
            for entry in sensors.get(key, ()) or ():
                val = _valid_celsius(getattr(entry, "current", None))
                if val is not None and val > 0.0:
                    candidates.append(val)
        if not candidates:
            for entries in sensors.values():
                for entry in entries or ():
                    val = _valid_celsius(getattr(entry, "current", None))
                    if val is not None and val > 0.0:
                        candidates.append(val)
        return round(max(candidates), 1) if candidates else None

    @staticmethod
    def _read_windows_wmi_temp() -> float | None:
        try:
            import wmi  # type: ignore
        except Exception:
            return None

        # 1) LibreHardwareMonitor / OpenHardwareMonitor
        for namespace in ("root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"):
            try:
                conn = wmi.WMI(namespace=namespace)
                temps = []
                for sensor in conn.Sensor(SensorType="Temperature"):
                    name = str(getattr(sensor, "Name", "") or "").lower()
                    if any(tag in name for tag in ("cpu", "core", "package", "tdie", "tctl")):
                        val = _valid_celsius(getattr(sensor, "Value", None))
                        if val is not None and val > 0.0:
                            temps.append(val)
                if temps:
                    return round(max(temps), 1)
            except Exception:
                pass

        # 2) ACPI Thermal Zone (onda-kelvin -> °C)
        try:
            conn = wmi.WMI(namespace="root\\WMI")
            temps = []
            for zone in conn.MSAcpi_ThermalZoneTemperature():
                raw = getattr(zone, "CurrentTemperature", None)
                if raw is not None:
                    celsius = (float(raw) / 10.0) - 273.15
                    val = _valid_celsius(celsius)
                    if val is not None and val > 0.0:
                        temps.append(val)
            if temps:
                return round(max(temps), 1)
        except Exception:
            pass

        return None

    def evaluate(self) -> dict[str, Any] | None:
        """Sıcaklık eşik değerindeyse ısınma/yatma tepkisi döndürür."""
        temp = self.read_cpu_temp()
        if temp is None or temp < self.hot_threshold:
            return None
        return {
            "pose": "thermal_bask",
            "message": self.HOT_MESSAGE,
            "temp": temp,
        }


# ---------------------------------------------------------------------------
# 3. Gece Rüya Motoru (DreamEngine)
# ---------------------------------------------------------------------------
class DreamEngine:
    """Uyku veya gece saatlerinde gün içi notlardan hazır kalıplarla komik kedi rüyaları üretir (ağ yok)."""

    NIGHT_START_HOUR = 23
    NIGHT_END_HOUR = 6

    def __init__(self, memory_store: MemoryStore) -> None:
        self.memory_store = memory_store

    @classmethod
    def is_dream_time(cls, is_sleeping: bool = False, hour: int | None = None) -> bool:
        if is_sleeping:
            return True
        current_hour = _dt.datetime.now().hour if hour is None else int(hour) % 24
        return current_hour >= cls.NIGHT_START_HOUR or current_hour < cls.NIGHT_END_HOUR

    def collect_source_context(self, message_limit: int = 8, note_limit: int = 5) -> tuple[list[str], str]:
        messages = self.memory_store.messages(limit=message_limit)
        notes = self.memory_store.notes(limit=note_limit)
        snippets: list[str] = []
        for note in notes:
            text = str(note.get("content", "")).strip()
            if text:
                snippets.append(text[:120])
        for msg in messages:
            text = str(msg.get("content", "")).strip()
            if text:
                snippets.append(text[:120])
        summary = " | ".join(snippets[:6])[:500]
        return snippets, summary

    @staticmethod
    def _pick_topic(snippets: list[str]) -> str:
        if not snippets:
            return ""
        joined = " ".join(snippets)
        words = [w.strip(".,!?;:\"'()[]{}") for w in joined.split()]
        meaningful = [w for w in words if len(w) >= 4]
        return meaningful[0].lower() if meaningful else ""

    @classmethod
    def _synthesize_offline_dream(cls, snippets: list[str]) -> str:
        joined_lower = " ".join(snippets).lower()
        topic = cls._pick_topic(snippets)

        if any(k in joined_lower for k in ("python", "kod", "bug", "hata", "git", "test", "commit", "pytest")):
            if topic:
                return (
                    f"Kırmızı lazer noktasının aslında '{topic}' satırında saklanan bir bug olduğunu "
                    "sanıp sabaha kadar klavye tuşlarının üstünde yakalamaya çalışıyordum."
                )
            return (
                "Bütün syntax hataları minik parlak böceklere dönüşmüştü, patimle tek tek yakalayıp "
                "sıcak laptop adaptörünün üstünde uyuyakaldım."
            )
        if any(k in joined_lower for k in ("oyun", "valorant", "steam", "lol", "minecraft")):
            return (
                "Ekranın içindeki piksellerle kovalamaca oynarken kazara altın bir balık düşürdüm, "
                "skor tablosunun tepesinde mırlayarak şekerleme yapıyordum."
            )
        if any(k in joined_lower for k in ("çay", "kahve", "yemek", "balık", "mama")):
            return (
                "Klavyenin yanındaki kupadan buhar yerine somon kokusu yükseliyordu, ben de bütün "
                "masayı balık krallığı ilan edip başköşeye kuruldum."
            )
        if topic:
            return (
                f"Gün boyu aklımda kalan '{topic}' kelimesi dev bir yumak olmuştu; onunla bütün "
                "masaüstünü turlayıp sonunda monitörün tepesinde uykuya daldım."
            )
        return (
            "Uçan ton balıkları pencereden süzülürken ben de mekanik klavyenin en sıcak tuşunu "
            "yastık yapıp mırıl mırıl uyuyordum."
        )

    @staticmethod
    def format_bubble(dream_text: str) -> str:
        return f"💭 Rüyasında: {dream_text.strip()}"

    def generate_dream(
        self,
        is_sleeping: bool = True,
        hour: int | None = None,
        force: bool = False,
    ) -> dict[str, Any] | None:
        """Koşullar uygunsa rüya üretir, MemoryStore'a kaydeder ve balon metnini döndürür."""
        if not force and not self.is_dream_time(is_sleeping=is_sleeping, hour=hour):
            return None

        snippets, source_summary = self.collect_source_context()
        dream_text = self._synthesize_offline_dream(snippets)
        dream_text = redact(dream_text).strip()[:4000]
        dream_id = self.memory_store.add_dream(dream_text, source_summary=source_summary)
        return {
            "id": dream_id,
            "dream_text": dream_text,
            "source_summary": source_summary,
            "bubble": self.format_bubble(dream_text),
        }

    def dream_bubble(self, dream_text: str | None = None) -> str | None:
        if dream_text is not None:
            cleaned = dream_text.strip()
            return self.format_bubble(cleaned) if cleaned else None
        latest = self.memory_store.latest_dream()
        if not latest:
            return None
        return self.format_bubble(latest["dream_text"])


# ---------------------------------------------------------------------------
# Yardımcı
# ---------------------------------------------------------------------------
def _tr_lower(text: str) -> str:
    return (text or "").replace("I", "ı").replace("İ", "i").lower()


# ---------------------------------------------------------------------------
# 6. Kedi-İnsan Çevirmeni (MeowTranslator)
# ---------------------------------------------------------------------------
class MeowTranslator:
    """Kedinin seslerini durum, ruh hali, açlık ve saate göre komik Türkçe altyazıya çevirir."""

    @staticmethod
    def _normalize_sound(sound_kind: str) -> str:
        s = _tr_lower(sound_kind).strip()
        if any(k in s for k in ("hiss", "tıs", "fıs")):
            return "hiss"
        if any(k in s for k in ("purr", "mır")):
            return "purr"
        if any(k in s for k in ("chirp", "cıvıl", "trill", "prr")):
            return "chirp"
        return "meow"

    def translate_meow(
        self,
        sound_kind: str,
        state: str = "idle",
        mood: int = 70,
        hunger: int = 20,
        hour: int | None = None,
    ) -> str:
        sound = self._normalize_sound(sound_kind)
        state_l = _tr_lower(state).strip()
        mood_val = int(mood)
        hunger_val = int(hunger)
        hr = _dt.datetime.now().hour if hour is None else int(hour) % 24
        is_night = hr >= 23 or hr < 6

        if sound == "hiss":
            if "hiss" in state_l or "error" in state_l:
                return "Altyazı: 'Bu bug kesin senin değil derleyicinin suçu, tıss!'"
            if hunger_val >= 80:
                return "Altyazı: 'Mama kabının dibi göründü, acil kriz ilan ediyorum!'"
            return "Altyazı: 'Şu an bana yaklaşma, kritik bir düşünce sürecindeyim.'"

        if sound == "purr":
            if state_l == "thermal_bask":
                return "Altyazı: 'İşlemci fırın gibi, mırıl mırıl bedava hamam keyfi...'"
            if state_l == "sleep" or is_night:
                return "Altyazı: 'Motoru rölantiye aldım, rüyamda somon yakalıyorum...'"
            if mood_val >= 75:
                return "Altyazı: 'Keyfim gıcır, seninle aynı masayı paylaşmak fena değil.'"
            return "Altyazı: 'Tamam tamam, fena insan değilsin, devam et.'"

        if sound == "chirp":
            return "Altyazı: 'İmleç kıpırdadı! Av başlasın mı, yoksa kod mu yazıyoruz?'"

        # meow (varsayılan)
        if hunger_val >= 70:
            return "Altyazı: 'Kodu bırak, önce şu balık stoğunu kontrol et; midem zil çalıyor!'"
        if state_l == "dance":
            return "Altyazı: 'Yeşil testlerin şerefine masada zafer turu atıyorum!'"
        if is_night:
            return "Altyazı: 'Saat gece yarısını geçti, ya uyuyoruz ya da koridorda 3.00 koşusuna çıkıyorum.'"
        if state_l == "sleep":
            return "Altyazı: 'Beş dakika daha uyuyacağım, alarmı ertele lütfen.'"
        if mood_val < 35:
            return "Altyazı: 'İlgisizlikten patilerim kurudu, iki sevgi puanı fena olmazdı.'"
        if state_l == "coding":
            return "Altyazı: 'O satırdaki paranteze dikkat et derim, ama yine de sen bilirsin.'"
        return "Altyazı: 'Buradayım, masanın nöbeti bende. Sırada ne var?'"


def translate_meow(
    sound_kind: str,
    state: str = "idle",
    mood: int = 70,
    hunger: int = 20,
    hour: int | None = None,
) -> str:
    """Modül düzeyi kolaylık sarmalayıcısı."""
    return MeowTranslator().translate_meow(
        sound_kind=sound_kind,
        state=state,
        mood=mood,
        hunger=hunger,
        hour=hour,
    )
