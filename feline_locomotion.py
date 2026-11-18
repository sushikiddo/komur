"""4 bacaklı kedi yürüyüşü: lateral sekans (LH->LF->RH->RF), iki kemikli IK, Z eklemli arka bacak.

Saf matematik (Tk yok). Koordinatlar renderer'ın 260x280 mantıksal kedi uzayındadır, +x = kedinin
baktığı yön. Adım fazı gerçek gövde hızından entegre edilir: duruş (stance) sırasında ayak yere
göre sabit kalır, yani ayak kayması olmaz.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

DUTY = 0.62                      # adım döngüsünün yerde geçen oranı
STRIDE = 30.0                    # bir döngüde ayağın gövdeye göre katettiği yol (mantıksal px)
LIFT = 9.0                       # salınım (swing) sırasında en yüksek ayak kalkışı
MIN_SPEED, MAX_SPEED = 18.0, 140.0  # mantıksal px/sn; çok yavaşta da bacaklar canlı görünsün
# Lateral sekans: her bacak bir öncekinin çeyrek döngü ardından kalkar.
PHASE_OFFSETS = {"LH": 0.0, "LF": 0.25, "RH": 0.5, "RF": 0.75}


@dataclass
class Leg:
    hip: tuple[float, float]
    foot: tuple[float, float]
    joints: list[tuple[float, float]]   # kalçadan ayağa eklem zinciri (çizim için)
    lifted: bool


@dataclass
class GaitPose:
    legs: dict[str, Leg] = field(default_factory=dict)
    bob: float = 0.0          # gövde dikey salınımı
    spine: float = 0.0        # omurga dalgası (ön-arka karşıt eğim)
    shoulder: float = 0.0     # destek alan ön bacakta kürek kemiği kabarması


def two_bone_ik(root, target, l1, l2, bend):
    """Kök->hedef arasında l1/l2 uzunluklu iki kemik için orta eklem. ``bend`` +1/-1 bükülme yönü."""
    dx, dy = target[0] - root[0], target[1] - root[1]
    dist = math.hypot(dx, dy)
    dist = max(abs(l1 - l2) + 1e-6, min(dist, l1 + l2 - 1e-6))
    cos_a = (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)
    a = math.acos(max(-1.0, min(1.0, cos_a)))
    base = math.atan2(dy, dx)
    ang = base - bend * a
    return (root[0] + math.cos(ang) * l1, root[1] + math.sin(ang) * l1)


def foot_offset(phase):
    """Faz (0..1) -> (gövdeye göre x ofseti, kalkış). Duruşta ayak geriye düz kayar, salınımda ileri kavis."""
    phase %= 1.0
    if phase < DUTY:
        u = phase / DUTY
        return STRIDE * (0.5 - u), 0.0
    u = (phase - DUTY) / (1.0 - DUTY)
    eased = 0.5 - 0.5 * math.cos(math.pi * u)
    return STRIDE * (-0.5 + eased), LIFT * math.sin(math.pi * u)


class FelineGait:
    """Durumlu yürüyüş saati: ``pose`` her çağrıda fazı gerçek hıza göre ilerletir."""

    def __init__(self):
        self.phase = 0.0
        self._last_t: float | None = None

    def advance(self, t, speed):
        """``speed`` mantıksal px/sn. Döngü/sn = hız * DUTY / STRIDE (duruşta ayak yere sabit)."""
        dt = 0.0 if self._last_t is None else max(0.0, min(0.1, t - self._last_t))
        self._last_t = t
        speed = max(MIN_SPEED, min(MAX_SPEED, abs(speed)))
        self.phase = (self.phase + dt * speed * DUTY / STRIDE) % 1.0
        return self.phase

    def pose(self, t, speed, hips, ground):
        """``hips``: {"LH"/"LF"/"RH"/"RF": (x, y)} kalça/omuz noktaları. Ayaklar ``ground`` üstünde."""
        phase = self.advance(t, speed)
        cycle = 2 * math.pi * phase
        pose = GaitPose(bob=-1.4 * abs(math.sin(2 * cycle)), spine=1.6 * math.sin(cycle))
        for name, hip in hips.items():
            leg_phase = phase + PHASE_OFFSETS[name]
            dx, lift = foot_offset(leg_phase)
            front = name.endswith("F")
            # Omurga dalgası: ön ve arka kuşak karşıt yönde iner/kalkar.
            hx, hy = hip[0], hip[1] + pose.bob + (pose.spine if front else -pose.spine)
            foot = (hip[0] + dx, ground - lift)
            reach = ground - hy
            if front:
                # Ön bacak: dirsek geride (kedi ön bacağı geriye bükülür).
                elbow = two_bone_ik((hx, hy), foot, reach * 0.52, reach * 0.56, bend=-1)
                joints = [(hx, hy), elbow, foot]
                if lift == 0.0:
                    pose.shoulder = max(pose.shoulder, 2.2 * (1 - abs(dx) / (STRIDE * 0.5)))
            else:
                # Arka bacak: diz ileride, topuk (hock) geride -> Z şekli.
                hock = (foot[0] - 7.0, foot[1] - reach * 0.36)
                knee = two_bone_ik((hx, hy), hock, reach * 0.42, reach * 0.40, bend=1)
                joints = [(hx, hy), knee, hock, foot]
            pose.legs[name] = Leg(hip=(hx, hy), foot=foot, joints=joints, lifted=lift > 0.0)
        return pose
