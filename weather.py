"""Gerçek hava durumu (Open-Meteo, API anahtarı yok) ve kedinin üstündeki küçük hava bulutu.

Gizlilik: varsayılan KAPALI. Yalnız kullanıcı şehir girip açtığında şehir adı Open-Meteo'ya gider;
konum/IP sorgusu yapılmaz. Ağ isteği arka plan iş parçacığındadır, çizim döngüsü beklemez.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time
import urllib.parse
import urllib.request

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REFRESH_SECONDS = 1800.0
RETRY_SECONDS = 300.0

MESSAGES = {
    "rain": "Yağmur yağıyor… camdan izleyeyim. 🌧️",
    "storm": "Gök gürlüyor! Yanına sokulayım… ⛈️",
    "snow": "Kar yağıyor! Patilerim üşür. ❄️",
    "fog": "Dışarısı sisli, ben de mırıl mırıl uyuklarım. 🌫️",
    "hot": "Çok sıcak… serin bir yerde uzanayım. ☀️",
    "cold": "Hava buz gibi, kuyruğuma sarılıyorum. 🥶",
}
LABELS_TR = {"clear": "açık ☀️", "cloudy": "bulutlu ☁️", "fog": "sisli 🌫️", "rain": "yağmurlu 🌧️",
             "snow": "karlı ❄️", "storm": "fırtınalı ⛈️", "hot": "çok sıcak 🔥", "cold": "buz gibi 🥶"}
# Hava -> kedinin sakin duruşu (behavior.CatBrain.settle ile).
SETTLE = {"rain": "sit", "storm": "groom", "snow": "groom", "fog": "yawn", "hot": "sleep", "cold": "groom"}


def classify(code, temp_c):
    """WMO hava kodu + sıcaklık -> clear|cloudy|fog|rain|snow|storm|hot|cold."""
    code = int(code)
    if code >= 95:
        return "storm"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if code in (45, 48):
        return "fog"
    if temp_c is not None and temp_c >= 30:
        return "hot"
    if temp_c is not None and temp_c <= 0:
        return "cold"
    return "cloudy" if code in (2, 3) else "clear"


def _get_json(url, params, timeout=8.0):
    full = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full, timeout=timeout) as resp:   # noqa: S310 (sabit https adresleri)
        return json.loads(resp.read().decode("utf-8"))


def fetch_condition(city, get_json=_get_json):
    """Şehir adı -> (durum, sıcaklık, çözümlenen şehir adı). Bulunamazsa LookupError."""
    geo = get_json(GEOCODE_URL, {"name": city, "count": 1, "language": "tr", "format": "json"})
    results = geo.get("results") or []
    if not results:
        raise LookupError(city)
    place = results[0]
    data = get_json(FORECAST_URL, {"latitude": place["latitude"], "longitude": place["longitude"],
                                   "current": "temperature_2m,weather_code"})
    current = data.get("current") or {}
    temp = current.get("temperature_2m")
    return classify(current.get("weather_code", 0), temp), temp, place.get("name", city)


class WeatherWatcher:
    """Arka planda periyodik yeniler; ``take_change`` durum değiştiğinde bir kez döner."""

    def __init__(self, fetch=fetch_condition, clock=time.monotonic):
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self.city = ""
        self.condition = None
        self.temp = None
        self.place = ""
        self._next_fetch = 0.0
        self._busy = False
        self._changed = False
        self._announce = False

    def describe(self):
        """"Antalya: 18°C, açık ☀️" ya da henüz veri yoksa None."""
        if self.condition is None:
            return None
        temp = f"{round(self.temp)}°C, " if isinstance(self.temp, (int, float)) else ""
        return f"{self.place or self.city}: {temp}{LABELS_TR.get(self.condition, '')}".rstrip(", ")

    def request_announce(self):
        """Sıradaki (ya da hazırsa mevcut) sonucu take_announcement ile bir kez bildir."""
        with self._lock:
            self._announce = True

    def take_announcement(self):
        with self._lock:
            if not self._announce or self.condition is None:
                return None
            self._announce = False
        return self.describe()

    def set_city(self, city):
        with self._lock:
            self.city = (city or "").strip()
            self.condition = self.temp = None
            self._next_fetch = 0.0
            self._changed = False
            self._announce = bool(self.city)

    def poll(self, enabled):
        """Gerekirse arka plan yenilemesi başlat. Kapalıysa durumu temizler."""
        if not enabled or not self.city:
            self.condition = None
            return
        now = self._clock()
        with self._lock:
            if self._busy or now < self._next_fetch:
                return
            self._busy = True
            city = self.city
        threading.Thread(target=self._refresh, args=(city,), daemon=True).start()

    def _refresh(self, city):
        try:
            condition, temp, place = self._fetch(city)
            delay = REFRESH_SECONDS
        except Exception:
            logging.info("Hava durumu alınamadı", exc_info=True)
            condition = temp = None
            place = ""
            delay = RETRY_SECONDS
        with self._lock:
            self._busy = False
            self._next_fetch = self._clock() + delay
            if city != self.city or condition is None:
                return
            if condition != self.condition:
                self._changed = True
            self.condition, self.temp, self.place = condition, temp, place

    def take_change(self):
        with self._lock:
            if not self._changed:
                return None
            self._changed = False
            return self.condition


def draw_weather(renderer, kind, t):
    """Kedinin başının üstünde küçük bulut + yağmur/kar (renderer'ın mantıksal 260x280 uzayında)."""
    if kind == "clear":
        bob = math.sin(t * 1.5) * 1.5
        renderer._oval(108, 4 + bob, 128, 24 + bob, "#ffd84d", "#e0a800", 1)
        for k in range(8):
            a = t * 0.6 + k * math.pi / 4
            renderer._line([(118 + math.cos(a) * 14, 14 + bob + math.sin(a) * 14),
                            (118 + math.cos(a) * 19, 14 + bob + math.sin(a) * 19)], "#ffd84d", 2, smooth=False)
        return
    if kind == "hot":
        renderer._oval(110, 6, 126, 22, "#ff8a3d", "#c85a10", 1)
        return
    if kind == "cold":
        for k in range(3):
            x = 100 + k * 16
            renderer._line([(x - 5, 14), (x + 5, 14)], "#8ec8ff", 2, smooth=False)
            renderer._line([(x, 9), (x, 19)], "#8ec8ff", 2, smooth=False)
        return
    if kind == "cloudy":
        for cx, cy, r in ((106, 14, 11), (118, 9, 14), (131, 14, 10), (118, 17, 10)):
            renderer._oval(cx - r, cy - r * 0.8, cx + r, cy + r * 0.8, "#dfe6ec", "#aab6c2", 1)
        return
    if kind not in ("rain", "storm", "snow"):
        return
    cloud = "#5b6573" if kind == "storm" else "#c9d3dd"
    edge = "#3e4651" if kind == "storm" else "#9aa7b4"
    for cx, cy, r in ((96, 14, 15), (116, 7, 19), (138, 14, 14), (116, 18, 14)):
        renderer._oval(cx - r, cy - r * 0.8, cx + r, cy + r * 0.8, cloud, edge, 1)
    for i in range(9):
        x = 88 + (i * 7.3) % 60
        fall = (t * (30 if kind == "snow" else 90) + i * 9.7) % 26
        y = 28 + fall
        if kind == "snow":
            drift = math.sin(t * 2 + i) * 3
            renderer._oval(x + drift - 2.2, y - 2.2, x + drift + 2.2, y + 2.2, "#ffffff", "#b8c4d0", 1)
        else:
            renderer._line([(x, y), (x - 2, y + 8)], "#5aa0e6", 2, smooth=False)
    if kind == "storm" and (t % 4.0) < 0.12:
        renderer._line([(122, 24), (116, 36), (124, 38), (116, 52)], "#ffd84d", 3, smooth=False)
