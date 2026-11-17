"""Örnek eklenti: zar at / yazı tura. Rastgele ve güvenlidir (onay gerekmez)."""
import random

from pc_actions import ActionSpec


def zar_at(sides: int = 6) -> str:
    sides = max(2, min(int(sides), 1000))
    return f"{sides} yüzlü zar: {random.randint(1, sides)}"


def yazi_tura() -> str:
    return "Yazı!" if random.random() < 0.5 else "Tura!"


ACTIONS = [
    ActionSpec("zar_at", "Zar at (varsayılan 6 yüzlü) ve sonucu söyle.",
               {"properties": {"sides": {"type": "integer", "description": "Zarın yüz sayısı", "default": 6}},
                "required": ["sides"]}, zar_at, keywords=("zar",)),
    ActionSpec("yazi_tura", "Yazı tura at.", {"properties": {}, "required": []}, yazi_tura,
               keywords=("yazi", "tura")),
]
