import threading

import pytest

from weather import WeatherWatcher, classify, fetch_condition


def test_classify_wmo_codes_and_temperature():
    assert classify(61, 12) == "rain" and classify(81, 12) == "rain"
    assert classify(73, -2) == "snow" and classify(95, 20) == "storm"
    assert classify(45, 10) == "fog"
    assert classify(0, 33) == "hot" and classify(1, -4) == "cold"
    assert classify(3, 15) == "cloudy" and classify(0, 15) == "clear"


def test_fetch_condition_uses_geocode_then_forecast():
    calls = []

    def fake(url, params):
        calls.append(params)
        if "geocoding" in url:
            return {"results": [{"latitude": 41.0, "longitude": 29.0, "name": "İstanbul"}]}
        return {"current": {"temperature_2m": 9.5, "weather_code": 63}}

    assert fetch_condition("istanbul", get_json=fake) == ("rain", 9.5, "İstanbul")
    assert calls[0]["name"] == "istanbul" and calls[1]["latitude"] == 41.0
    with pytest.raises(LookupError):
        fetch_condition("yok", get_json=lambda url, params: {"results": []})


def _wait_idle(watcher):
    for thread in threading.enumerate():
        if thread is not threading.current_thread() and thread.daemon and "_refresh" in str(thread._target):
            thread.join(2)


def test_watcher_is_off_by_default_and_reports_changes_once():
    seen = []
    clock = [0.0]
    watcher = WeatherWatcher(fetch=lambda city: (seen.append(city) or ("snow", -1, city)),
                             clock=lambda: clock[0])
    watcher.poll(enabled=True)                      # şehir yok -> ağ isteği yok
    watcher.set_city("Ankara")
    watcher.poll(enabled=False)                     # kapalı -> ağ isteği yok
    assert seen == []
    watcher.poll(enabled=True)
    _wait_idle(watcher)
    assert seen == ["Ankara"] and watcher.condition == "snow"
    assert watcher.take_change() == "snow" and watcher.take_change() is None
    watcher.poll(enabled=True)                      # 30 dk dolmadan yeniden sormaz
    _wait_idle(watcher)
    assert seen == ["Ankara"]
