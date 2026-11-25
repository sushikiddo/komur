"""4 bacaklı çevik, yumuşak gerçek kedi yürüyüşü: lateral sekans (LH->LF->RH->RF),
pürüzsüz iki kemikli IK, zarif pati kıvrımı ve yumuşak kedi topuğu.

Saf matematik (Tk yok). Koordinatlar renderer'ın 260x280 mantıksal kedi uzayındadır, +x = kedinin
baktığı yön. Adım fazı gerçek gövde hızından entegre edilir: duruş (stance) sırasında ayak yere
göre sabit kalır, yani ayak kayması olmaz.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

DUTY = 0.62                      # adım döngüsünün yerde geçen oranı (%62 duruş, %38 çevik salınım)
STRIDE = 34.0                    # kompakt, seri, zarif kedi adımı (mantıksal px)
LIFT = 13.5                      # salınım (swing) sırasında hafif, zıplak pati kalkışı
MIN_SPEED, MAX_SPEED = 48.0, 195.0  # mantıksal px/sn; yavaş yürüyüşte bile hafif ve canlı tempo
# Lateral sekans: her bacak bir öncekinin çeyrek döngü ardından kalkar (gerçek kedi yürüyüşü).
PHASE_OFFSETS = {"LH": 0.0, "LF": 0.25, "RH": 0.5, "RF": 0.75}


@dataclass
class Leg:
    hip: tuple[float, float]
    foot: tuple[float, float]
    joints: list[tuple[float, float]]   # kalçadan ayağa eklem zinciri (çizim için)
    lifted: bool
    swing_u: float = 0.0                # salınım ilerlemesi 0..1 (duruşta 0.0)
    stance_u: float = 0.0               # duruş ilerlemesi 0..1 (salınımda 0.0)
    paw_angle: float = 0.0              # salınım sırasında pati/bilek kıvrımı (derece)
    wrist: tuple[float, float] | None = None


@dataclass
class GaitPose:
    legs: dict[str, Leg] = field(default_factory=dict)
    bob: float = 0.0            # gövde dikey yaylanması
    spine: float = 0.0          # omurga dalgası (ön-arka karşıt eğim)
    shoulder: float = 0.0       # destek alan ön bacakta kürek kemiği kabarması
    hip_bob: float = 0.0        # arka kalça/pelvis salınımı
    shoulder_bob: float = 0.0   # ön omuz salınımı
    head_bob: float = 0.0       # dengelenmiş hafif kafa salınımı
    head_nod: float = 0.0       # adım ritmine uygun hafif kafa eğimi (derece)
    phase: float = 0.0          # mevcut yürüyüş döngüsü fazı 0..1
    speed_norm: float = 0.0     # normalize yürüyüş hızı 0..1


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
    """Faz (0..1) -> (gövdeye göre x ofseti, kalkış).

    Duruşta (0..DUTY) ayak gövdeye göre sabit doğrusal hızla geriye kayar (sıfır ayak kayması).
    Salınımda (DUTY..1) pati çevikçe kalkar, zarif kavisle öne uzanır ve yumuşakça basar.
    """
    phase %= 1.0
    if phase < DUTY:
        u = phase / DUTY
        return STRIDE * (0.5 - u), 0.0
    u = (phase - DUTY) / (1.0 - DUTY)
    eased = 0.5 - 0.5 * math.cos(math.pi * u)
    lift = LIFT * (math.sin(math.pi * u) ** 0.85)
    return STRIDE * (-0.5 + eased), max(0.0, lift)


class FelineGait:
    """Durumlu yürüyüş saati: ``pose`` her çağrıda fazı gerçek hıza göre ilerletir."""

    def __init__(self):
        self.phase = 0.0
        self._last_t: float | None = None

    def advance(self, t, speed):
        """``speed`` mantıksal px/sn. Döngü/sn = hız * DUTY / STRIDE (duruşta ayak yere sabit)."""
        speed = max(MIN_SPEED, min(MAX_SPEED, abs(speed)))
        if self._last_t is None:
            self._last_t = t
            self.phase = (t * speed * DUTY / STRIDE) % 1.0
            return self.phase
        dt = max(0.0, min(0.5, t - self._last_t))
        self._last_t = t
        self.phase = (self.phase + dt * speed * DUTY / STRIDE) % 1.0
        return self.phase

    def pose(self, t, speed, hips, ground):
        """``hips``: {"LH"/"LF"/"RH"/"RF": (x, y)} kalça/omuz noktaları. Ayaklar ``ground`` üstünde."""
        speed_clamped = max(MIN_SPEED, min(MAX_SPEED, abs(speed)))
        speed_norm = (speed_clamped - MIN_SPEED) / max(1.0, MAX_SPEED - MIN_SPEED)
        phase = self.advance(t, speed_clamped)
        cycle = 2.0 * math.pi * phase

        # Hafif, esnek, ritmik kedi yürüyüş yaylanması (asla ağır/hantal değil!)
        bob = -2.4 * abs(math.sin(2.0 * cycle))
        spine = 2.4 * math.sin(cycle)
        shoulder_bob = bob + 2.0 * math.sin(cycle + 0.4)
        hip_bob = bob - 2.0 * math.sin(cycle - 0.1)
        head_bob = -1.4 * math.sin(2.0 * cycle + 0.35)
        head_nod = 2.0 * math.sin(2.0 * cycle - 0.25)

        pose = GaitPose(
            bob=bob,
            spine=spine,
            hip_bob=hip_bob,
            shoulder_bob=shoulder_bob,
            head_bob=head_bob,
            head_nod=head_nod,
            phase=phase,
            speed_norm=speed_norm,
        )

        for name, hip in hips.items():
            leg_phase = (phase + PHASE_OFFSETS[name]) % 1.0
            dx, lift = foot_offset(leg_phase)
            lifted = lift > 0.0
            swing_u = 0.0 if not lifted else (leg_phase - DUTY) / (1.0 - DUTY)
            stance_u = (leg_phase / DUTY) if not lifted else 0.0
            front = name.endswith("F")

            hx = hip[0] + (1.2 * math.sin(cycle) if front else -1.0 * math.sin(cycle))
            hy = hip[1] + (shoulder_bob if front else hip_bob)
            foot = (hip[0] + dx, ground - lift)
            reach = max(28.0, ground - hy)

            if front:
                # Ön bacak: peluş kedi ön kolu — abartılı böcek dirseği olmadan yumuşak kıvrım!
                l1 = reach * 0.46
                l2 = reach * 0.57
                elbow = two_bone_ik((hx, hy), foot, l1, l2, bend=-1)
                joints = [(hx, hy), elbow, foot]
                if not lifted:
                    support = max(0.0, 1.0 - abs(dx) / (STRIDE * 0.55))
                    pose.shoulder = max(pose.shoulder, 3.6 * (support ** 0.85))
                    paw_angle = 6.0 * max(0.0, stance_u - 0.72) / 0.28
                    wrist = (
                        elbow[0] + (foot[0] - elbow[0]) * 0.72,
                        elbow[1] + (foot[1] - elbow[1]) * 0.72,
                    )
                else:
                    # Havadayken pati bilekten tatlıca kıvrılır, yere inmeden önce açılır
                    curl = math.sin(math.pi * swing_u) * (1.0 - 0.35 * swing_u)
                    paw_angle = -28.0 * curl
                    wrist = (
                        elbow[0] + (foot[0] - elbow[0]) * 0.70 + 2.4 * curl,
                        elbow[1] + (foot[1] - elbow[1]) * 0.70 - 1.6 * curl,
                    )
            else:
                # Arka bacak: yumuşak dolgun kalça -> nazik diz -> alçak doğal kedi topuğu -> küçük pati
                push_ext = max(0.0, -dx / (STRIDE * 0.5))
                fwd_reach = max(0.0, dx / (STRIDE * 0.5))
                swing_fold = math.sin(math.pi * swing_u) if lifted else 0.0
                hock_back = 5.5 + 2.2 * push_ext - 1.8 * fwd_reach + 1.5 * swing_fold
                hock_up = reach * (0.28 + 0.05 * swing_fold)
                hock = (foot[0] - hock_back, foot[1] - hock_up)
                knee = two_bone_ik((hx, hy), hock, reach * 0.44, reach * 0.42, bend=1)
                joints = [(hx, hy), knee, hock, foot]
                wrist = hock
                if lifted:
                    paw_angle = -20.0 * swing_fold
                else:
                    paw_angle = 8.0 * max(0.0, stance_u - 0.72) / 0.28

            pose.legs[name] = Leg(
                hip=(hx, hy),
                foot=foot,
                joints=joints,
                lifted=lifted,
                swing_u=swing_u,
                stance_u=stance_u,
                paw_angle=paw_angle,
                wrist=wrist,
            )
        return pose
