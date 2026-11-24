import pytest
from intents import parse_intent


@pytest.mark.parametrize("text,action,args", [
    ("valorantıu aç", "open_app", {"name": "valorant"}),
    ("Valorant'ı aç", "open_app", {"name": "valorant"}),
    ("YouTube'dan Gülpembe çal", "youtube_play", {"query": "Gülpembe"}),
    ("YouTube’dan Gülpembe çal", "youtube_play", {"query": "Gülpembe"}),
    ("Gülpembe youtube'da ara aç", "youtube_play", {"query": "Gülpembe"}),
    ("YouTube'dan Bir Derdim Var çal", "youtube_play", {"query": "Bir Derdim Var"}),
    ("Kömür yerde yuvarlan", "cat_behavior", {"behavior": "roll"}),
    ("esne", "cat_behavior", {"behavior": "yawn"}),
    ("canın sıkılsın", "cat_behavior", {"behavior": "bored"}),
])
def test_natural_turkish_commands(text, action, args):
    parsed = parse_intent(text)
    assert parsed is not None
    assert parsed[0] == action
    assert parsed[1] == args


def test_regex_fast_path_does_not_overreach():
    from intents import parse_intent
    assert parse_intent("canım sıkıldı") is None or parse_intent("canım sıkıldı")[2] != "Ben de seni seviyorum. Mırrr."
    assert parse_intent("canım")[0] == "_chat"
    assert parse_intent("bilgisayarda yazı yazacağım bir program lazım") is None or \
        parse_intent("bilgisayarda yazı yazacağım bir program lazım")[0] != "system_info"
    assert parse_intent("ram durumu")[0] == "system_info"
