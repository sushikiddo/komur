from types import SimpleNamespace
from unittest.mock import MagicMock

import settings
from ai import CatAI
from assistant_ui import AssistantUI


def _ai(ctx):
    actions = MagicMock()
    actions.describe_for_prompt.return_value = ""
    return CatAI(lambda k, default=None: {"ai_backend": "offline"}.get(k, default), actions, context_provider=lambda: ctx)


def test_weather_goes_into_context_text():
    text = _ai({"summary": "", "weather": "Antalya 18°C açık"})._context_text()
    assert "Hava: Antalya 18°C açık" in text


def test_hava_nasil_uses_known_weather_offline():
    reply = _ai({"summary": "", "weather": "Antalya 18°C açık"})._respond_offline("Hava nasıl").reply
    assert "Antalya 18°C açık" in reply
    assert "bakamıyorum" in _ai({"summary": ""})._respond_offline("Hava nasıl").reply


def test_weather_text_formats_watcher():
    ui = SimpleNamespace(app=SimpleNamespace(weather=SimpleNamespace(condition="clear", temp=18.2, place="Antalya", city="")))
    assert AssistantUI.weather_text(ui) == "Antalya 18°C açık"
    ui.app.weather.condition = None
    assert AssistantUI.weather_text(ui) == ""


def test_removed_persona_and_dev_settings_migrate():
    loaded = settings.Settings({"persona": "bilge_yazilimci", "rubber_duck_mode": True, "dev_repo_path": "x"})
    assert loaded.get("persona") == "asil_tembel"
    assert "rubber_duck_mode" not in settings.DEFAULTS and "dev_repo_path" not in settings.DEFAULTS
    assert loaded.get("rubber_duck_mode") is None
