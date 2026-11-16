import pytest
from ai import parse_intent


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
