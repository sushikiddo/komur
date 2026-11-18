import pytest

from intents import parse_intent


@pytest.mark.parametrize("text", [
    "Bugün ne yapalım?",
    "Müzik açalım mı",
    "Notlarımı aç",
    "Ödevime yardım eder misin",
    "Film izleyelim mi",
    "Biraz dinlensek mi",
    "Bana yardım edebilir misin ödevimde",
])
def test_chat_sentences_not_commands(text):
    intent = parse_intent(text)
    assert intent is None or intent[0] == "_chat"
    if intent:
        assert "not defterini aç" not in intent[2]


@pytest.mark.parametrize("text,name", [
    ("Saat kaç", "get_time"),
    ("Bugün günlerden ne", "get_time"),
    ("not defterini aç", "open_app"),
    ("youtube'da lofi ara", "web_search"),
    ("sesi %30 yap", "set_volume"),
])
def test_real_commands_unchanged(text, name):
    assert parse_intent(text)[0] == name


@pytest.mark.parametrize("text", ["yardım", "neler yapabilirsin"])
def test_bare_help_lists_commands(text):
    intent = parse_intent(text)
    assert intent[0] == "_chat" and "not defterini aç" in intent[2]
