"""Procedural animation, visual evolution, costumes, retro filter, and desktop props.

Pure Python + Tkinter Canvas compatible module (< 800 lines) providing:
- SpringChain2D & EarSpring: Hooke's-law + damped spring physics with inertia
- GazeController: smooth lerp gaze tracking & pupil dilation
- AnimeEmotes: vector anime emotion bubbles ("!", "?", "Zzz", "heart", "anger", "dream")
- LayeredCostumes: new layered costumes ("witch_hat", "winter_set", "cyberpunk_collar", "headphones")
- GrowthStage: kitten-to-adult scaling, head proportion & step wobble
- RetroPixelFilter: 4px grid quantization, 16-bit color quantization & dither scanlines
- DesktopProps & PawPrintTrail: cardboard box, cat bed, laser dot, task fish, evaporating paw prints
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sys

_IS_MAC = sys.platform == "darwin"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * _clamp(t, 0.0, 1.0)


# ---------------------------------------------------------------------------
# 1. Spring physics for tail & ears
# ---------------------------------------------------------------------------

class SpringChain2D:
    """5-joint 2D spring chain using Hooke's law, damping, and motion inertia."""

    def __init__(
        self,
        num_joints: int = 5,
        segment_len: float = 16.0,
        stiffness: float = 140.0,
        damping: float = 14.0,
        inertia: float = 0.22,
        rest_angles: tuple[float, ...] | None = None,
    ):
        self.num_joints = max(2, int(num_joints))
        self.segment_len = float(segment_len)
        self.stiffness = float(stiffness)
        self.damping = float(damping)
        self.inertia = float(inertia)
        if rest_angles is None:
            # Gentle upward/curved tail rest posture
            self.rest_angles = tuple(-0.45 - i * 0.22 for i in range(self.num_joints))
        else:
            self.rest_angles = tuple(rest_angles)
        self.joints: list[tuple[float, float]] = [(0.0, 0.0)] * self.num_joints
        self.velocities: list[tuple[float, float]] = [(0.0, 0.0)] * self.num_joints
        self._prev_vel = (0.0, 0.0)
        self._initialized = False

    def reset(self, base_xy: tuple[float, float], facing: float = 1.0) -> list[tuple[float, float]]:
        bx, by = float(base_xy[0]), float(base_xy[1])
        sign = 1.0 if facing >= 0 else -1.0
        pts = [(bx, by)]
        cx, cy = bx, by
        for i in range(1, self.num_joints):
            ang = self.rest_angles[min(i, len(self.rest_angles) - 1)]
            cx -= sign * math.cos(ang) * self.segment_len
            cy += math.sin(ang) * self.segment_len
            pts.append((cx, cy))
        self.joints = pts
        self.velocities = [(0.0, 0.0)] * self.num_joints
        self._prev_vel = (0.0, 0.0)
        self._initialized = True
        return list(self.joints)

    def update(
        self,
        dt: float,
        base_xy: tuple[float, float],
        vel_xy: tuple[float, float] = (0.0, 0.0),
        facing: float = 1.0,
        wag_phase: float = 0.0,
        wag_amp: float = 0.0,
    ) -> list[tuple[float, float]]:
        if not self._initialized:
            self.reset(base_xy, facing=facing)
        bx, by = float(base_xy[0]), float(base_xy[1])
        self.joints[0] = (bx, by)
        self.velocities[0] = (0.0, 0.0)

        dt_clamped = _clamp(float(dt), 0.0, 0.05)
        if dt_clamped <= 0.0:
            return list(self.joints)

        vx_body, vy_body = float(vel_xy[0]), float(vel_xy[1])
        ax_body = (vx_body - self._prev_vel[0]) / max(dt_clamped, 1e-4)
        ay_body = (vy_body - self._prev_vel[1]) / max(dt_clamped, 1e-4)
        self._prev_vel = (vx_body, vy_body)

        sign = 1.0 if facing >= 0 else -1.0
        substeps = 2
        h = dt_clamped / substeps

        for _ in range(substeps):
            tx, ty = bx, by
            for i in range(1, self.num_joints):
                ang = self.rest_angles[min(i, len(self.rest_angles) - 1)]
                ang += math.sin(wag_phase - i * 0.55) * wag_amp
                tx -= sign * math.cos(ang) * self.segment_len
                ty += math.sin(ang) * self.segment_len

                jx, jy = self.joints[i]
                jvx, jvy = self.velocities[i]

                # Hooke's law toward rest target + damping + inertial lag
                fx = (tx - jx) * self.stiffness - jvx * self.damping - ax_body * self.inertia * (1.0 + i * 0.35)
                fy = (ty - jy) * self.stiffness - jvy * self.damping - ay_body * self.inertia * (1.0 + i * 0.35)

                jvx += fx * h
                jvy += fy * h
                jx += jvx * h
                jy += jvy * h

                # Segment-length constraint relative to parent joint
                px, py = self.joints[i - 1]
                dx, dy = jx - px, jy - py
                dist = math.hypot(dx, dy)
                if dist > 1e-6:
                    scale = self.segment_len / dist
                    # Soft pull toward exact segment length preserves spring stretchiness
                    jx = _lerp(jx, px + dx * scale, 0.65)
                    jy = _lerp(jy, py + dy * scale, 0.65)

                self.joints[i] = (jx, jy)
                self.velocities[i] = (jvx, jvy)

        return list(self.joints)


@dataclass
class EarState:
    layback: float
    twitch_left: float
    twitch_right: float
    mode: str

    def __getitem__(self, key: str):
        return getattr(self, key)


class EarSpring:
    """Spring-driven ear layback (for speed/startle) and micro-twitches."""

    def __init__(self, stiffness: float = 180.0, damping: float = 18.0):
        self.stiffness = float(stiffness)
        self.damping = float(damping)
        self.layback = 0.0
        self._layback_vel = 0.0
        self._twitch_l = 0.0
        self._twitch_r = 0.0

    def update(
        self,
        dt: float,
        speed: float = 0.0,
        mood: str = "calm",
        startled: bool = False,
        t: float = 0.0,
    ) -> EarState:
        dt_clamped = _clamp(float(dt), 0.0, 0.08)
        target = 0.0
        if startled or mood in ("hiss", "scared"):
            target = 1.0
        elif mood in ("play", "pounce"):
            target = 0.6
        elif mood in ("bored", "sleep"):
            target = 0.35
        target = max(target, _clamp(abs(float(speed)) / 240.0, 0.0, 0.85))

        if dt_clamped > 0.0:
            acc = (target - self.layback) * self.stiffness - self._layback_vel * self.damping
            self._layback_vel += acc * dt_clamped
            self.layback = _clamp(self.layback + self._layback_vel * dt_clamped, 0.0, 1.0)

        # Periodic quick ear twitches
        p_l = float(t) % 7.3
        p_r = (float(t) + 2.0) % 9.1
        self._twitch_l = math.sin(p_l / 0.28 * math.pi * 2) * 4.5 if p_l < 0.28 else 0.0
        self._twitch_r = math.sin(p_r / 0.28 * math.pi * 2) * 4.5 if p_r < 0.28 else 0.0

        if self.layback >= 0.8:
            mode = "flat"
        elif self.layback >= 0.45:
            mode = "back"
        elif mood in ("bored", "sleep") or self.layback >= 0.25:
            mode = "droop"
        else:
            mode = "up"

        return EarState(
            layback=self.layback,
            twitch_left=self._twitch_l,
            twitch_right=self._twitch_r,
            mode=mode,
        )


# ---------------------------------------------------------------------------
# 2. Smooth gaze & pupil dilation controller
# ---------------------------------------------------------------------------

class GazeController:
    """Smoothly tracks pointer coordinates and dilates pupils in dark/play."""

    def __init__(
        self,
        max_offset_x: float = 6.5,
        max_offset_y: float = 4.5,
        gaze_speed: float = 10.0,
        pupil_speed: float = 6.0,
    ):
        self.max_offset_x = float(max_offset_x)
        self.max_offset_y = float(max_offset_y)
        self.gaze_speed = float(gaze_speed)
        self.pupil_speed = float(pupil_speed)
        self.gaze: tuple[float, float] = (0.0, 0.0)
        self.pupil: float = 0.3

    @property
    def dilation(self) -> float:
        return self.pupil

    def update(
        self,
        dt: float,
        head_screen_xy: tuple[float, float],
        pointer_xy: tuple[float, float] | None,
        is_dark: bool = False,
        play_mode: bool = False,
    ) -> tuple[tuple[float, float], float]:
        dt_clamped = _clamp(float(dt), 0.0, 0.1)
        alpha_g = 1.0 - math.exp(-self.gaze_speed * dt_clamped) if dt_clamped > 0 else 1.0
        alpha_p = 1.0 - math.exp(-self.pupil_speed * dt_clamped) if dt_clamped > 0 else 1.0

        if pointer_xy is not None and head_screen_xy is not None:
            dx = float(pointer_xy[0]) - float(head_screen_xy[0])
            dy = float(pointer_xy[1]) - float(head_screen_xy[1])
            target_gx = _clamp(dx * 0.045, -self.max_offset_x, self.max_offset_x)
            target_gy = _clamp(dy * 0.045, -self.max_offset_y, self.max_offset_y)
        else:
            target_gx, target_gy = 0.0, 0.0

        self.gaze = (
            _lerp(self.gaze[0], target_gx, alpha_g),
            _lerp(self.gaze[1], target_gy, alpha_g),
        )

        target_pupil = 1.0 if play_mode else (0.85 if is_dark else 0.32)
        self.pupil = _lerp(self.pupil, target_pupil, alpha_p)
        return self.gaze, self.pupil


# ---------------------------------------------------------------------------
# 3. Vector anime emotes
# ---------------------------------------------------------------------------

class AnimeEmotes:
    """Draws vector anime emotion bubbles above the cat's head."""

    EMOTES = ("!", "?", "Zzz", "heart", "anger", "dream")

    @staticmethod
    def normalize(emote: str | None) -> str | None:
        if not emote:
            return None
        low = str(emote).strip().lower()
        mapping = {
            "!": "!",
            "alert": "!",
            "?": "?",
            "confused": "?",
            "zzz": "Zzz",
            "sleep": "Zzz",
            "heart": "heart",
            "love": "heart",
            "anger": "anger",
            "angry": "anger",
            "dream": "dream",
        }
        return mapping.get(low)

    @classmethod
    def draw(
        cls,
        canvas,
        head_xy: tuple[float, float],
        emote: str,
        progress: float = 0.0,
        scale: float = 1.0,
        tag: str = "cat_emote",
    ) -> list[int]:
        kind = cls.normalize(emote)
        if kind is None or canvas is None:
            return []

        hx, hy = float(head_xy[0]), float(head_xy[1])
        s = max(0.35, float(scale))
        bob = math.sin(float(progress) * math.pi * 2) * 3.0 * s
        cx = hx + 26.0 * s
        cy = hy - 54.0 * s + bob
        items: list[int] = []

        if kind == "!":
            r = 14.0 * s
            items.append(canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill="#fff6d6", outline="#d9483b", width=max(1.0, 2.0 * s), tags=tag,
            ))
            items.append(canvas.create_polygon(
                cx - 6 * s, cy + r - 2 * s, cx + 2 * s, cy + r - 2 * s, cx - 8 * s, cy + r + 8 * s,
                fill="#fff6d6", outline="#d9483b", width=max(1.0, 1.5 * s), tags=tag,
            ))
            items.append(canvas.create_text(
                cx, cy, text="!", fill="#d9483b",
                font=("Segoe UI", max(8, int(13 * s)), "bold"), tags=tag,
            ))
        elif kind == "?":
            r = 14.0 * s
            items.append(canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill="#eef6ff", outline="#3a7bd5", width=max(1.0, 2.0 * s), tags=tag,
            ))
            items.append(canvas.create_text(
                cx, cy, text="?", fill="#3a7bd5",
                font=("Segoe UI", max(8, int(13 * s)), "bold"), tags=tag,
            ))
        elif kind == "Zzz":
            for i, ch in enumerate(("z", "z", "Z")):
                p = (float(progress) + i * 0.28) % 1.0
                zx = cx + i * 7.0 * s + p * 8.0 * s
                zy = cy - i * 8.0 * s - p * 14.0 * s
                fsize = max(7, int((8 + i * 2) * s))
                items.append(canvas.create_text(
                    zx, zy, text=ch, fill="#b7c6e6",
                    font=("Segoe UI", fsize, "bold"), tags=tag,
                ))
        elif kind == "heart":
            r = 6.0 * s
            items.append(canvas.create_oval(
                cx - 2 * r, cy - r, cx, cy + r,
                fill="#ff5c7c", outline="#c72c48", width=max(1.0, 1.2 * s), tags=tag,
            ))
            items.append(canvas.create_oval(
                cx, cy - r, cx + 2 * r, cy + r,
                fill="#ff5c7c", outline="#c72c48", width=max(1.0, 1.2 * s), tags=tag,
            ))
            items.append(canvas.create_polygon(
                cx - 2 * r, cy + 1 * s, cx + 2 * r, cy + 1 * s, cx, cy + 2.4 * r,
                fill="#ff5c7c", outline="#c72c48", width=max(1.0, 1.2 * s), tags=tag,
            ))
        elif kind == "anger":
            # Classic 4-corner anime vein cross mark
            w = max(1.5, 2.2 * s)
            d = 4.0 * s
            arm = 8.0 * s
            for sx in (-1, 1):
                for sy in (-1, 1):
                    items.append(canvas.create_line(
                        cx + sx * d, cy + sy * arm,
                        cx + sx * d, cy + sy * d,
                        cx + sx * arm, cy + sy * d,
                        fill="#e63946", width=w, smooth=True, capstyle="round", tags=tag,
                    ))
        elif kind == "dream":
            # Thought cloud + small trailing puffs
            items.append(canvas.create_oval(
                cx - 12 * s, cy + 12 * s, cx - 6 * s, cy + 18 * s,
                fill="#ffffff", outline="#7f8fa6", width=max(1.0, 1.2 * s), tags=tag,
            ))
            items.append(canvas.create_oval(
                cx - 7 * s, cy + 4 * s, cx + 1 * s, cy + 12 * s,
                fill="#ffffff", outline="#7f8fa6", width=max(1.0, 1.2 * s), tags=tag,
            ))
            for ox, oy, rad in ((-10, -8, 10), (4, -12, 12), (16, -6, 9), (2, 0, 10)):
                items.append(canvas.create_oval(
                    cx + (ox - rad) * s, cy + (oy - rad) * s,
                    cx + (ox + rad) * s, cy + (oy + rad) * s,
                    fill="#ffffff", outline="#7f8fa6", width=max(1.0, 1.2 * s), tags=tag,
                ))
            # Mini fish silhouette inside dream bubble
            items.append(canvas.create_oval(
                cx - 4 * s, cy - 11 * s, cx + 10 * s, cy - 3 * s,
                fill="#6ec6ff", outline="#2f80ed", width=max(1.0, 1.0 * s), tags=tag,
            ))
            items.append(canvas.create_polygon(
                cx + 9 * s, cy - 7 * s, cx + 15 * s, cy - 11 * s, cx + 15 * s, cy - 3 * s,
                fill="#6ec6ff", outline="#2f80ed", width=max(1.0, 1.0 * s), tags=tag,
            ))

        return items


# ---------------------------------------------------------------------------
# 4. Layered costumes (extends CatRenderer's bow / scarf / hat / glasses)
# ---------------------------------------------------------------------------

class LayeredCostumes:
    """Draws layered costumes in head-local coordinates via CatRenderer helpers."""

    BASE_ACCESSORIES = (None, "bow", "scarf", "hat", "glasses")
    _CORE_LAYERED = ("witch_hat", "winter_set", "cyberpunk_collar", "headphones")
    try:
        from costumes import EXTRA_COSTUMES as _EXTRA_COSTUMES
    except Exception:
        _EXTRA_COSTUMES = ()
    NEW_COSTUMES = _CORE_LAYERED + _EXTRA_COSTUMES
    ALL_COSTUMES = BASE_ACCESSORIES + NEW_COSTUMES

    @classmethod
    def is_layered(cls, kind: str | None) -> bool:
        return kind in cls.NEW_COSTUMES

    @classmethod
    def draw(cls, renderer, kind: str | None, shape, size: float = 1.0, t: float = 0.0) -> bool:
        """Render one of the new layered costumes. Returns True if drawn."""
        if kind == "witch_hat":
            cls._draw_witch_hat(renderer, shape, size)
            return True
        if kind == "winter_set":
            cls._draw_winter_set(renderer, shape, size)
            return True
        if kind == "cyberpunk_collar":
            cls._draw_cyberpunk_collar(renderer, shape, t)
            return True
        if kind == "headphones":
            cls._draw_headphones(renderer, shape, size, t)
            return True
        try:
            from costumes import draw_extra_costume
            return draw_extra_costume(renderer, kind, shape, size=size, t=t)
        except Exception:
            return False

    @staticmethod
    def _draw_witch_hat(r, shape, size: float):
        brim_center = shape([(0, -39)])[0]
        r._ellipse(brim_center, 34 * size, 7 * size, "#231942", "#0f0a1e", 1.3)
        r._poly(shape([(-19, -40), (-12, -62), (4, -84), (16, -66), (19, -40)]), "#2d1e54", "#0f0a1e", 1.3, smooth=True)
        r._poly(shape([(-17, -45), (17, -45), (18, -39), (-18, -39)]), "#7b2cbf", "", 1)
        r._poly(shape([(-5, -46), (5, -46), (5, -38), (-5, -38)]), "#f8cd35", "#8d5b00", 1.1)

    @staticmethod
    def _draw_winter_set(r, shape, size: float):
        r._poly(shape([(-34, 34), (-16, 44), (0, 47), (16, 44), (34, 34), (36, 46), (16, 57), (0, 60), (-16, 57), (-36, 46)]), "#2a6f97", "#184e77", 1.2, smooth=True)
        r._poly(shape([(12, 50), (26, 48), (28, 74), (15, 76)]), "#2a6f97", "#184e77", 1.1)
        for sx in (-20, -4, 12):
            r._line(shape([(sx, 45), (sx + 2, 56)]), "#a9d6e5", 1.8)
        r._poly(shape([(-26, -34), (-22, -56), (0, -64), (22, -56), (26, -34)]), "#d64550", "#8e2430", 1.2, smooth=True)
        r._poly(shape([(-28, -37), (28, -37), (27, -29), (-27, -29)]), "#fffaf0", "#d8dfdf", 1.1, smooth=True)
        r._ellipse(shape([(0, -67)])[0], 8 * size, 8 * size, "#fffaf0", "#d8dfdf", 1.1)

    @staticmethod
    def _draw_cyberpunk_collar(r, shape, t: float):
        r._poly(shape([(-30, 36), (0, 46), (30, 36), (32, 46), (0, 56), (-32, 46)]), "#1b1f2a", "#434c5e", 1.3, smooth=True)
        neon = "#00f5d4" if (math.sin(float(t) * 6.0) + 1.0) * 0.5 > 0.35 else "#ff007f"
        r._line(shape([(-24, 42), (0, 50), (24, 42)]), neon, 2.4)
        r._poly(shape([(-7, 46), (7, 46), (5, 58), (-5, 58)]), "#0b0e14", neon, 1.4)
        r._line(shape([(-3, 52), (3, 52)]), "#ffbe0b", 1.8)

    @staticmethod
    def _draw_headphones(r, shape, size: float, t: float):
        bob = math.sin(float(t) * 8.0) * 1.8
        r._line(shape([(-42, -6 + bob), (-34, -36 + bob), (0, -48 + bob), (34, -36 + bob), (42, -6 + bob)]), "#2b2d42", 3.6)
        r._line(shape([(-20, -43 + bob), (0, -48 + bob), (20, -43 + bob)]), "#ef233c", 2.0)
        for s in (-1, 1):
            cup = shape([(s * 43, -4 + bob)])[0]
            r._ellipse(cup, 8.5 * size, 13.0 * size, "#2b2d42", "#8d99ae", 1.4)
            r._ellipse(cup, 4.5 * size, 8.0 * size, "#ef233c", "", 1.0)


# ---------------------------------------------------------------------------
# 5. Growth / aging system
# ---------------------------------------------------------------------------

@dataclass
class GrowthMetrics:
    age_days: float
    stage: str
    scale: float
    head_scale: float
    wobble: float


class GrowthStage:
    """Maps cat age in days to body scale, head ratio, and walking wobble."""

    KITTEN_MAX_DAYS = 3.0
    ADULT_MIN_DAYS = 7.0
    KITTEN_SCALE = 0.68
    KITTEN_HEAD_SCALE = 1.18

    @classmethod
    def evaluate(cls, age_days: float) -> GrowthMetrics:
        age = max(0.0, float(age_days))
        if age < cls.KITTEN_MAX_DAYS:
            return GrowthMetrics(
                age_days=age,
                stage="kitten",
                scale=cls.KITTEN_SCALE,
                head_scale=cls.KITTEN_HEAD_SCALE,
                wobble=1.0,
            )
        if age >= cls.ADULT_MIN_DAYS:
            return GrowthMetrics(
                age_days=age,
                stage="adult",
                scale=1.0,
                head_scale=1.0,
                wobble=0.0,
            )
        f = (age - cls.KITTEN_MAX_DAYS) / (cls.ADULT_MIN_DAYS - cls.KITTEN_MAX_DAYS)
        return GrowthMetrics(
            age_days=age,
            stage="juvenile",
            scale=_lerp(cls.KITTEN_SCALE, 1.0, f),
            head_scale=_lerp(cls.KITTEN_HEAD_SCALE, 1.0, f),
            wobble=_lerp(1.0, 0.0, f),
        )

    @classmethod
    def step_wobble(cls, t: float, age_days: float) -> tuple[float, float, float]:
        """Return (dx, dy, tilt_deg) for clumsy kitten steps."""
        m = cls.evaluate(age_days)
        if m.wobble <= 0.0:
            return (0.0, 0.0, 0.0)
        w = m.wobble
        dx = math.sin(float(t) * 5.2) * 3.5 * w
        dy = abs(math.sin(float(t) * 10.4)) * -2.8 * w
        tilt = math.sin(float(t) * 5.2) * 6.5 * w
        return (dx, dy, tilt)


# ---------------------------------------------------------------------------
# 6. Retro / 90s Pixel-Art filter
# ---------------------------------------------------------------------------

class RetroPixelFilter:
    """Quantizes Canvas items to a 4px grid, 16-bit RGB565 colors, and dither scanlines."""

    def __init__(self, grid_size: int = 4, scanline_step: int = 4):
        self.grid_size = max(2, int(grid_size))
        self.scanline_step = max(2, int(scanline_step))

    def quantize_coord(self, val: float) -> float:
        g = float(self.grid_size)
        return round(float(val) / g) * g

    def quantize_coords(self, coords: list[float] | tuple[float, ...]) -> list[float]:
        return [self.quantize_coord(v) for v in coords]

    @staticmethod
    def quantize_color(color: str) -> str:
        """Quantize a #RRGGBB color to 16-bit (RGB565) precision."""
        if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
            return color
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
        except ValueError:
            return color
        rq = (r >> 3) << 3
        gq = (g >> 2) << 2
        bq = (b >> 3) << 3
        return f"#{rq:02x}{gq:02x}{bq:02x}"

    def apply(
        self,
        canvas,
        tag: str | None = None,
        width: int = 260,
        height: int = 280,
        scanlines: bool = True,
        dither_tag: str = "retro_dither",
    ) -> int:
        """Apply pixel grid & 16-bit quantization to existing Canvas items and add dither."""
        if canvas is None:
            return 0
        try:
            canvas.delete(dither_tag)
        except Exception:
            pass

        try:
            item_ids = list(canvas.find_withtag(tag) if tag else canvas.find_all())
        except Exception:
            item_ids = []

        modified = 0
        for item_id in item_ids:
            try:
                coords = canvas.coords(item_id)
                if coords and len(coords) >= 2:
                    q_coords = self.quantize_coords(coords)
                    # Keep bounding boxes non-degenerate for ovals/rectangles
                    if len(q_coords) == 4 and canvas.type(item_id) in ("oval", "rectangle"):
                        if q_coords[0] == q_coords[2]:
                            q_coords[2] += self.grid_size
                        if q_coords[1] == q_coords[3]:
                            q_coords[3] += self.grid_size
                    canvas.coords(item_id, *q_coords)

                for opt in ("fill", "outline"):
                    try:
                        c = canvas.itemcget(item_id, opt)
                    except Exception:
                        c = ""
                    if c and isinstance(c, str) and c.startswith("#"):
                        canvas.itemconfigure(item_id, **{opt: self.quantize_color(c)})
                modified += 1
            except Exception:
                continue

        if scanlines and not (_IS_MAC and hasattr(canvas, "tk")):
            tags = (tag, dither_tag) if tag else dither_tag
            for idx, y in enumerate(range(0, int(height), self.scanline_step)):
                stipple = "gray50" if idx % 2 == 0 else "gray25"
                try:
                    canvas.create_line(
                        0, y, int(width), y,
                        fill="#0a0d13", stipple=stipple, width=1, tags=tags,
                    )
                except Exception:
                    break
        return modified


# ---------------------------------------------------------------------------
# 7. Desktop props & evaporating paw prints
# ---------------------------------------------------------------------------

def draw_cardboard_box(canvas, x: float, y: float, scale: float = 1.0, tag: str = "desktop_prop") -> list[int]:
    """Draw a cozy cardboard box at bottom-center (x, y)."""
    s = float(scale)
    w, h = 58 * s, 38 * s
    return [
        canvas.create_polygon(x - w, y - h, x + w, y - h, x + w * 0.92, y, x - w * 0.92, y, fill="#c69c6d", outline="#7c5832", width=max(1.0, 1.5 * s), tags=tag),
        canvas.create_polygon(x - w, y - h, x - w * 1.15, y - h - 14 * s, x - 4 * s, y - h - 10 * s, x, y - h, fill="#d9b382", outline="#7c5832", width=max(1.0, 1.2 * s), tags=tag),
        canvas.create_polygon(x, y - h, x + 4 * s, y - h - 10 * s, x + w * 1.15, y - h - 14 * s, x + w, y - h, fill="#d9b382", outline="#7c5832", width=max(1.0, 1.2 * s), tags=tag),
        canvas.create_rectangle(x - 6 * s, y - h, x + 6 * s, y - h + 16 * s, fill="#e6ccb2", outline="#9c7a54", width=1, tags=tag),
    ]


def draw_cat_bed(canvas, x: float, y: float, scale: float = 1.0, occupied: bool = False, tag: str = "desktop_prop") -> list[int]:
    """Draw a cushioned round cat bed centered at (x, y)."""
    s = float(scale)
    rx, ry = 54 * s, 20 * s
    cushion_color = "#f4a261" if occupied else "#e9c46a"
    return [
        canvas.create_oval(x - rx, y - ry, x + rx, y + ry, fill="#6d597a", outline="#355070", width=max(1.0, 1.8 * s), tags=tag),
        canvas.create_oval(x - rx * 0.78, y - ry * 0.68, x + rx * 0.78, y + ry * 0.68, fill=cushion_color, outline="#b56576", width=max(1.0, 1.2 * s), tags=tag),
    ]


def draw_laser_dot(canvas, x: float, y: float, t: float = 0.0, scale: float = 1.0, tag: str = "desktop_prop") -> list[int]:
    """Draw a glowing pulsing red laser pointer dot."""
    s = float(scale)
    r_outer = 8.0 * s * (1.0 + 0.25 * math.sin(float(t) * 14.0))
    r_inner = 3.5 * s
    if _IS_MAC and hasattr(canvas, "tk"):
        outer = canvas.create_oval(
            x - r_outer, y - r_outer, x + r_outer, y + r_outer,
            fill="", outline="#ff4d6d", width=max(1.0, 1.5 * s), tags=tag,
        )
    else:
        outer = canvas.create_oval(
            x - r_outer, y - r_outer, x + r_outer, y + r_outer,
            fill="#ff4d6d", outline="", stipple="gray50", tags=tag,
        )
    return [
        outer,
        canvas.create_oval(x - r_inner, y - r_inner, x + r_inner, y + r_inner, fill="#ff0a2f", outline="#fff0f3", width=1, tags=tag),
    ]


def draw_task_fish(canvas, x: float, y: float, t: float = 0.0, label: str = "", scale: float = 1.0, tag: str = "desktop_prop") -> list[int]:
    """Draw a floating task fish treat with optional short label."""
    s = float(scale)
    fy = y + math.sin(float(t) * 3.0) * 4.0 * s
    items = [
        canvas.create_polygon(x + 14 * s, fy, x + 24 * s, fy - 8 * s, x + 24 * s, fy + 8 * s, fill="#48cae4", outline="#0077b6", width=max(1.0, 1.2 * s), tags=tag),
        canvas.create_oval(x - 16 * s, fy - 9 * s, x + 16 * s, fy + 9 * s, fill="#90e0ef", outline="#0077b6", width=max(1.0, 1.4 * s), tags=tag),
        canvas.create_oval(x - 10 * s, fy - 3 * s, x - 6 * s, fy + 1 * s, fill="#03045e", outline="", tags=tag),
    ]
    if label:
        items.append(canvas.create_text(x, fy - 16 * s, text=str(label), fill="#023e8a", font=("Segoe UI", max(7, int(9 * s)), "bold"), tags=tag))
    return items


@dataclass
class _PawPrint:
    x: float
    y: float
    angle: float
    age: float = 0.0
    ttl: float = 3.5


class PawPrintTrail:
    """Manages evaporating transparent/stippled paw prints on a Canvas."""

    def __init__(self, ttl: float = 3.5, max_prints: int = 24):
        self.ttl = max(0.2, float(ttl))
        self.max_prints = max(1, int(max_prints))
        self.prints: list[_PawPrint] = []

    def add_print(self, x: float, y: float, angle: float = 0.0) -> None:
        self.prints.append(_PawPrint(float(x), float(y), float(angle), age=0.0, ttl=self.ttl))
        if len(self.prints) > self.max_prints:
            self.prints = self.prints[-self.max_prints:]

    def update(self, dt: float) -> None:
        dt_val = max(0.0, float(dt))
        alive: list[_PawPrint] = []
        for p in self.prints:
            p.age += dt_val
            if p.age < p.ttl:
                alive.append(p)
        self.prints = alive

    def draw(self, canvas, scale: float = 1.0, tag: str = "paw_print") -> list[int]:
        if canvas is None:
            return []
        try:
            canvas.delete(tag)
        except Exception:
            pass
        s = float(scale)
        items: list[int] = []
        mac_tk = _IS_MAC and hasattr(canvas, "tk")
        for p in self.prints:
            life = 1.0 - _clamp(p.age / p.ttl, 0.0, 1.0)
            if mac_tk and life < 0.35:
                continue
            if life > 0.72:
                stipple = "gray75"
            elif life > 0.45:
                stipple = "gray50"
            elif life > 0.2:
                stipple = "gray25"
            else:
                stipple = "gray12"

            # Main pad + 3 toe beans rotated by p.angle
            cos_a, sin_a = math.cos(p.angle), math.sin(p.angle)
            ps = s * (0.45 + 0.55 * life) if mac_tk else s
            kw = {} if mac_tk else {"stipple": stipple}
            r_pad = 4.2 * ps
            items.append(canvas.create_oval(
                p.x - r_pad, p.y - r_pad * 0.8, p.x + r_pad, p.y + r_pad * 0.8,
                fill="#52606d", outline="", tags=tag, **kw,
            ))
            for ox, oy in ((-4.2, -5.5), (0.0, -6.8), (4.2, -5.5)):
                tx = p.x + (ox * cos_a - oy * sin_a) * ps
                ty = p.y + (ox * sin_a + oy * cos_a) * ps
                rt = 1.9 * ps
                items.append(canvas.create_oval(
                    tx - rt, ty - rt, tx + rt, ty + rt,
                    fill="#52606d", outline="", tags=tag, **kw,
                ))
        return items
