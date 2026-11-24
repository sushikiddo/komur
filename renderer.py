"""Draw an animated realistic domestic cat in a 260 by 280 logical frame.

Colors are class attributes so a palette/skin can be swapped by overriding them
(see skins.py). Geometry is expressed in the logical 260x280 space and scaled to
the real canvas size by ``_xy``. Every derived shade (under-coat shadow, coat
sheen, ear inner, iris limbal ring, closed eyelids…) is blended at draw time
from the palette attributes, so all 7 skins recolor organically.

Poses (chosen from ``brain.state``):
    sit / look / purr_idle / chirp / knead / groom / yawn / sneeze  -> sitting
    wander / follow                                                -> walking
    play                                                           -> crouch/pounce
    bored                                                          -> drooping sit
    roll                                                           -> reclining side-roll
    stretch                                                        -> bow stretch
    hiss                                                           -> arched back
    sleep                                                          -> curled doughnut
Unknown states fall back to sitting. ``facing`` < 0 mirrors the whole frame.

Optional brain attributes (read with getattr, all have defaults):
    ball_x, ball_y (window px), ball_vx, ball_vy, pounce (0..1),
    pupil_dilation (0..1 override), low_light (bool), elapsed (s in state).
"""
import math
import sys
import time

_IS_MAC = sys.platform == "darwin"

from procedural_anim import (
    AnimeEmotes,
    EarSpring,
    GazeController,
    GrowthStage,
    LayeredCostumes,
    PawPrintTrail,
    RetroPixelFilter,
    SpringChain2D,
    draw_cardboard_box,
    draw_cat_bed,
    draw_laser_dot,
    draw_task_fish,
)
import cat_poses


def _hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def blend(c1, c2, f):
    """Mix two hex colors: f=0 -> c1, f=1 -> c2."""
    f = max(0.0, min(1.0, f))
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(3))


def luminance(color):
    r, g, b = _hex_to_rgb(color)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def _no_black_key(color):
    """Keep colors safely above macOS's near-black chroma-key ramp (max channel >= 12)."""
    r, g, b = _hex_to_rgb(color)
    top = max(r, g, b)
    if top < 12:
        boost = 12 - top
        r = min(255, r + boost // 2)
        g = min(255, g + boost // 2)
        b = min(255, b + boost)
    return "#%02x%02x%02x" % (r, g, b)


class CatRenderer:
    INK = "#0a0d13"
    FUR = "#11151b"
    FUR_LIGHT = "#222831"
    FUR_EDGE = "#2c333d"
    WHITE = "#fffaf2"
    WHITE_SHADE = "#d8dce0"
    GOLD = "#e6e145"
    GOLD_LIGHT = "#f8f694"
    GOLD_DARK = "#a7ad24"
    PINK = "#ea8192"
    MOUTH = "#7c858c"
    BALL = "#e99444"
    BALL_DARK = "#8d4c32"
    BALL_LIGHT = "#ffda90"
    TAG = "cat_renderer"
    GROUND = 262.0
    LOW_LIGHT_HOURS = frozenset((21, 22, 23, 0, 1, 2, 3, 4, 5, 6))
    accessory = None       # None | "bow" | "scarf" | "hat" | "glasses" | layered costumes
    time_of_day = "day"    # "day" | "evening" | "night"
    _dance_tilt = 0.0
    _reaction = "none"
    _last_anim_time = None
    _head_logical = (118.0, 108.0)
    _growth_scale = 1.0
    _growth_head_scale = 1.0
    _gaze_override = None
    _ear_override = None
    _gait = None
    _walk_sample = None
    use_procedural_springs = True
    retro_enabled = False
    tail_spring = None
    ear_spring = None
    gaze_controller = None
    retro_filter = None
    scale = 1.0
    width = 260
    height = 280
    ACCESSORIES = (None, "bow", "scarf", "hat", "glasses")
    ALL_ACCESSORIES = LayeredCostumes.ALL_COSTUMES
    TIMES_OF_DAY = ("day", "evening", "night")
    ACC_RED = "#c23b3b"
    ACC_RED_DARK = "#7e1f26"
    ACC_METAL = "#d5dbe0"
    CORN_BUCKET = "#f6e4c5"
    CORN_STRIPE = "#db6656"
    CORN_KERNEL = "#fff2bd"

    def __init__(self, canvas, width=260, height=280):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.scale = min(width / 260, height / 280)
        self.left = (width - 260 * self.scale) / 2
        self.top = (height - 280 * self.scale) / 2
        self.dx = 0.0
        self.dy = 0.0
        self.flip = False
        self.effect_orchestrator = None
        self.micro_time = 0.0
        self.idle_sway = 0.0
        self.item_count = 0
        self.tail_spring = SpringChain2D()
        self.ear_spring = EarSpring()
        self.gaze_controller = GazeController()
        self.retro_filter = RetroPixelFilter()
        self.use_procedural_springs = True
        self.retro_enabled = False
        self._last_anim_time = None
        self._head_logical = (118.0, 108.0)
        self._growth_scale = 1.0
        self._growth_head_scale = 1.0
        self._gaze_override = None
        self._ear_override = None
        self._reaction = "none"
        self._gait = None            # feline_locomotion.FelineGait
        self._walk_sample = None     # (t, x, y) body speed estimator

    def set_retro_mode(self, enabled: bool):
        """Enable or disable the 90s retro pixel/dither post-filter."""
        self.retro_enabled = bool(enabled)

    def set_effect_orchestrator(self, eo):
        """Wire the effect orchestrator into the renderer."""
        self.effect_orchestrator = eo

    # -- derived palette ----------------------------------------------------
    def _palette(self):
        fur_lum = luminance(self.FUR)
        dark_fur = fur_lum < 0.45
        very_light_fur = fur_lum > 0.78
        self._dark_fur = dark_fur
        self._very_light_fur = very_light_fur
        self._ink = _no_black_key(self.INK)
        self._coat = _no_black_key(self.FUR)
        # Plush velvet coat shading: rich deep shadow on dark coats, gentle warm tone on light coats
        self._coat_shadow = _no_black_key(
            blend(self.FUR, self.INK, 0.52) if dark_fur else blend(self.FUR, self.FUR_EDGE, 0.34)
        )
        self._belly = _no_black_key(
            blend(self.INK, self.FUR, 0.20) if dark_fur else blend(self.FUR_EDGE, self.INK, 0.22)
        )
        self._far_fur = _no_black_key(
            blend(self.INK, self.FUR, 0.42) if dark_fur else blend(self.FUR, self.FUR_EDGE, 0.54)
        )
        # Soft, plush velvety mid-tone & subtle sheen (NEVER harsh gray patches on black fur!)
        self._fur_mid = _no_black_key(
            blend(self.FUR, self.FUR_LIGHT, 0.16 if dark_fur else 0.24)
        )
        self._fur_sheen = _no_black_key(
            blend(self.FUR, self.FUR_LIGHT, 0.28) if dark_fur else blend(self.FUR_LIGHT, self.WHITE, 0.16)
        )
        self._muzzle_puff = _no_black_key(
            blend(self.FUR, self.FUR_LIGHT, 0.12) if dark_fur else blend(self.FUR, self.FUR_EDGE, 0.12)
        )
        # Ultra-soft velvety rim (ZERO harsh gray outlines on dark coats!)
        self._outline = _no_black_key(
            blend(self.FUR, self.FUR_EDGE, 0.12) if dark_fur else blend(self.FUR_EDGE, self.INK, 0.14)
        )
        self._soft_edge = _no_black_key(
            blend(self.FUR, self.INK, 0.44) if dark_fur else blend(self.FUR_EDGE, self.FUR, 0.32)
        )
        # Inner ear: plush deep velvet + subtle silvery-gray feathery tufts on dark coats; soft warm peach on light coats
        if dark_fur:
            self._ear_depth = _no_black_key(blend(self.INK, self.FUR, 0.24))
            self._ear_inner = _no_black_key(blend(self.FUR, self.FUR_LIGHT, 0.22))
            self._ear_inner_light = _no_black_key(blend(self.FUR_LIGHT, self.WHITE, 0.12))
            self._ear_tuft = blend(self.FUR_LIGHT, self.WHITE, 0.42)
        else:
            self._ear_depth = _no_black_key(blend(self.FUR_EDGE, self.PINK, 0.24))
            self._ear_inner = blend(self.PINK, self.FUR, 0.58)
            self._ear_inner_light = blend(self.PINK, self.WHITE, 0.30)
            self._ear_tuft = blend(self.WHITE, self.FUR_LIGHT, 0.30)
        # Nose: cute matte jet-charcoal velvet triangle on dark coats (like real Kömür!), soft rose on light coats
        if dark_fur:
            self._nose = _no_black_key(blend(self.INK, self.FUR_LIGHT, 0.24))
            self._nose_hi = _no_black_key(blend(self.FUR_LIGHT, self.WHITE, 0.26))
            self._nose_dark = _no_black_key(self.INK)
        else:
            self._nose = blend(self.PINK, self.FUR_EDGE, 0.28)
            self._nose_hi = blend(self.PINK, self.WHITE, 0.68)
            self._nose_dark = _no_black_key(blend(self._nose, self.INK, 0.45))
        self._mouth_in = _no_black_key(blend(self.PINK, self.INK, 0.62))
        self._tongue = blend(self.PINK, self.WHITE, 0.14)
        self._lip_line = (
            _no_black_key(blend(self.FUR_LIGHT, self.WHITE, 0.18)) if dark_fur
            else _no_black_key(blend(self.INK, self.FUR_EDGE, 0.40))
        )
        self._fur_line = (
            _no_black_key(blend(self.FUR_LIGHT, self.WHITE, 0.28)) if dark_fur
            else _no_black_key(blend(self.INK, self.FUR_EDGE, 0.34))
        )
        self._whisker_col = (
            blend(self.WHITE_SHADE, self.FUR_EDGE, 0.48) if very_light_fur
            else self.WHITE
        )
        self._blush = blend(self.PINK, self.WHITE, 0.48)
        self._paw_pad = blend(self.PINK, self.WHITE_SHADE, 0.32)
        self._whisker_pad = blend(self.WHITE, self.WHITE_SHADE, 0.42)
        self._white_mid = blend(self.WHITE, self.WHITE_SHADE, 0.36)
        self._white_rim = blend(self.WHITE_SHADE, self._coat, 0.10 if dark_fur else 0.08)
        self._eye_rim = _no_black_key(blend(self.INK, self.FUR, 0.12))
        # Luminous chartreuse-gold gaze for default komur skin; preserve exact skin eye colors for all other skins!
        if self.GOLD.lower() == "#f8cd35" and self.GOLD_DARK.lower() == "#c98720":
            self._iris_main = "#e6e145"
            self._iris_dark = "#a7ad24"
            self._iris_light = blend(self.GOLD_LIGHT, "#f8f694", 0.65)
        else:
            self._iris_main = self.GOLD
            self._iris_dark = self.GOLD_DARK
            self._iris_light = self.GOLD_LIGHT
        self._iris_limbal = _no_black_key(blend(self._iris_dark, self.INK, 0.40))
        self._iris_glow = blend(self._iris_main, self._iris_light, 0.64)
        self._pupil_col = _no_black_key(self.INK)

    # -- coordinate helpers -------------------------------------------------
    def _xy(self, x, y):
        if self._growth_scale != 1.0:
            x = 130.0 + (x - 130.0) * self._growth_scale
            y = self.GROUND - (self.GROUND - y) * self._growth_scale
        x = x + self.dx
        if self.flip:
            x = 260 - x
        return (self.left + x * self.scale, self.top + (y + self.dy) * self.scale)

    def _coords(self, values):
        output = []
        for x, y in zip(values[0::2], values[1::2]):
            output.extend(self._xy(x, y))
        return output

    def _flat(self, pts):
        output = []
        for x, y in pts:
            output.extend(self._xy(x, y))
        return output

    def _w(self, width):
        return max(1.0, width * self.scale)

    def _oval(self, x1, y1, x2, y2, fill, outline="", width=1, **kw):
        a, b = self._xy(x1, y1)
        c, d = self._xy(x2, y2)
        if a > c:
            a, c = c, a
        self.item_count += 1
        return self.canvas.create_oval(
            a, b, c, d, fill=fill, outline=outline,
            width=self._w(width), tags=self.TAG, **kw,
        )

    def _ellipse(self, center, rx, ry, fill, outline="", width=1):
        cx, cy = center
        return self._oval(cx - rx, cy - ry, cx + rx, cy + ry, fill, outline, width)

    def _poly(self, points, fill, outline="", width=1, smooth=False, **kw):
        if points and isinstance(points[0], tuple):
            coords = self._flat(points)
        else:
            coords = self._coords(points)
        self.item_count += 1
        return self.canvas.create_polygon(
            *coords, fill=fill, outline=outline, width=self._w(width),
            smooth=smooth, joinstyle="round", tags=self.TAG, **kw,
        )

    def _line(self, points, color, width=1, smooth=True):
        if points and isinstance(points[0], tuple):
            coords = self._flat(points)
        else:
            coords = self._coords(points)
        self.item_count += 1
        return self.canvas.create_line(
            *coords, fill=color, width=self._w(width), smooth=smooth,
            capstyle="round", joinstyle="round", tags=self.TAG,
        )

    def _text(self, x, y, string, **kwargs):
        a, b = self._xy(x, y)
        self.item_count += 1
        return self.canvas.create_text((a, b), text=string, tags=self.TAG, **kwargs)

    @staticmethod
    def _scaled(pts, cx, cy, s, dx=0.0, dy=0.0):
        return [(cx + (x - cx) * s + dx, cy + (y - cy) * s + dy) for x, y in pts]

    @staticmethod
    def _tapered_outline(pts, widths, round_start=False):
        """Polygon outline for a centerline with per-point widths and rounded tip."""
        n = len(pts)
        left, right = [], []
        for i, (x, y) in enumerate(pts):
            if i == 0:
                dx, dy = pts[1][0] - x, pts[1][1] - y
            elif i == n - 1:
                dx, dy = x - pts[i - 1][0], y - pts[i - 1][1]
            else:
                dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length, dx / length
            hw = widths[i] / 2
            left.append((x + nx * hw, y + ny * hw))
            right.append((x - nx * hw, y - ny * hw))
        ex, ey = pts[-1]
        dx, dy = ex - pts[-2][0], ey - pts[-2][1]
        length = math.hypot(dx, dy) or 1.0
        tip = (ex + dx / length * widths[-1] * 0.52, ey + dy / length * widths[-1] * 0.52)
        if round_start:
            sx, sy = pts[0]
            sdx, sdy = pts[1][0] - sx, pts[1][1] - sy
            slen = math.hypot(sdx, sdy) or 1.0
            cap = (sx - sdx / slen * widths[0] * 0.42, sy - sdy / slen * widths[0] * 0.42)
            return [cap] + left + [tip] + right[::-1]
        return left + [tip] + right[::-1]

    @staticmethod
    def _split_chain(pts, widths, u_start):
        """Return the distal sub-chain from normalized arc position ``u_start``..1.0."""
        n = len(pts)
        if n < 2:
            return pts, widths
        seg_lens = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                    for i in range(n - 1)]
        total = sum(seg_lens)
        if total <= 1e-6:
            return pts[-2:], widths[-2:]
        target = max(0.0, min(0.95, u_start)) * total
        acc = 0.0
        for i, sl in enumerate(seg_lens):
            if acc + sl >= target or i == n - 2:
                f = (target - acc) / sl if sl > 1e-6 else 0.0
                f = max(0.0, min(1.0, f))
                cx = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f
                cy = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
                cw = widths[i] + (widths[i + 1] - widths[i]) * f
                out_pts = [(cx, cy)] + list(pts[i + 1:])
                out_w = [cw] + list(widths[i + 1:])
                if len(out_pts) < 2:
                    out_pts = [pts[-2], pts[-1]]
                    out_w = [widths[-2], widths[-1]]
                return out_pts, out_w
            acc += sl
        return pts[-2:], widths[-2:]

    def _tapered(self, pts, widths, fill, outline="", width=1.1, round_start=False):
        return self._poly(
            self._tapered_outline(pts, widths, round_start=round_start),
            fill, outline, width, smooth=True,
        )

    # -- fur primitives -----------------------------------------------------
    def _fur_mass(self, pts, cx, cy, inner=0.88, lift=3.2, highlight=None, outline_w=0.65):
        """Plush velvety feline coat volume with silky organic shading & zero harsh outlines."""
        self._poly(pts, self._coat_shadow, self._outline, outline_w, smooth=True)
        # Main plush velvety coat shifted gently toward overhead light (leaving cozy belly shadow)
        self._poly(self._scaled(pts, cx, cy, 0.96, 0.0, -1.2), self._coat, "", 1, smooth=True)
        # Ultra-soft upper-form velvety volume glow
        self._poly(
            self._scaled(pts, cx, cy, inner * 0.78, 0.0, -lift * 0.85),
            self._fur_mid, "", 1, smooth=True,
        )
        if highlight and len(highlight) >= 2 and self.scale >= 0.60:
            # Whisper-subtle velvet fur sheen along back/shoulder contour (never a bright stripe)
            n = len(highlight)
            w_soft = [2.2 + 2.2 * math.sin(math.pi * (i + 0.5) / n) for i in range(n)]
            self._tapered(highlight, w_soft, self._fur_mid, "", 1, round_start=True)

    def _bib(self, pts, tufts=4):
        """Fluffy, soft-edged snow-white tuxedo chest ruff with feathered fur locks."""
        if not pts or len(pts) < 4:
            self._poly(pts, self.WHITE, "", 1, smooth=True)
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max(8.0, max_x - min_x)
        h = max(8.0, max_y - min_y)
        # Soft shaded outer fur fluff underneath snow-white chest ruff
        self._poly(self._scaled(pts, cx, cy, 1.05, 0.0, 0.8), self._white_mid, "", 1, smooth=True)
        self._poly(pts, self.WHITE, "", 1, smooth=True)
        # Soft feathery fur-tuft locks along the lower chest ruff edge (fluffy, NOT stiff oval!)
        n_tufts = max(3, int(tufts))
        for i in range(n_tufts):
            u = (i + 0.5) / n_tufts
            dist_mid = abs(u - 0.5) * 2.0
            tx = min_x + w * (0.14 + 0.72 * u)
            ty = max_y - h * (0.04 + 0.18 * (dist_mid ** 1.3))
            tlen = 5.5 + 3.6 * (1.0 - dist_mid * 0.75)
            tw = 3.8 + 1.4 * (1.0 - dist_mid)
            self._poly(
                [(tx - tw, ty - 3.2), (tx, ty + tlen), (tx + tw, ty - 3.2)],
                self.WHITE, "", 1, smooth=True,
            )
        if self.scale >= 0.60 and h > 24.0:
            # Soft delicate fur texture wisps inside the fluffy chest ruff
            mid_y = min_y + h * 0.42
            self._line(
                [(cx - w * 0.24, mid_y - 2.0), (cx - w * 0.08, mid_y + 4.5)],
                self.WHITE_SHADE, 0.9,
            )
            self._line(
                [(cx + w * 0.24, mid_y - 2.0), (cx + w * 0.08, mid_y + 4.5)],
                self.WHITE_SHADE, 0.9,
            )

    def _tail(self, pts, widths, outline_w=0.65, puffed=False, use_springs=None):
        """Thick, plush, fluffy tapered tail with soft rounded tip & subtle velvet sheen."""
        if use_springs is None:
            use_springs = getattr(self, "_frame_use_springs", getattr(self, "use_procedural_springs", True))
        spring = getattr(self, "tail_spring", None)
        spring_pts = None
        if use_springs and spring is not None:
            spring_pts = getattr(spring, "points", None)
            if spring_pts is None and getattr(spring, "_initialized", False):
                spring_pts = getattr(spring, "joints", None)
        if use_springs and spring_pts is not None and len(spring_pts) >= 2 and len(pts) >= 2:
            root_x, root_y = pts[0]
            sp0_x, sp0_y = spring_pts[0]
            blended = [(root_x, root_y)]
            last_sp = len(spring_pts) - 1
            for idx in range(1, len(pts)):
                px, py = pts[idx]
                sp_x, sp_y = spring_pts[min(idx, last_sp)]
                dx = sp_x - sp0_x
                dy = sp_y - sp0_y
                if self.flip:
                    dx = -dx
                w_sp = 0.14 + 0.20 * (idx / max(1, len(pts) - 1))
                blended.append((
                    max(4.0, min(256.0, px * (1.0 - w_sp) + (root_x + dx) * w_sp)),
                    max(4.0, min(276.0, py * (1.0 - w_sp) + (root_y + dy) * w_sp)),
                ))
            pts = blended
        # Ensure real Kömür's lush plush tail fullness (generous rounded fluffy tip)
        plush_w = [max(7.2, w * (1.16 if not puffed else 1.05)) for w in widths]
        self._tapered(pts, plush_w, self._coat_shadow, self._outline, outline_w, round_start=True)
        inner_w = [w * 0.84 for w in plush_w]
        self._tapered([(x, y - 0.8) for x, y in pts], inner_w, self._coat, "", 1, round_start=True)
        if len(pts) >= 3 and self.scale >= 0.55:
            hi_w = [max(1.5, w * 0.28) for w in plush_w[:-1]]
            sheen_pts = [
                (x, y - max(1.0, plush_w[min(i, len(plush_w) - 1)] * 0.18))
                for i, (x, y) in enumerate(pts[:-1])
            ]
            self._tapered(sheen_pts, hi_w, self._fur_mid, "", 1, round_start=True)

    def _sock(self, x, y, rx=11.0, ry=6.0, toes=True, lift=0.0, show_beans=False, forward=1.0, angle=0.0):
        """Dainty plush snow-white feline paw with soft domed toes, flat sole & optional wrist tilt."""
        cy = y - lift
        d = 1.0 if forward >= 0 else -1.0
        paw_local = [
            (-d * rx * 0.88, ry * 0.62),
            (-d * rx * 0.80, -ry * 0.58),
            (-d * rx * 0.10, -ry * 0.98),
            (d * rx * 0.68, -ry * 0.72),
            (d * rx * 1.02, ry * 0.14),
            (d * rx * 0.86, ry * 0.88),
            (d * rx * 0.15, ry * 0.96),
            (-d * rx * 0.64, ry * 0.92),
        ]
        if angle:
            rad = math.radians(angle)
            ca, sa = math.cos(rad), math.sin(rad)
            paw_pts = [(x + px * ca - py * sa, cy + px * sa + py * ca) for px, py in paw_local]
        else:
            paw_pts = [(x + px, cy + py) for px, py in paw_local]

        sole_pts = [(px, py + 0.8) for px, py in paw_pts]
        self._poly(sole_pts, self._white_mid, "", 1, smooth=True)
        self._poly(paw_pts, self.WHITE, self._white_rim, 0.55, smooth=True)

        if show_beans and self.scale >= 0.55:
            self._oval(
                x - rx * 0.26, cy - ry * 0.04,
                x + rx * 0.26, cy + ry * 0.48,
                self._paw_pad, "", 1,
            )
            for bx, by in ((-rx * 0.36, -ry * 0.30), (0.0, -ry * 0.46), (rx * 0.36, -ry * 0.30)):
                br = max(1.3, rx * 0.13)
                self._oval(
                    x + bx - br, cy + by - br * 0.82,
                    x + bx + br, cy + by + br * 0.82,
                    self._paw_pad, "", 1,
                )
        elif toes and self.scale >= 0.55:
            for off in (0.04, 0.44):
                tx = x + d * rx * off
                self._line(
                    [(tx - d * 0.3, cy - ry * 0.08), (tx + d * 0.5, cy + ry * 0.78)],
                    self.WHITE_SHADE, 0.95,
                )

    def _curved_limb(self, pts, widths, *, sock=True, sock_start=0.78, far=False,
                     toes=True, show_beans=False, paw_rx=None, paw_ry=None,
                     forward=1.0, paw_offset=(0.0, 1.5), show_rim=False):
        """Plush, full-volume feline limb merging seamlessly into body with dainty white toe tips."""
        base_col = self._far_fur if far else self._coat_shadow
        # Zero outline seam where limb meets body for velvety continuous fur!
        self._tapered(pts, widths, base_col, "", 1, round_start=True)
        if not far:
            inner_w = [w * 0.91 for w in widths]
            inner_pts = [(x + forward * 0.4, y - 0.4) for x, y in pts]
            self._tapered(inner_pts, inner_w, self._coat, "", 1, round_start=True)
            if self.scale >= 0.60 and len(pts) >= 3:
                sheen_pts = [(x + forward * (w * 0.12), y - 0.3) for (x, y), w in zip(pts[:-1], widths[:-1])]
                sheen_w = [max(1.2, w * 0.20) for w in widths[:-1]]
                self._tapered(sheen_pts, sheen_w, self._fur_mid, "", 1, round_start=True)
        if sock:
            s_pts, s_w = self._split_chain(pts, widths, sock_start)
            self._tapered(
                s_pts, [w * 1.02 for w in s_w],
                self._white_mid if far else self.WHITE, "", 1, round_start=True,
            )
            if not far:
                self._tapered(s_pts, [w * 0.92 for w in s_w], self.WHITE, "", 1, round_start=True)
        ex, ey = pts[-1]
        end_w = widths[-1]
        rx = paw_rx if paw_rx is not None else max(9.5, end_w * 0.78 + 2.0)
        ry = paw_ry if paw_ry is not None else max(5.6, end_w * 0.44 + 1.4)
        self._sock(
            ex + paw_offset[0] * forward, ey + paw_offset[1],
            rx, ry, toes=toes and not far, show_beans=show_beans, forward=forward,
        )

    def _leg(self, x_top, y_top, x_bot, y_bot, width=18, sock=True, toes=True,
             far=False, show_beans=False, bend=0.0, forward=1.0):
        """Plush curved feline leg."""
        dx = x_bot - x_top
        dy = y_bot - y_top
        curve = bend if bend != 0.0 else (-2.6 * forward)
        p0 = (x_top, y_top)
        p1 = (x_top + dx * 0.34 + curve * 0.85, y_top + dy * 0.34)
        p2 = (x_top + dx * 0.72 + curve * 0.32, y_top + dy * 0.72)
        p3 = (x_bot, y_bot)
        w0 = width * 1.18
        w1 = width * 0.92
        w2 = width * 0.74
        w3 = width * 0.62
        self._curved_limb(
            [p0, p1, p2, p3], [w0, w1, w2, w3],
            sock=sock, sock_start=0.78, far=far, toes=toes,
            show_beans=show_beans, forward=forward,
        )

    # -- head ---------------------------------------------------------------
    def _head_ears(self, shape, t, ears, twitch, profile=0.0):
        """Plush pointed feline ears with velvety dark interior & wispy silver-white inner ear hairs."""
        music_active = getattr(self, "_reaction", "none") == "music"
        p = max(0.0, min(1.0, float(profile)))
        # Draw far ear first when in 3/4 profile (s=+1 is far/front-side, s=-1 is near/back-side)
        order = (1, -1) if p > 0.05 else (-1, 1)
        for s in order:
            tw = 0.0
            if twitch:
                period = 6.8 if s < 0 else 8.7
                phase = (t + (0.0 if s < 0 else 2.3)) % period
                if phase < 0.28:
                    tw = math.sin(phase / 0.28 * math.pi * 2) * 3.2
            if music_active:
                beat = math.sin(t * 4.4 + (0.0 if s < 0 else 0.7))
                tw += beat * 2.2

            if ears == "flat":
                tip = (s * 58, -20)
                outer = (s * 40, -5)
            elif ears == "back":
                tip = (s * 52 + tw, -44)
                outer = (s * 40, -8)
            elif ears == "droop":
                tip = (s * 46 + tw, -49)
                outer = (s * 39, -8)
            elif ears == "relaxed":
                tip = (s * 42 + tw * s, -59)
                outer = (s * 40, -10)
            elif ears == "forward":
                tip = (s * 34 + tw * s, -66)
                outer = (s * 39, -11)
            else:
                # Real Kömür: adorable pointed plush ears angled gracefully outward (broader base, natural height)
                tip = (s * 41 + tw * s, -64)
                outer = (s * 40, -10)

            if self._ear_override is not None:
                angle_attr = "left_angle" if s < 0 else "right_angle"
                angle_val = getattr(self._ear_override, angle_attr, None)
                if angle_val is not None:
                    tip = (tip[0] + float(angle_val) * 0.36, tip[1] + abs(float(angle_val)) * 0.18)
                else:
                    ear_tw = float(getattr(self._ear_override, "twitch_left" if s < 0 else "twitch_right", 0.0) or 0.0)
                    layback = float(getattr(self._ear_override, "layback", 0.0) or 0.0)
                    tip = (
                        tip[0] + s * ear_tw * 0.55 + s * layback * 5.5,
                        tip[1] + layback * 7.5,
                    )

            inner_base = (s * 12.0, -30)
            far_ear = p > 0.15 and s > 0
            if p > 0.0:
                if s > 0:
                    # Far ear (front-top of 3/4 skull, tucked behind crown in depth)
                    inner_base = (inner_base[0] - p * 4.0, inner_base[1] + p * 1.5)
                    outer = (outer[0] - p * 14.0, outer[1] - p * 3.0)
                    tip = (tip[0] - p * 18.0, tip[1] + p * 6.5)
                else:
                    # Near ear (closer to viewer on left-top of skull)
                    inner_base = (inner_base[0] + p * 4.5, inner_base[1] + p * 1.0)
                    outer = (outer[0] + p * 6.5, outer[1] + p * 2.0)
                    tip = (tip[0] + p * 8.0, tip[1] + p * 3.0)

            inner_mid = (
                inner_base[0] + (tip[0] - inner_base[0]) * 0.50 - s * 1.0,
                inner_base[1] + (tip[1] - inner_base[1]) * 0.50,
            )
            tip_a = (tip[0] - s * 2.2, tip[1] + 2.4)
            tip_b = (tip[0] + s * 2.0, tip[1] + 3.6)
            outer_upper = ((tip[0] + outer[0]) * 0.5 + s * 4.2, (tip[1] + outer[1]) * 0.5 - 1.6)
            tragus_in = (outer[0] - s * 2.0, outer[1] - 5.2)
            tragus_out = (outer[0] + s * 1.0, outer[1] - 2.8)
            ear_poly = [inner_base, inner_mid, tip_a, tip, tip_b, outer_upper, tragus_in, tragus_out, outer]
            ear_col = self._far_fur if far_ear else self._coat_shadow
            self._poly(shape(ear_poly), ear_col, self._outline, 0.65, smooth=True)
            if not far_ear:
                self._poly(
                    shape(self._scaled(ear_poly, (inner_base[0] + outer[0]) * 0.5, (tip[1] + outer[1]) * 0.5, 0.91)),
                    self._coat, "", 1, smooth=True,
                )

            # Deep velvety inner ear cavity + delicate feathery silver-gray tuft ONLY at lower-inner opening!
            gx = inner_base[0] * 0.36 + tip[0] * 0.32 + outer[0] * 0.32
            gy = inner_base[1] * 0.36 + tip[1] * 0.32 + outer[1] * 0.32
            concha = [
                (gx + (px - gx) * 0.64, gy + (py - gy) * 0.64 + 1.0)
                for px, py in (inner_base, tip, outer)
            ]
            self._poly(shape(concha), self._ear_depth, "", 1, smooth=True)
            inner_soft = [
                (gx + (px - gx) * 0.42 + s * 0.5, gy + (py - gy) * 0.42 + 2.2)
                for px, py in (inner_base, tip, outer)
            ]
            self._poly(shape(inner_soft), self._ear_inner, "", 1, smooth=True)

            # Delicate feathery silver-white inner ear tufts nestled along lower-inner edge (NO zebra bars!)
            if self.scale >= 0.45 and not far_ear:
                tuft_col = self._ear_tuft
                for frac, span, lift_y in ((0.14, 0.34, -1.5), (0.25, 0.42, -2.5), (0.36, 0.32, -3.2)):
                    b_x = inner_base[0] + (tip[0] - inner_base[0]) * frac + s * 1.4
                    b_y = inner_base[1] + (tip[1] - inner_base[1]) * frac + 2.2
                    t_x = b_x + (outer[0] - inner_base[0]) * span
                    t_y = b_y + (outer[1] - inner_base[1]) * (span * 0.35) + lift_y
                    m_x = (b_x + t_x) * 0.5
                    m_y = (b_y + t_y) * 0.5 - 1.2
                    self._line(shape([(b_x, b_y), (m_x, m_y), (t_x, t_y)]), tuft_col, 0.72)

    def _head_eyes(self, shape, tf, eyes, pupil, gaze, lid, profile=0.0):
        """Big, round, soulful luminous chartreuse-gold eyes with twin catchlight sparkles."""
        p_norm = max(0.0, min(1.0, pupil))
        lid = max(0.0, min(1.0, float(lid)))
        p = max(0.0, min(1.0, float(profile)))

        for s in (-1, 1):
            if p <= 0.01:
                ex, ey = s * 17.4, -3.5
                rx, ry = 12.6, 11.4
                far_eye = False
            else:
                if s < 0:
                    # Near eye (big, round, luminous gaze)
                    ex = -17.0 + p * 19.8
                    ey = -3.5 + p * 0.5
                    rx, ry = 12.2, 11.0
                    far_eye = False
                else:
                    # Far eye (gently foreshortened near the front contour of the 3/4 cheek)
                    ex = 17.0 + p * 10.6
                    ey = -3.5 + p * 0.3
                    rx = 12.2 * (1.0 - p * 0.24)
                    ry = 11.0 * (1.0 - p * 0.06)
                    far_eye = True

            # Big, soulful, gently round feline eye (matches real Kömür's huge round yellow-green eyes!)
            eye_pts = [
                (ex - s * rx * 0.96, ey + ry * 0.16),
                (ex - s * rx * 0.66, ey - ry * 0.72),
                (ex + s * rx * 0.06, ey - ry * 0.98),
                (ex + s * rx * 0.74, ey - ry * 0.72),
                (ex + s * rx * 0.98, ey - ry * 0.08),
                (ex + s * rx * 0.76, ey + ry * 0.68),
                (ex + s * rx * 0.04, ey + ry * 0.96),
                (ex - s * rx * 0.66, ey + ry * 0.74),
            ]

            if eyes == "closed" or lid >= 0.94:
                self._line(
                    shape([
                        (ex - s * rx * 0.85, ey + 1.8),
                        (ex, ey + 4.4),
                        (ex + s * rx * 0.85, ey + 0.6),
                    ]),
                    self._fur_line, 1.75,
                )
                continue
            if eyes == "happy":
                # Sweet blissful curved happy cat-kiss eyes
                self._line(
                    shape([
                        (ex - s * rx * 0.82, ey + 2.4),
                        (ex, ey - 2.4),
                        (ex + s * rx * 0.82, ey + 1.6),
                    ]),
                    self._fur_line, 1.85,
                )
                continue
            if eyes == "squeezed":
                self._line(
                    shape([
                        (ex - s * rx * 0.82, ey + 1.8),
                        (ex, ey - 1.8),
                        (ex + s * rx * 0.82, ey + 1.4),
                    ]),
                    self._fur_line, 1.85,
                )
                if self.scale >= 0.60:
                    self._line(
                        shape([
                            (ex - s * rx * 0.56, ey + 5.0),
                            (ex, ey + 3.0),
                            (ex + s * rx * 0.56, ey + 4.8),
                        ]),
                        self._fur_line, 0.85,
                    )
                continue

            # 1. Soft velvety dark lash socket rim
            self._poly(shape(self._scaled(eye_pts, ex, ey, 1.12)), self._eye_rim, "", 1, smooth=True)
            # 2. Delicate dark olive-gold limbal ring
            self._poly(shape(eye_pts), self._iris_limbal, "", 1, smooth=True)
            # 3. Outer olive-chartreuse iris -> wide luminous yellow-green iris
            self._poly(shape(self._scaled(eye_pts, ex, ey, 0.94, 0, 0.2)), self._iris_dark, "", 1, smooth=True)
            self._poly(shape(self._scaled(eye_pts, ex, ey, 0.84, 0, 0.5)), self._iris_main, "", 1, smooth=True)
            # 4. Radiant warm yellow-green inner glow crescent (glassy sunlit real-cat eye depth!)
            if self.scale >= 0.45:
                gx_off = max(-2.2, min(2.2, gaze[0] * 0.22))
                crescent = [
                    (ex - rx * 0.64 + gx_off, ey + ry * 0.14),
                    (ex - rx * 0.28 + gx_off, ey + ry * 0.68),
                    (ex + rx * 0.30 + gx_off, ey + ry * 0.68),
                    (ex + rx * 0.64 + gx_off, ey + ry * 0.14),
                    (ex + rx * 0.28 + gx_off, ey + ry * 0.38),
                    (ex - rx * 0.28 + gx_off, ey + ry * 0.38),
                ]
                self._poly(shape(crescent), self._iris_glow, "", 1, smooth=True)

            # 5. Large, sweet, glossy dark oval-round pupil (adorable like real Kömür's photo!)
            gx_c = max(-3.0, min(3.0, gaze[0] * 0.48)) * (0.72 if far_eye else 1.0)
            gy_c = max(-2.0, min(2.0, gaze[1] * 0.46))
            px, py = ex + gx_c, ey + gy_c
            ph = ry * 0.74
            if p_norm <= 0.18:
                # Sharp narrow vertical slit ONLY when hissing / bright glare
                pw = (1.6 + 1.4 * (p_norm / 0.18)) * (0.82 if far_eye else 1.0)
                slit = [
                    (px, py - ph),
                    (px + pw * 0.88, py - ph * 0.42),
                    (px + pw, py),
                    (px + pw * 0.88, py + ph * 0.42),
                    (px, py + ph),
                    (px - pw * 0.88, py + ph * 0.42),
                    (px - pw, py),
                    (px - pw * 0.88, py - ph * 0.42),
                ]
                self._poly(shape(slit), self._pupil_col, "", 1, smooth=True)
            else:
                # Wide adorable rounded-oval pupil -> big boba-round orb when excited/dark
                u_d = (p_norm - 0.18) / 0.82
                pw = (3.8 + 3.4 * u_d) * (0.80 if far_eye else 1.0)
                ph_eff = min(ry * 0.80, ph + 0.6 * u_d)
                self._oval(*tf(px - pw, py - ph_eff), *tf(px + pw, py + ph_eff), self._pupil_col)

            # 6. Crisp twin bright white sparkle catchlights!
            cl_x = px - pw * 0.44 - 1.1
            cl_y = py - ph * 0.48
            r_big = 2.05 if not far_eye else 1.75
            self._oval(*tf(cl_x - r_big, cl_y - r_big), *tf(cl_x + r_big, cl_y + r_big), self.WHITE)
            if self.scale >= 0.50:
                cl2_x = px + pw * 0.34 + 0.9
                cl2_y = py + ph * 0.30
                r_sm = 1.05 if not far_eye else 0.9
                self._oval(*tf(cl2_x - r_sm, cl2_y - r_sm), *tf(cl2_x + r_sm, cl2_y + r_sm), self.WHITE)

            # 7. Soft upper lash rim
            self._line(
                shape([
                    (ex - s * rx * 0.94, ey + ry * 0.14),
                    (ex - s * rx * 0.56, ey - ry * 0.78),
                    (ex + s * rx * 0.16, ey - ry * 0.98),
                    (ex + s * rx * 0.96, ey - ry * 0.12),
                ]),
                self._eye_rim, 1.5,
            )

            # 8. Smooth drooping / slow-blinking upper eyelid
            if lid > 0.02:
                top = ey - ry - 1.5
                cover = top + (ry * 2.0 + 1.0) * lid
                self._poly(
                    shape([
                        (ex - rx - 2.5, top),
                        (ex + rx + 2.5, top),
                        (ex + rx + 2.5, cover - 2.2),
                        (ex, cover + 0.6),
                        (ex - rx - 2.5, cover - 2.0),
                    ]),
                    self._coat, "", 1, smooth=True,
                )
                self._line(
                    shape([
                        (ex - s * rx * 0.92, cover - 1.4),
                        (ex, cover + 0.8),
                        (ex + s * rx * 0.92, cover - 1.8),
                    ]),
                    self._eye_rim, 1.25,
                )

    def _head_muzzle_mouth(self, shape, tf, mouth, open_amount, tongue_out, chomp, blush, whiskers, profile=0.0):
        """Plush ALL-COAT face (NO white muzzle patch!), cute matte velvet nose, long white whiskers & brow hairs."""
        p = max(0.0, min(1.0, float(profile)))
        mx = p * 16.5  # nose/muzzle center shifts forward (+x) in 3/4 profile

        # Subtle plush velvety cheek/muzzle pads (coat-colored — matches real Kömür's all-black face!)
        if self.scale >= 0.50:
            for s in (-1, 1):
                sx = 1.0 if p <= 0.01 else (0.72 if s > 0 else 1.05)
                pad = [
                    (mx + s * 1.4 * sx, 14.5),
                    (mx + s * 9.5 * sx, 14.0),
                    (mx + s * 13.8 * sx, 19.8),
                    (mx + s * 7.8 * sx, 24.4),
                    (mx + s * 1.2 * sx, 20.8),
                ]
                self._poly(shape(pad), self._muzzle_puff, "", 1, smooth=True)

        # Cute tiny matte charcoal-black velvet nose triangle (real Kömür!)
        nw = 4.2 * (1.0 - p * 0.14)
        nose = [
            (mx - nw, 10.6), (mx, 9.8), (mx + nw, 10.6),
            (mx + nw * 0.72, 13.4), (mx, 15.6), (mx - nw * 0.72, 13.4),
        ]
        self._poly(shape(nose), self._nose, self._nose_dark, 0.55, smooth=True)
        if self.scale >= 0.50:
            self._oval(*tf(mx - nw * 0.45, 10.4), *tf(mx + nw * 0.30, 11.9), self._nose_hi)

        # Delicate philtrum & realistic mouth expressions
        if mouth == "yawn":
            opening = max(2.0, open_amount * 0.92)
            mw = (7.4 + opening * 0.14) * (1.0 - p * 0.15)
            self._poly(
                shape([
                    (mx - mw, 16.5), (mx + mw, 16.5),
                    (mx + mw * 1.08, 19.5 + opening * 0.55),
                    (mx, 20.5 + opening),
                    (mx - mw * 1.08, 19.5 + opening * 0.55),
                ]),
                self._mouth_in, self._nose_dark, 0.65, smooth=True,
            )
            # Cute tiny white upper fangs visible during wide yawn
            if opening > 6.5 and self.scale >= 0.50:
                self._poly(shape([(mx - mw * 0.62, 16.8), (mx - mw * 0.34, 16.8), (mx - mw * 0.48, 20.6)]), self.WHITE, "", 1)
                self._poly(shape([(mx + mw * 0.34, 16.8), (mx + mw * 0.62, 16.8), (mx + mw * 0.48, 20.6)]), self.WHITE, "", 1)
            # Curled soft pink tongue inside the yawn
            tx_r = mw * 0.58
            self._poly(
                shape([
                    (mx - tx_r, 19.5 + opening * 0.52),
                    (mx, 18.2 + opening * 0.38),
                    (mx + tx_r, 19.5 + opening * 0.52),
                    (mx + tx_r * 0.85, 20.8 + opening * 0.92),
                    (mx, 21.8 + opening * 1.02),
                    (mx - tx_r * 0.85, 20.8 + opening * 0.92),
                ]),
                self._tongue, "", 1, smooth=True,
            )
        elif mouth == "hiss":
            mw = 9.0 * (1.0 - p * 0.15)
            self._poly(
                shape([(mx - mw, 16.2), (mx + mw, 16.2), (mx + mw * 1.08, 24.5), (mx, 29.8), (mx - mw * 1.08, 24.5)]),
                self._mouth_in, self._nose_dark, 0.70, smooth=True,
            )
            self._poly(shape([(mx - mw * 0.80, 17.0), (mx - mw * 0.50, 17.0), (mx - mw * 0.65, 22.8)]), self.WHITE, "", 1)
            self._poly(shape([(mx + mw * 0.50, 17.0), (mx + mw * 0.80, 17.0), (mx + mw * 0.65, 22.8)]), self.WHITE, "", 1)
            self._oval(*tf(mx - mw * 0.42, 24.0), *tf(mx + mw * 0.42, 28.4), self._tongue)
        elif mouth == "chirp":
            self._line(shape([(mx, 15.6), (mx, 18.0)]), self._lip_line, 0.95)
            self._oval(*tf(mx - 2.8, 18.0), *tf(mx + 2.8, 23.0), self._mouth_in)
        elif mouth == "sneeze":
            self._line(shape([(mx, 15.6), (mx, 17.6)]), self._lip_line, 0.95)
            self._oval(*tf(mx - 4.6, 17.6), *tf(mx + 4.6, 25.4), self._mouth_in)
        elif mouth == "groom":
            self._line(shape([(mx, 15.6), (mx, 19.2)]), self._lip_line, 0.95)
            ext = 0.45 + 0.55 * max(0.0, min(1.0, tongue_out if tongue_out > 0 else 0.75))
            self._poly(
                shape([
                    (mx + 1.0, 19.2),
                    (mx + 12.5 * ext, 21.8 + ext * 1.8),
                    (mx + 7.2 * ext, 29.8 + ext * 3.0),
                    (mx + 0.4, 24.0),
                ]),
                self._tongue, "", 1, smooth=True,
            )
        elif mouth == "lap":
            self._line(shape([(mx, 15.6), (mx, 19.0)]), self._lip_line, 0.95)
            self._oval(*tf(mx - 4.0, 18.6), *tf(mx + 4.0, 23.2), self._mouth_in)
            ext = max(0.0, min(1.0, tongue_out))
            if ext > 0.08:
                ty = 22.4 + ext * 14.2
                self._poly(
                    shape([
                        (mx - 3.2, 20.4), (mx + 3.2, 20.4),
                        (mx + 4.2, 23.0 + ext * 8.2), (mx, ty), (mx - 4.2, 23.0 + ext * 8.2),
                    ]),
                    self._tongue, "", 1, smooth=True,
                )
        elif mouth == "munch":
            ch = max(0.0, min(1.0, chomp))
            self._line(shape([(mx, 15.6), (mx, 19.0)]), self._lip_line, 0.95)
            if ch > 0.25:
                oh = 1.8 + ch * 4.4
                self._oval(*tf(mx - 3.8, 19.0), *tf(mx + 3.8, 19.0 + oh), self._mouth_in)
                self._oval(*tf(mx - 2.3, 19.0 + oh * 0.45), *tf(mx + 2.3, 19.0 + oh), self._tongue)
            self._line(shape([(mx, 19.0), (mx - 4.2, 22.2 - ch * 1.0), (mx - 8.2, 20.2)]), self._lip_line, 0.95)
            self._line(shape([(mx, 19.0), (mx + 4.2, 22.2 - ch * 1.0), (mx + 8.2, 20.2)]), self._lip_line, 0.95)
        else:
            # Subtle warm feline upper-lip curve on plush black velvet
            self._line(shape([(mx, 15.6), (mx, 19.0)]), self._lip_line, 0.95)
            self._line(shape([(mx, 19.0), (mx - 4.2, 22.2), (mx - 8.2, 20.4)]), self._lip_line, 0.95)
            self._line(shape([(mx, 19.0), (mx + 4.2 * (1.0 - p * 0.2), 22.2), (mx + 8.0 * (1.0 - p * 0.25), 20.4)]), self._lip_line, 0.95)

        if whiskers:
            # Iconic sweeping long bright white whiskers & whisper-fine white brow hairs (real Kömür!)
            w_thick = 0.96 if (_IS_MAC and self.scale < 0.75) else 0.82
            w_col = self._whisker_col
            brow_col = blend(w_col, self._coat, 0.24)
            brow_thick = max(0.65, w_thick * 0.74)
            if p <= 0.05:
                for s in (-1, 1):
                    root = (s * 13.5, 17.5)
                    # 4 sweeping long gracefully arching bright-white whiskers per cheek!
                    for (mid_x, mid_y, tip_x, tip_y) in (
                        (35, 14.0, 58, 16.0),
                        (38, 19.5, 62, 26.5),
                        (35, 25.0, 56, 36.5),
                        (29, 29.5, 46, 43.5),
                    ):
                        self._line(shape([root, (s * mid_x, mid_y), (s * tip_x, tip_y)]), w_col, w_thick)
                    # 2 delicate whisper-fine curving white eyebrow hairs above each eye (never colliding with ears!)
                    for (bx, by, cmx, cmy, btx, bty) in (
                        (14.0, -17.5, 17.5, -26.5, 22.0, -33.0),
                        (18.5, -16.8, 24.0, -24.5, 29.5, -29.5),
                    ):
                        self._line(
                            shape([(s * bx, by), (s * cmx, cmy), (s * btx, bty)]),
                            brow_col, brow_thick,
                        )
            else:
                # 3/4 profile whiskers: near-side sweep gracefully back across cheek, far-side fan forward!
                near_root = (mx - 6.5, 17.5)
                for (dx1, dy1, dx2, dy2) in (
                    (-22, -0.5, -46, 4.5),
                    (-25, 4.5, -50, 14.0),
                    (-23, 9.5, -45, 23.5),
                    (-18, 13.5, -34, 31.0),
                ):
                    self._line(
                        shape([near_root, (near_root[0] + dx1, near_root[1] + dy1), (near_root[0] + dx2, near_root[1] + dy2)]),
                        w_col, w_thick,
                    )
                far_root = (mx + 6.5, 17.2)
                for (dx1, dy1, dx2, dy2) in (
                    (16, -2.0, 34, -0.5),
                    (18, 2.5, 36, 8.0),
                    (16, 7.0, 31, 16.5),
                ):
                    self._line(
                        shape([far_root, (far_root[0] + dx1, far_root[1] + dy1), (far_root[0] + dx2, far_root[1] + dy2)]),
                        w_col, w_thick * 0.90,
                    )
                # 2 whisper-fine gently fanned brow hairs arcing above near eye
                near_bx = -17.0 + p * 19.8
                for (ox, oy, tx, ty) in ((-3.5, -15.5, -12.5, -26.5), (1.0, -16.0, -3.5, -29.5)):
                    self._line(
                        shape([(near_bx + ox, oy), (near_bx + (ox + tx) * 0.5, (oy + ty) * 0.5 - 2.2), (near_bx + tx, ty)]),
                        brow_col, brow_thick,
                    )

    def _head(self, cx, cy, t, *, size=0.86, tilt=0.0, eyes="open", pupil=0.3,
              gaze=(0.0, 0.0), lid=0.0, mouth="closed", ears="up", twitch=True,
              whiskers=True, open_amount=12.0, blush=False, tongue_out=0.0, chomp=0.0,
              profile=0.0):
        """Draw adorable plush real-Kömür head centred at (cx, cy).
        ``profile`` (0.0..1.0): 0.0 = front-facing (sit/box), 0.65 = natural 3/4 profile (walk/side)."""
        self._head_logical = (cx, cy)
        size = size * self._growth_head_scale
        p = max(0.0, min(1.0, float(profile)))
        if self._gaze_override is not None:
            gaze = self._gaze_override
        if self._ear_override is not None:
            ov_mode = getattr(self._ear_override, "mode", None)
            if ov_mode and (ears == "up" or ov_mode == "flat"):
                ears = ov_mode
        tilt += self._dance_tilt
        rad = math.radians(tilt)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        def tf(x, y):
            return (cx + (x * cos_a - y * sin_a) * size, cy + (x * sin_a + y * cos_a) * size)

        def shape(pts):
            return [tf(x, y) for x, y in pts]

        # 1. Plush pointed ears behind skull
        self._head_ears(shape, t, ears, twitch, profile=p)

        # 2. Plush round-cheeked velvety feline skull (morphs smoothly into 3/4 profile!)
        if p <= 0.01:
            skull = [
                (0, -35.0),
                (18.5, -33.0),
                (34.5, -20.5),
                (42.0, -1.5),
                (41.5, 13.5),
                (30.5, 27.5),
                (15.5, 35.5),
                (0, 38.0),
                (-15.5, 35.5),
                (-30.5, 27.5),
                (-41.5, 13.5),
                (-42.0, -1.5),
                (-34.5, -20.5),
                (-18.5, -33.0),
            ]
        else:
            # Cute plush 3/4-profile cat head: rounded back-of-head + gentle protruding snout/cheek on +x
            snout = p * 8.5
            back = p * 5.0
            skull = [
                (p * 2.0, -34.5),
                (18.0 + p * 3.5, -31.5),
                (32.5 + p * 4.5, -18.5),
                (38.5 + snout * 0.55, -2.5),
                (40.0 + snout, 11.5),
                (32.5 + snout * 0.85, 25.5),
                (18.0 + snout * 0.55, 34.5),
                (2.0 + p * 4.0, 36.5),
                (-16.0 + back * 0.3, 33.5),
                (-31.5 + back * 0.4, 24.5),
                (-40.5 + back * 0.3, 10.5),
                (-40.5 + back * 0.2, -5.0),
                (-33.5 + back * 0.2, -21.5),
                (-17.5 + p * 1.0, -32.5),
            ]

        # Ultra-plush all-coat velvety head (ZERO white face patch, ZERO harsh gray lines!)
        self._poly(shape(skull), self._coat_shadow, self._outline, 0.7, smooth=True)
        self._poly(shape(self._scaled(skull, p * 3.0, 0, 0.96, 0, -1.0)), self._coat, "", 1, smooth=True)
        self._poly(shape(self._scaled(skull, p * 3.0, -5, 0.78, 0, -3.0)), self._fur_mid, "", 1, smooth=True)

        # 3. Luminous big round chartreuse-gold eyes
        self._head_eyes(shape, tf, eyes, pupil, gaze, lid, profile=p)

        # 4. Plush coat-colored muzzle puffs, cute matte black nose, mouth, sweeping white whiskers & brow hairs
        self._head_muzzle_mouth(
            shape, tf, mouth, open_amount, tongue_out, chomp, blush, whiskers, profile=p,
        )

        # 5. Head-tracking accessories / costumes
        self._accessory(shape, size)

    def _accessory(self, shape, size=1.0):
        """Draw the chosen accessory in head-local coordinates."""
        kind = self.accessory
        if LayeredCostumes.draw(self, kind, shape, size=size, t=self.micro_time):
            return
        if kind == "bow":
            red, dark = self.ACC_RED, self.ACC_RED_DARK
            self._poly(shape([(0, 46), (-19, 38), (-19, 55)]), red, dark, 1, smooth=False)
            self._poly(shape([(0, 46), (19, 38), (19, 55)]), red, dark, 1, smooth=False)
            self._poly(shape([(-5, 41), (5, 41), (5, 52), (-5, 52)]), dark, "", 1, smooth=True)
        elif kind == "scarf":
            red, dark = self.ACC_RED, self.ACC_RED_DARK
            self._poly(
                shape([
                    (-32, 31), (-16, 40), (0, 43), (16, 40), (32, 31), (34, 42),
                    (16, 52), (0, 55), (-16, 52), (-34, 42),
                ]),
                red, dark, 1, smooth=True,
            )
            self._line(shape([(-24, 39), (-20, 48)]), self.WHITE, 1.8)
            self._line(shape([(-7, 44), (-5, 53)]), self.WHITE, 1.8)
            self._line(shape([(9, 44), (7, 53)]), self.WHITE, 1.8)
            self._line(shape([(24, 39), (20, 48)]), self.WHITE, 1.8)
            self._poly(shape([(13, 49), (26, 47), (28, 70), (17, 72)]), red, dark, 1)
        elif kind == "hat":
            self._poly(
                shape([(-14, -38), (-12, -58), (-2, -64), (10, -60), (14, -38)]),
                self.ACC_RED, self.ACC_RED_DARK, 1, smooth=True,
            )
            self._poly(shape([(-13, -43), (13, -43), (14, -38), (-14, -38)]), self.GOLD, "", 1)
            self._ellipse(shape([(0, -37)])[0], 21 * size, 4.8 * size, self.ACC_RED_DARK, self._ink, 1)
        elif kind == "glasses":
            for s in (-1, 1):
                x0, y0 = s * 17.5, -5.0
                self._ellipse(shape([(x0, y0)])[0], 12.2 * size, 10.8 * size, "", self.ACC_METAL, 1.8)
                self._line(shape([(x0 - s * 5.5, y0 - 7), (x0 - s * 10, y0 - 2.5)]), self.WHITE, 1)
            self._line(shape([(-5.5, -6.5), (0, -9.0), (5.5, -6.5)]), self.ACC_METAL, 1.8)
            for s in (-1, 1):
                self._line(shape([(s * 30, -6.5), (s * 41, -10)]), self.ACC_METAL, 1.5)

    # -- awake-state helpers ------------------------------------------------
    def _blink_amount(self, t, offset=0.0, allow_slow=True):
        """Continuous eyelid closure 0..1: smooth natural blinks + affectionate slow 'cat kiss' blink."""
        u = (t + offset) % 5.1
        quick = 0.0
        if u < 0.22:
            quick = math.sin(u / 0.22 * math.pi)
        slow = 0.0
        if allow_slow:
            s_u = (t + offset + 3.1) % 13.7
            if s_u < 0.88:
                # Smooth feline slow-blink ("cat kiss"): gentle lower, soft pause, smooth reopen
                p = s_u / 0.88
                slow = math.sin(p * math.pi) ** 0.72 * 0.96
        return max(quick, slow)

    def _blinking(self, t, offset=0.0):
        return self._blink_amount(t, offset, allow_slow=False) > 0.75

    def _pupil(self, brain, state):
        override = getattr(brain, "pupil_dilation", None)
        if override is not None:
            try:
                return max(0.0, min(1.0, float(override)))
            except (TypeError, ValueError):
                pass
        if state in ("play", "laser_chase"):
            return 1.0
        if state == "hiss":
            return 0.14
        if state in ("jump", "scratch"):
            return 0.56
        base = 0.42 if state == "look" else 0.28
        low = bool(getattr(brain, "low_light", False))
        if not low:
            try:
                low = time.localtime().tm_hour in self.LOW_LIGHT_HOURS
            except (OSError, ValueError, OverflowError):
                low = False
        return max(base, 0.78) if low else base

    # -- poses --------------------------------------------------------------
    def _sit_body(self, lift=0.0, vib_x=0.0, tail_sw=(0.0, 0.0)):
        """Photo-faithful plush sitting Kömür body: cozy silhouette, wide fluffy white bib & thick tail."""
        g = self.GROUND
        sw, sw2 = tail_sw

        # 1. Thick plush fluffy black tail sweeping softly beside the haunch (like real Kömür's photo!)
        self._tail(
            [
                (190, 242), (214, 250), (234, 240),
                (242, 222 + sw * 0.6), (234, 206 + sw2 * 0.7), (222, 198 + sw2 * 0.8),
            ],
            [14.5, 14.0, 12.8, 11.4, 9.8, 8.0],
        )

        # 2. Cozy plush sitting feline body (soft rounded shoulders + plush haunch)
        body = [
            (96 + vib_x, 126 - lift),
            (144 + vib_x, 126 - lift),
            (168 + vib_x, 146 - lift * 0.6),
            (192 + vib_x * 0.6, 172),
            (208 + vib_x * 0.4, 204),
            (208, 236),
            (194, g - 1),
            (146, g),
            (96, g - 2),
            (78, 238),
            (74 + vib_x * 0.6, 198),
            (82 + vib_x, 154 - lift * 0.5),
        ]
        self._fur_mass(
            body, 140 + vib_x * 0.4, 198, inner=0.86, lift=3.0,
            highlight=[
                (148 + vib_x * 0.6, 154 - lift * 0.4),
                (180 + vib_x * 0.4, 176),
                (198, 206),
            ],
        )
        # Soft folded-haunch shading
        if self.scale >= 0.55:
            self._line(
                [(154 + vib_x * 0.4, 190), (170 + vib_x * 0.3, 216), (164, 244)],
                self._coat_shadow, 2.0,
            )
        # Cute tucked white hind toe-tip peeking beside the haunch
        self._sock(184, g - 2.5, 11.0, 5.6, toes=False)

        # 3. Wide, lush, fluffy snow-white tuxedo chest bib starting RIGHT under the black chin!
        bib = [
            (94 + vib_x, 130 - lift),
            (146 + vib_x, 130 - lift),
            (156 + vib_x * 0.8, 158),
            (148 + vib_x * 0.6, 196),
            (134 + vib_x * 0.3, 222),
            (120 + vib_x * 0.2, 229),
            (106 + vib_x * 0.3, 222),
            (92 + vib_x * 0.6, 196),
            (84 + vib_x * 0.8, 158),
        ]
        self._bib(bib, tufts=5)

    def _sit(self, t, state, brain, pupil):
        g = self.GROUND
        reaction = getattr(self, "_reaction", "none")
        breath = math.sin(t * 2 * math.pi / 3.6)
        elapsed = float(getattr(brain, "elapsed", 0.0) or 0.0)

        if state == "play":
            sw, sw2 = math.sin(t * 7.0) * 4.0, math.sin(t * 7.0 - 1.1) * 7.0
        elif reaction == "music":
            sw, sw2 = math.sin(t * 2.4) * 7.5, math.sin(t * 2.4 - 0.85) * 12.5
        elif reaction == "video":
            sw, sw2 = math.sin(t * 0.85) * 3.5, math.sin(t * 0.85 - 0.9) * 6.0
        else:
            sw, sw2 = math.sin(t * 1.15) * 5.0, math.sin(t * 1.15 - 0.9) * 8.5

        lift = breath * 1.4
        self._sit_body(lift=lift, vib_x=0.0, tail_sw=(sw, sw2))

        # 4. Plush black front legs with dainty snow-white paw tips close together
        lift_l = lift_r = 0.0
        if state == "knead":
            lift_l = max(0.0, math.sin(t * 4.8)) * 6.5
            lift_r = max(0.0, -math.sin(t * 4.8)) * 6.5

        groom_over_head = None
        groom_mouth = "closed"
        groom_tilt = 0.0
        groom_lid = 0.0
        groom_tongue = 0.0
        groom_hx_off = 0.0
        groom_hy_off = 0.0

        if state == "groom":
            # Left supporting plush front leg planted cleanly on floor
            self._curved_limb(
                [(90, 178), (92, 212), (98, 239), (104, g - 3.0)],
                [20.5, 16.0, 12.8, 10.6],
                sock=True, sock_start=0.78, toes=True, forward=1.0,
            )
            # Realistic 3-phase feline bath:
            # Phase 1 (0.00..0.38): lick plush white paw cleanly with cute pink tongue
            # Phase 2 (0.38..0.78): sweep moist paw in curved arc across cheek & behind ear!
            # Phase 3 (0.78..1.00): lower paw gently & peaceful slow blink
            groom_t = elapsed if elapsed > 0.0 else t
            cyc = (groom_t * 0.34) % 1.0
            if cyc < 0.38:
                u = cyc / 0.38
                lick_wave = math.sin(u * math.pi * 4.0)
                lick_bob = lick_wave * 2.4
                paw_x = 131.5 + math.sin(u * math.pi) * 2.0
                paw_y = 140.5 + lick_bob
                elbow_x, elbow_y = 154.0, 182.0
                groom_mouth = "groom"
                groom_tongue = 0.50 + 0.50 * max(0.0, lick_wave)
                groom_tilt = 11.0 + lick_bob * 0.5
                groom_lid = 0.52
                groom_hx_off = 5.0
                groom_hy_off = 7.5
                groom_over_head = (
                    [(148, 190), (elbow_x, elbow_y), (paw_x + 5, (elbow_y + paw_y) * 0.5), (paw_x, paw_y)],
                    [19.5, 15.8, 12.8, 10.6],
                    True,
                )
            elif cyc < 0.78:
                u = (cyc - 0.38) / 0.40
                sweep = math.sin(u * math.pi)
                # Curved cheek-and-ear wash arc (paw sweeps up by ear then glides down cheek cleanly!)
                ang = -0.30 + u * 2.40
                paw_x = 152.0 + math.sin(ang) * 14.0
                paw_y = 132.0 - math.sin(u * math.pi) * 24.0 + math.cos(ang) * 5.0
                elbow_x = 168.0 + sweep * 6.0
                elbow_y = 178.0 - sweep * 14.0
                groom_mouth = "closed"
                groom_tilt = 10.0 + sweep * 10.0
                groom_lid = 0.84
                groom_hx_off = 7.0 + sweep * 2.5
                groom_hy_off = 6.0 - sweep * 2.0
                groom_over_head = (
                    [(148, 190), (elbow_x, elbow_y), ((elbow_x + paw_x) * 0.5 + 3, (elbow_y + paw_y) * 0.5), (paw_x, paw_y)],
                    [19.5, 15.8, 12.8, 10.6],
                    False,
                )
            else:
                u = (cyc - 0.78) / 0.22
                ease = 0.5 - 0.5 * math.cos(u * math.pi)
                paw_x = 142.0 - ease * 8.0
                paw_y = 164.0 + ease * 78.0
                elbow_x = 156.0 - ease * 10.0
                elbow_y = 192.0 + ease * 20.0
                groom_mouth = "closed"
                groom_tilt = 8.0 * (1.0 - ease)
                groom_lid = 0.78 * math.sin(u * math.pi)
                groom_hx_off = 4.5 * (1.0 - ease)
                groom_hy_off = 4.5 * (1.0 - ease)
                self._curved_limb(
                    [(146, 184), (elbow_x, elbow_y), (paw_x, paw_y)],
                    [19.5, 15.6, 11.4],
                    sock=True, sock_start=0.76, toes=True, forward=-1.0,
                )
        else:
            # Plush black front legs with dainty white paws sitting neatly close together
            self._curved_limb(
                [
                    (90, 178 - lift * 0.4),
                    (92, 212 - lift_l * 0.3),
                    (98, 239 - lift_l * 0.7),
                    (104 - lift_l * 0.2, g - 3.0 - lift_l),
                ],
                [20.5, 16.0, 12.8, 10.6],
                sock=True, sock_start=0.78, toes=True, show_beans=lift_l > 3.5, forward=1.0,
            )
            self._curved_limb(
                [
                    (148, 180 - lift * 0.4),
                    (146, 212 - lift_r * 0.3),
                    (140, 239 - lift_r * 0.7),
                    (134 - lift_r * 0.2, g - 3.0 - lift_r),
                ],
                [20.5, 16.0, 12.8, 10.6],
                sock=True, sock_start=0.78, toes=True, show_beans=lift_r > 3.5, forward=-1.0,
            )

        # 5. Photo-faithful adorable plush round black Kömür head
        hx, hy = 120.0, 106.0 - lift
        eyes, mouth, ears, lid = "open", "closed", "up", 0.0
        gaze = (1.6 + math.sin(t * 0.42) * 1.4, math.cos(t * 0.31) * 0.6)
        tilt = math.sin(t * 0.35) * 1.4
        yawn_open = 12.0

        if state == "look":
            gaze = (math.sin(t * 1.1) * 5.2, math.cos(t * 0.7) * 1.8)
            hx += math.sin(t * 1.1) * 3.5
            tilt = math.sin(t * 0.55) * 5.5
        elif state == "purr_idle":
            eyes = "happy"
            ears = "relaxed"
            hy += 2.0
        elif state == "bored":
            lid = 0.64 + 0.08 * math.sin(t * 1.4)
            ears = "droop"
            gaze = (3.5, 2.8)
            hy += 3.5
        elif state == "chirp":
            mouth = "chirp"
            hy -= 2.5
            gaze = (2.0, -2.6)
            tilt = -4.5
            ears = "forward"
        elif state == "yawn":
            # Smooth gradual yawn opening -> peak wide yawn with curled tongue & tiny fangs -> soft relax
            u_y = ((t + 0.55) % 3.2) / 3.2
            yawn_p = math.sin(u_y * math.pi) ** 1.25
            eyes = "squeezed" if yawn_p > 0.25 else "open"
            lid = 0.65 if yawn_p <= 0.25 else 0.0
            mouth = "yawn" if yawn_p > 0.14 else "closed"
            yawn_open = 4.0 + 15.5 * yawn_p
            hy += 1.5 - yawn_p * 3.0
            tilt = -4.0 * yawn_p
            ears = "back" if yawn_p > 0.3 else "relaxed"
        elif state == "groom":
            tilt = groom_tilt
            hx += groom_hx_off
            hy += groom_hy_off
            gaze = (3.5, 3.5)
            lid = groom_lid
            mouth = groom_mouth
            ears = "relaxed"
        elif state == "sneeze":
            phase = elapsed % 1.0 if elapsed else 0.3
            if phase < 0.45:
                hy -= 5.5 * (phase / 0.45)
                tilt = -7.5 * (phase / 0.45)
                eyes, mouth = "squeezed", "sneeze"
            else:
                hy += 6.5
                tilt = 9.0
                eyes, mouth = "squeezed", "sneeze"
                ears = "back"
        elif state == "knead":
            lid = 0.38
            ears = "relaxed"
            gaze = (2.0, 2.0)

        if reaction == "video" and state in ("sit", "look", "purr_idle"):
            ears = "relaxed"
            gaze = (3.6 + math.sin(t * 0.55) * 1.6, -0.8 + math.cos(t * 0.4) * 0.8)
            lid = max(lid, 0.22)
            hy += 1.5
        elif reaction == "music" and state in ("sit", "look", "purr_idle"):
            ears = "relaxed"
            lid = max(lid, 0.34 + 0.08 * math.sin(t * 2.2))

        if eyes == "open":
            allow_slow = state in ("sit", "look", "knead")
            lid = max(lid, self._blink_amount(t, allow_slow=allow_slow))

        self._head(
            hx, hy - 2.0, t, size=0.95, tilt=tilt, eyes=eyes, pupil=pupil, gaze=gaze,
            lid=lid, mouth=mouth, ears=ears,
            open_amount=yawn_open, tongue_out=groom_tongue, profile=0.0,
        )

        # Draw active grooming paw OVER the cheek/chin so the cat genuinely licks & washes her face!
        if groom_over_head is not None:
            g_pts, g_w, show_beans = groom_over_head
            self._curved_limb(
                g_pts, g_w,
                sock=True, sock_start=0.72, toes=False, show_beans=show_beans,
                paw_rx=10.5, paw_ry=6.8, forward=-1.0, paw_offset=(0.0, -1.0),
            )

    def _gait_limb(self, leg, width, far):
        """Plush, full-volume feline front or hind leg from IK joints with graceful swing wrist flex."""
        pts = list(leg.joints)
        n = len(pts)
        front = (n == 3)
        swing_u = float(getattr(leg, "swing_u", 0.0) or 0.0)
        flex = math.sin(math.pi * swing_u) if leg.lifted else 0.0

        if front:
            # 3 joints: shoulder -> elbow -> foot; add plush mid-forearm & supple wrist flex
            s0, el, ft = pts[0], pts[1], pts[2]
            ft_draw = (ft[0] - flex * 3.0, ft[1] - flex * 1.2)
            fore_mid = ((el[0] + ft_draw[0]) * 0.5 + 1.2, (el[1] + ft_draw[1]) * 0.5)
            chain = [s0, el, fore_mid, ft_draw]
            widths = [width * 1.38, width * 0.98, width * 0.78, width * 0.64]
            sock_u = 0.78
        else:
            # 4 joints: hip -> stifle/knee -> hock -> foot (plush rounded thigh -> supple Z-hock!)
            hp, kn, hk, ft = pts[0], pts[1], pts[2], pts[3]
            ft_draw = (ft[0] - flex * 2.5, ft[1] - flex * 1.0)
            chain = [hp, kn, hk, ft_draw]
            widths = [width * 1.66, width * 1.20, width * 0.80, width * 0.64]
            sock_u = 0.80

        base_col = self._far_fur if far else self._coat_shadow
        # ZERO outline seam where limb joins body — seamless plush velvet fur!
        self._tapered(chain, widths, base_col, "", 1, round_start=True)
        if not far:
            inner_pts = [(x + 0.5, y - 0.4) for x, y in chain]
            self._tapered(inner_pts, [w * 0.91 for w in widths], self._coat, "", 1, round_start=True)
            if self.scale >= 0.60:
                hi_pts = [(x + w * 0.12, y - 0.3) for (x, y), w in zip(chain[:-1], widths[:-1])]
                hi_w = [max(1.2, w * 0.20) for w in widths[:-1]]
                self._tapered(hi_pts, hi_w, self._fur_mid, "", 1, round_start=True)

        # Dainty snow-white toe-tip sock wrapping only the lower wrist/ankle
        s_pts, s_w = self._split_chain(chain, widths, sock_u)
        self._tapered(s_pts, [w * 1.02 for w in s_w], self._white_mid if far else self.WHITE, "", 1, round_start=True)
        if not far:
            self._tapered(s_pts, [w * 0.92 for w in s_w], self.WHITE, "", 1, round_start=True)

        fx, fy = chain[-1]
        lift = max(0.0, self.GROUND - 2.0 - fy)
        rx = (width * 0.48 + 2.4) * (0.92 if leg.lifted else 1.0)
        ry = 5.6 if far else 6.2
        paw_angle = (-22.0 if front else -16.0) * flex
        self._sock(
            fx + 1.8 - flex * 1.5, self.GROUND - 1.5, rx, ry,
            toes=not far and not leg.lifted, lift=lift, forward=1.0, angle=paw_angle,
        )

    def _measure_ground_speed(self, brain, t):
        """Convert screen px/s body speed to logical px/s (prevents foot slip)."""
        x, y = getattr(brain, "x", None), getattr(brain, "y", None)
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        prev, self._walk_sample = self._walk_sample, (t, x, y)
        if prev is None or not 0.0 < t - prev[0] < 0.5:
            return None
        return abs(x - prev[1]) / (t - prev[0]) / max(self.scale, 1e-6)

    def _walk(self, t, state, pupil, speed=8.0, ground_speed=None, crouch=0.0, ears="up"):
        """Genuine realistic plush 3/4-profile walking cat with 4-beat lateral gait & flowing tail."""
        g = self.GROUND
        if self._gait is None:
            from feline_locomotion import FelineGait
            self._gait = FelineGait()
        if ground_speed is None:
            ground_speed = speed * 7.0
        drop = max(0.0, float(crouch))
        pose = self._gait.pose(t, ground_speed, {
            "LH": (74, 198 + drop * 0.60), "LF": (172, 198 + drop * 0.60),
            "RH": (90, 196 + drop * 0.60), "RF": (158, 196 + drop * 0.60),
        }, g - 2)
        bob = pose.bob + drop
        sp = pose.spine
        sh = pose.shoulder * 0.95

        # 1. Far legs (softly recessed deeper coat shade for natural 3D depth)
        self._gait_limb(pose.legs["RH"], 18.5, far=True)
        self._gait_limb(pose.legs["RF"], 17.5, far=True)

        # 2. Thick plush fluffy black tail trailing gracefully with fluid travelling sine wave!
        tail_drop = drop * 0.85
        tw1 = math.sin(t * 2.5 - 0.5) * 4.5
        tw2 = math.sin(t * 2.5 - 1.1) * 7.5
        tw3 = math.sin(t * 2.5 - 1.7) * 10.5
        tw4 = math.sin(t * 2.5 - 2.3) * 12.5
        self._tail(
            [
                (58, 178 + bob - sp * 0.5),
                (40, 166 + bob + tw1 * 0.4 + tail_drop * 0.3),
                (26, 148 + tw2 * 0.5 + tail_drop * 0.55),
                (25, 126 + tw3 * 0.7 + tail_drop * 0.70),
                (37, 108 + tw4 * 0.8 + tail_drop * 0.80),
                (53, 100 + tw4 * 0.9 + tail_drop * 0.85),
            ],
            [14.5, 14.0, 13.0, 11.6, 10.0, 8.2],
        )

        # 3. Plush, full-bodied feline torso (curved spine, soft shoulder rise, rounded rump, warm belly)
        body = [
            (50, 180 + bob - sp),          # plush rounded rump back
            (78, 156 + bob - sp),          # hip / pelvis crest
            (124, 156 + bob),              # supple mid-back spine
            (166, 152 + bob + sp - sh),    # plush shoulder withers
            (192, 160 + bob + sp * 0.8),   # smooth plush neck/chest junction
            (204, 180 + bob + sp),         # smooth natural rounded chest front
            (194, 206 + bob + sp),         # sternum
            (162, 215 + bob + sp * 0.5),   # cozy ribcage bottom
            (122, 212 + bob),              # warm natural feline belly
            (80, 216 + bob - sp * 0.5),    # plush hind thigh join
            (52, 202 + bob - sp),          # lower rounded rump
        ]
        self._fur_mass(
            body, 128, 186 + bob, inner=0.86, lift=3.0,
            highlight=[
                (76, 164 + bob - sp),
                (124, 161 + bob),
                (168, 160 + bob + sp - sh),
            ],
        )

        # Soft plush neck bridge connecting chest smoothly into the 3/4-profile head
        head_y = 140.0 + pose.bob * 0.30 + drop * 0.90
        neck = [
            (166, 156 + bob + sp * 0.6),
            (190, head_y + 16),
            (205, head_y + 28),
            (200, 184 + bob + sp),
            (172, 188 + bob + sp),
        ]
        self._poly(neck, self._coat, "", 1, smooth=True)

        # Smoothly integrated fluffy snow-white chest ruff following the natural chest contour!
        self._bib(
            [
                (179, 170 + bob + sp * 0.7), (197, 178 + bob + sp),
                (199, 194 + bob + sp), (188, 206 + bob + sp),
                (176, 202 + bob + sp), (174, 186 + bob + sp),
            ],
            tufts=3,
        )

        # 4. Near plush full-volume legs (thick rounded thigh/Z-hock & muscular shoulder/forearm)
        self._gait_limb(pose.legs["LH"], 20.5, far=False)
        self._gait_limb(pose.legs["LF"], 19.5, far=False)

        # 5. Stabilized plush 3/4-profile Kömür head looking smoothly forward along stride!
        lid = self._blink_amount(t, allow_slow=False)
        gaze = (3.8, 0.8) if state == "follow" else (2.8, 0.2)
        self._head(
            195.0, head_y, t, size=0.86, tilt=3.0 if drop > 5 else 1.0,
            eyes="open", pupil=pupil, gaze=gaze, lid=lid, ears=ears,
            profile=0.68,
        )

    def _play(self, t, brain, pupil, ball_local):
        g = self.GROUND
        pounce = getattr(brain, "pounce", None)
        try:
            pounce = max(0.0, min(1.0, float(pounce))) if pounce is not None else None
        except (TypeError, ValueError):
            pounce = None
        if pounce is None:
            cyc = t % 2.6
            pounce = max(0.0, math.sin((cyc - 1.6) / 1.0 * math.pi)) if cyc > 1.6 else 0.0

        wiggle = math.sin(t * 12.0) * 2.4 * (1.0 - pounce)
        sw = math.sin(t * 7.5) * 5.0
        sw2 = math.sin(t * 7.5 - 1.1) * 9.0
        lunge = pounce * 18.0

        self._sock(74, g - 2, 11.5, 5.8, toes=False)
        self._tail(
            [
                (54 + wiggle, 202), (34, 182), (28, 156),
                (40, 134 + sw), (58, 126 + sw2),
            ],
            [14.0, 13.0, 11.4, 9.6, 7.6],
        )

        # Plush coiled hunter body
        body = [
            (48 + wiggle, 184 - pounce * 6), (82 + wiggle, 160 - pounce * 8),
            (124, 166 - pounce * 5), (166 + lunge * 0.3, 190),
            (198 + lunge * 0.5, 204), (208 + lunge * 0.6, 228),
            (194 + lunge * 0.6, 246), (146, 246), (98, 244),
            (60 + wiggle, 238), (44 + wiggle, 212),
        ]
        self._fur_mass(
            body, 128, 204, inner=0.86, lift=3.0,
            highlight=[
                (72 + wiggle, 170 - pounce * 7),
                (120, 172 - pounce * 5),
                (166, 194),
            ],
        )
        # Plush folded near hind haunch & hock
        self._curved_limb(
            [(78 + wiggle, 204), (62 + wiggle, 226), (76 + wiggle, 248), (94, g - 2.5)],
            [24.0, 18.0, 13.0, 10.6],
            sock=True, sock_start=0.80, toes=True, forward=1.0,
        )
        self._bib(
            [
                (170 + lunge * 0.4, 204), (198 + lunge * 0.5, 212),
                (204 + lunge * 0.6, 234), (186 + lunge * 0.5, 244),
                (166, 238), (162, 218),
            ],
            tufts=4,
        )

        bx, by = ball_local
        self._curved_limb(
            [(176 + lunge * 0.3, 216), (174 + lunge * 0.3, 238), (180 + lunge * 0.3, g - 3)],
            [18.0, 14.5, 11.2],
            sock=True, sock_start=0.76, far=True, toes=False, forward=1.0,
        )
        if pounce > 0.15:
            reach = pounce
            tx = max(200.0, min(244.0, 198.0 + (bx - 12.0 - 198.0) * reach))
            ty = g - 3.0 + (min(by, g - 3.0) - (g - 3.0)) * reach
            self._curved_limb(
                [
                    (190 + lunge * 0.4, 218),
                    ((192 + tx) * 0.5, (218 + ty) * 0.5 - 8.0),
                    (tx, ty),
                ],
                [19.5, 15.6, 12.2],
                sock=True, sock_start=0.76, toes=True, forward=1.0,
            )
        else:
            self._curved_limb(
                [(192, 216), (190, 238), (198, g - 2.5)],
                [19.5, 15.4, 11.8],
                sock=True, sock_start=0.76, toes=True, forward=1.0,
            )

        hx = 192.0 + lunge * 0.50
        hy = 192.0 - pounce * 4.0
        gaze_x = max(-4.5, min(4.5, (bx - hx) * 0.08))
        gaze_y = max(-2.5, min(3.5, (by - hy) * 0.06))
        lid = self._blink_amount(t, offset=1.7, allow_slow=False)
        self._head(
            hx, hy, t, size=0.84, tilt=math.sin(t * 3.0) * 2.0,
            eyes="open", pupil=pupil, gaze=(gaze_x, gaze_y), lid=lid,
            ears="forward" if pounce < 0.55 else "back", profile=0.62,
        )

    def _stretch(self, t, pupil):
        """Authentic fluid cat bow-stretch: extended front legs flat on floor, low chest, tall rump & high curled tail."""
        g = self.GROUND
        reach = math.sin(t * 2.2) * 3.5
        sw = math.sin(t * 1.4) * 5.0
        sw2 = math.sin(t * 1.4 - 0.9) * 8.5

        # Far plush hind leg standing tall with authentic feline hock angle
        self._curved_limb(
            [(94, 178), (104, 206), (92, 232), (96, g - 3.0)],
            [24.0, 18.0, 13.0, 10.6],
            sock=True, sock_start=0.80, far=True, toes=False, forward=1.0,
        )
        # Thick fluffy tail curving steeply upward with a graceful curling tip!
        self._tail(
            [
                (62, 164), (44, 138), (38, 108),
                (48, 82 + sw * 0.6), (68, 72 + sw2 * 0.7), (82, 80 + sw2 * 0.8),
            ],
            [14.5, 13.8, 12.6, 11.2, 9.6, 7.8],
        )

        # Sweeping concave plush bow-stretch torso: rounded hindquarters high -> deep dipped chest near floor!
        body = [
            (54, 160), (84, 140), (118, 152), (148, 184),
            (176, 212), (192, 234), (178, 250),
            (138, 244), (102, 222), (70, 208), (50, 188),
        ]
        self._fur_mass(
            body, 122, 194, inner=0.86, lift=3.2,
            highlight=[(74, 148), (114, 160), (154, 194)],
        )
        # Near plush muscular hind leg planted tall
        self._curved_limb(
            [(76, 178), (86, 208), (72, 234), (76, g - 2.5)],
            [26.5, 19.6, 14.0, 11.2],
            sock=True, sock_start=0.80, toes=True, forward=1.0,
        )

        # Plush front legs stretched far forward flat on the floor!
        self._curved_limb(
            [(174, 232), (202 + reach * 0.5, 246), (228 + reach, g - 5.0)],
            [18.5, 14.6, 11.4],
            sock=True, sock_start=0.76, far=True, toes=False, forward=1.0,
            paw_offset=(2.0, 0.8),
        )
        self._curved_limb(
            [(180, 236), (208 + reach * 0.5, 250), (235 + reach, g - 2.5)],
            [19.8, 15.6, 12.0],
            sock=True, sock_start=0.76, toes=True, forward=1.0,
            paw_offset=(2.5, 0.8),
        )
        # Fluffy snow-white chest bib dipping low close to the floor
        self._bib(
            [(166, 212), (192, 224), (196, 244), (178, 250), (162, 240), (160, 226)],
            tufts=4,
        )
        # Blissfully squinted 3/4-profile head dipped low between extended forelegs
        self._head(
            190.0, 208.0, t, size=0.82, tilt=8.0, eyes="happy", pupil=pupil,
            mouth="yawn" if (t % 6.0) < 1.6 else "closed", ears="back",
            open_amount=7.5 + 4.5 * math.sin(t * 4.0), profile=0.62,
        )

    def _hiss(self, t, pupil):
        """Defensive arched Halloween-cat posture with plush hackles, braced legs & bottle-brush tail."""
        g = self.GROUND
        shake = math.sin(t * 28.0) * 0.75

        self._curved_limb(
            [(94, 206), (98, 226), (92, 244), (96, g - 3.0)],
            [20.0, 15.6, 12.0, 10.2],
            sock=True, sock_start=0.78, far=True, toes=False, forward=1.0,
        )
        self._curved_limb(
            [(172, 204), (168, 232), (174, g - 3.0)],
            [18.0, 14.2, 10.8],
            sock=True, sock_start=0.76, far=True, toes=False, forward=1.0,
        )

        # Piloerected bottle-brush tail straight up
        puff = [(70, 200), (56, 174), (48, 144), (46, 116), (50, 92)]
        self._tail(puff, [16, 20, 22, 20, 14], outline_w=0.8, puffed=True)

        body = [
            (64, 198), (78, 156), (108, 130), (140, 126),
            (172, 144), (190, 172), (196, 200),
            (184, 224), (148, 228), (112, 226), (76, 220),
        ]
        body = [(x + shake, y) for x, y in body]
        self._fur_mass(
            body, 132, 182, inner=0.86, lift=3.2,
            highlight=[(90, 148), (130, 134), (168, 152)],
        )
        for bx, by, ang in (
            (80, 156, -0.78), (94, 142, -0.52), (110, 133, -0.28),
            (126, 128, -0.08), (142, 128, 0.12), (158, 134, 0.36), (172, 146, 0.58),
        ):
            tx = bx + math.sin(ang - 0.35) * 6.5
            ty = by - math.cos(ang - 0.35) * 5.2
            self._line([(bx + shake, by + 1), (tx + shake, ty)], self._outline, 1.3, smooth=False)

        self._curved_limb(
            [(84, 204), (88, 226), (80, 246), (84, g - 2.5)],
            [22.5, 16.8, 12.4, 10.6],
            sock=True, sock_start=0.78, toes=True, forward=1.0,
        )
        self._curved_limb(
            [(184, 204), (180, 232), (188, g - 2.5)],
            [19.5, 14.8, 11.4],
            sock=True, sock_start=0.76, toes=True, forward=1.0,
        )
        self._bib(
            [(170, 190), (198, 200), (200, 220), (184, 230), (166, 222), (164, 204)],
            tufts=4,
        )
        self._head(
            184.0 + shake, 178.0, t, size=0.84, tilt=4.0, eyes="open", pupil=pupil,
            gaze=(3.2, -0.8), mouth="hiss", ears="flat", twitch=False, profile=0.58,
        )

    def _sleep(self, t, state, pupil):
        """Cozy plush curled furball with thick fluffy tail wrapped warmly around dainty paws & face."""
        g = self.GROUND
        breath = math.sin(t * 2.0 * math.pi / 4.2)
        grow = 1.0 + 0.028 * breath

        # Soft plush curled furball silhouette
        body = [
            (52, 196), (84, 170), (132, 164), (180, 172),
            (214, 200), (214, 238), (186, g),
            (114, g), (62, 254), (42, 226),
        ]
        body = [(130.0 + (x - 130.0) * (1.0 + 0.010 * breath), g - (g - y) * grow) for x, y in body]
        self._fur_mass(
            body, 130, 216, inner=0.86, lift=3.5,
            highlight=[
                (86, 180 - 2.4 * breath),
                (142, 172 - 2.6 * breath),
                (188, 190 - 2.0 * breath),
            ],
        )
        # Cozy fluffy white chest peek nestled inside the curl
        self._bib(
            [
                (108, 204), (146, 200), (164, 216), (156, 240),
                (134, 248), (112, 244), (102, 224),
            ],
            tufts=4,
        )

        # Dainty white front paws tucked warmly under the black cheek
        self._sock(96, g - 2.5, 12.0, 6.2, toes=False)
        self._sock(118, g - 1.5, 11.5, 5.8, toes=False)

        # Thick plush black tail wrapped warmly around the paws & face!
        flick = 0.0
        phase = t % 9.2
        if phase < 0.55:
            flick = math.sin(phase / 0.55 * math.pi) * 4.5
        self._tail(
            [
                (206, 236), (190, 254), (160, 263),
                (128, 265), (100, 260 - flick * 0.5), (82, 252 - flick),
            ],
            [15.0, 14.5, 13.0, 11.6, 10.0, 8.2],
            use_springs=False,
        )

        waking = state in ("stretch", "yawn")
        hy = 222.0 - breath * 1.5
        if waking:
            self._head(
                94.0, 214.0, t, size=0.84, tilt=-8.0, eyes="squeezed", pupil=pupil,
                mouth="yawn", ears="droop", open_amount=9.0 + 5.0 * math.sin(t * 2.5),
            )
        else:
            self._head(
                92.0, hy, t, size=0.84, tilt=-15.0, eyes="closed", pupil=pupil,
                mouth="closed", ears="droop", twitch=True,
            )

    def _roll(self, t, pupil):
        """Plush relaxed side-reclining stretch with curved paws & wide fluffy tuxedo chest."""
        rock = math.sin(t * 2.8) * 2.0
        self._tail(
            [
                (64, 222), (44, 212), (38, 194), (50, 182),
                (66, 188), (72, 202), (64, 210),
            ],
            [14.0, 13.0, 11.6, 10.2, 8.8, 7.6, 6.6],
        )
        body = [
            (52, 204 + rock), (82, 178 + rock), (132, 174 + rock),
            (184, 184 + rock), (208, 210 + rock), (198, 242 + rock),
            (156, 252 + rock), (96, 248 + rock), (58, 236 + rock),
        ]
        self._fur_mass(
            body, 130, 214 + rock, inner=0.86, lift=3.2,
            highlight=[(86, 186 + rock), (132, 182 + rock), (176, 194 + rock)],
        )
        self._bib(
            [
                (136, 184 + rock), (174, 188 + rock), (196, 210 + rock),
                (186, 234 + rock), (154, 240 + rock), (132, 220 + rock),
            ],
            tufts=4,
        )
        self._curved_limb(
            [(136, 220 + rock), (160, 234 + rock), (178, 244 + rock)],
            [17.5, 14.2, 11.2],
            sock=True, sock_start=0.66, far=True, toes=False, show_beans=True, forward=1.0,
        )
        self._curved_limb(
            [(150, 214 + rock), (182, 222 + rock), (202, 230 + rock)],
            [19.0, 15.2, 12.0],
            sock=True, sock_start=0.66, toes=False, show_beans=True, forward=1.0,
        )
        self._sock(78, 240 + rock, 12.0, 6.2, toes=False)
        self._sock(98, 246 + rock, 12.0, 6.2, toes=True)
        lid = self._blink_amount(t, offset=0.7, allow_slow=True)
        self._head(
            176.0, 176.0 + rock, t, size=0.84, tilt=16.0 + rock * 1.2,
            eyes="open", pupil=pupil, gaze=(-2.0, 1.8), lid=max(0.26, lid),
            ears="droop", mouth="closed", profile=0.28,
        )

    # -- ball ---------------------------------------------------------------
    def _ball_logical(self, brain):
        x = getattr(brain, "ball_x", None)
        y = getattr(brain, "ball_y", None)
        if x is None or y is None:
            return (218.0, 241.0)
        try:
            brain_width = max(1.0, float(getattr(brain, "width", self.width)))
            brain_height = max(1.0, float(getattr(brain, "height", self.height)))
            lx = 24 + 209 * max(0.0, min(1.0, float(x) / brain_width))
            ly = 205 + 52 * max(0.0, min(1.0, float(y) / brain_height))
            return (lx, ly)
        except (TypeError, ValueError):
            return (218.0, 241.0)

    def _ball(self, brain, t, pos):
        x, y = pos
        g = self.GROUND
        height = max(0.0, g - 6 - y)
        shadow_r = max(6.0, 13 - height * 0.12)
        if not _IS_MAC:
            self._oval(x - shadow_r, g - 2, x + shadow_r, g + 3, self._pupil_col, "", 1, stipple="gray50")
        elif height < 40.0:
            sr = shadow_r * 0.65 * (1.0 - height / 40.0)
            if sr >= 2.0:
                self._oval(x - sr, g - 1, x + sr, g + 2, self._pupil_col, "", 1)
        self._oval(x - 12, y - 12, x + 12, y + 12, self.BALL, self.BALL_DARK, 1.3)
        try:
            vx = float(getattr(brain, "ball_vx", getattr(brain, "_ball_vx", 60.0)))
        except (TypeError, ValueError):
            vx = 60.0
        angle = (float(getattr(brain, "ball_x", 0.0) or 0.0) / 18.0) * (1 if vx >= 0 else 1)
        seam = []
        for k in range(5):
            a = angle + k * 0.5 - 1.0
            seam.append((x + math.cos(a) * 9, y + math.sin(a) * 9))
        self._line(seam, self.BALL_DARK, 1.4)
        self._oval(x - 8, y - 9, x - 2, y - 3, self.BALL_LIGHT)

    # -- legacy in-canvas bubble (off by default) ---------------------------
    def _bubble(self, message):
        message = str(message or "").strip()
        if not message:
            return
        pad = 8 * self.scale
        font = ("Segoe UI", max(8, int(11 * self.scale)), "bold")
        item = self.canvas.create_text(
            self.width / 2, 6 + pad, text=message, anchor="n", width=self.width - 2 * pad,
            font=font, fill="#27343b", justify="center", tags=self.TAG,
        )
        x1, y1, x2, y2 = self.canvas.bbox(item)
        box = self.canvas.create_rectangle(
            x1 - pad, y1 - pad, x2 + pad, y2 + pad, fill=self.WHITE, outline="#9aa8ab",
            width=self._w(1.5), tags=self.TAG,
        )
        self.canvas.tag_lower(box, item)
        self.item_count += 2

    # -- frame --------------------------------------------------------------
    _TOD_TINT = {"evening": ("#ff9a52", 0.07), "night": ("#1c2c64", 0.10)}
    _TOD_KEYS = ("FUR", "FUR_LIGHT", "FUR_EDGE", "WHITE", "WHITE_SHADE", "GOLD_LIGHT")

    def draw(self, brain, animation_time, message="", effect_orchestrator=None,
             draw_bubble=False, accessory=None, time_of_day=None):
        """Public entry. ``accessory`` / ``time_of_day`` override the renderer
        attributes of the same name for this frame (None = use attribute)."""
        tod = time_of_day if time_of_day is not None else self.time_of_day
        saved = {}
        tint = self._TOD_TINT.get(tod)
        if tint:
            for key in self._TOD_KEYS:
                saved[key] = self.__dict__.get(key, None)
                base = getattr(self, key)
                if key == "GOLD_LIGHT":
                    new = blend(base, "#ffffff", 0.35) if tod == "night" else base
                elif key == "WHITE":
                    new = blend(base, tint[0], tint[1] * 0.7)
                else:
                    new = blend(base, tint[0], tint[1])
                setattr(self, key, new)
        prev_acc = self.__dict__.get('accessory', None)
        if accessory is not None:
            self.accessory = accessory
        try:
            self._draw(brain, animation_time, message, effect_orchestrator, draw_bubble)
        finally:
            if prev_acc is None:
                self.__dict__.pop('accessory', None)
            else:
                self.accessory = prev_acc
            for key, old in saved.items():
                if old is None:
                    self.__dict__.pop(key, None)
                else:
                    setattr(self, key, old)

    def _draw(self, brain, animation_time, message="", effect_orchestrator=None,
              draw_bubble=False):
        """Render one frame from a brain with state, elapsed and facing fields."""
        self.canvas.delete(self.TAG)
        self.item_count = 0
        self.dx = self.dy = 0.0
        self.flip = False
        self._palette()
        raw_state = getattr(brain, "state", "sit")
        state = str(getattr(raw_state, "value", raw_state)).lower()
        try:
            facing = float(getattr(brain, "facing", 1))
        except (TypeError, ValueError):
            facing = 1.0
        try:
            t = float(animation_time)
        except (TypeError, ValueError):
            t = 0.0
        if not math.isfinite(t):
            t = 0.0
        dt = 0.016 if self._last_anim_time is None else max(0.0, min(0.1, t - self._last_anim_time))
        self._last_anim_time = t
        self.micro_time = t

        if effect_orchestrator is not None:
            self.effect_orchestrator = effect_orchestrator

        age_days = getattr(brain, "age_days", None)
        wobble_tilt = 0.0
        if age_days is not None:
            try:
                gm = GrowthStage.evaluate(float(age_days))
                self._growth_scale = gm.scale
                self._growth_head_scale = gm.head_scale
                if state in ("wander", "follow") and not getattr(brain, "paused", False):
                    wdx, wdy, wobble_tilt = GrowthStage.step_wobble(t, float(age_days))
                    self.dx += wdx
                    self.dy += wdy
            except (TypeError, ValueError):
                self._growth_scale = 1.0
                self._growth_head_scale = 1.0
        else:
            self._growth_scale = 1.0
            self._growth_head_scale = 1.0

        pointer_xy = getattr(brain, "pointer_xy", None)
        if pointer_xy is not None:
            head_px = self._xy(*self._head_logical)
            is_dark = bool(getattr(brain, "low_light", False)) or self.time_of_day == "night"
            gaze_vec, smooth_pupil = self.gaze_controller.update(
                dt, head_px, pointer_xy, is_dark=is_dark, play_mode=(state == "play")
            )
            self._gaze_override = gaze_vec
            pupil = smooth_pupil if getattr(brain, "pupil_dilation", None) is None else self._pupil(brain, state)
        else:
            self._gaze_override = None
            pupil = self._pupil(brain, state)

        vx = float(getattr(brain, "vx", 0.0) or 0.0)
        vy = float(getattr(brain, "vy", 0.0) or 0.0)
        startled = bool(getattr(brain, "startled", False))
        use_procedural_springs = bool(
            getattr(brain, "use_procedural_springs", getattr(self, "use_procedural_springs", True))
        )
        self._frame_use_springs = use_procedural_springs
        if startled or use_procedural_springs:
            if getattr(self, "ear_spring", None) is not None:
                self._ear_override = self.ear_spring.update(
                    dt, speed=math.hypot(vx, vy), mood=state, startled=startled, t=t
                )
        else:
            self._ear_override = None
        if use_procedural_springs and getattr(self, "tail_spring", None) is not None:
            pts_spring = self.tail_spring.update(
                dt, (196.0, 246.0), vel_xy=(vx, vy), facing=facing,
                wag_phase=t * (7.0 if state == "play" else 1.5),
                wag_amp=0.22 if state == "play" else 0.10,
            )
            self.tail_spring.points = pts_spring

        self.flip = facing < 0
        ball = None
        ball_local = (220.0, 244.0)
        hide_ball = bool(getattr(brain, "hide_internal_ball", False))
        if state == "play":
            if hide_ball:
                ball = None
                ball_local = (222.0, 246.0)
            else:
                ball = self._ball_logical(brain)
                self.flip = ball[0] < 128
                ball_local = (260 - ball[0], ball[1]) if self.flip else ball

        _NO_SWAY = ("sleep", "play", "hiss", "box_sit", "scratch", "jump",
                    "laser_chase", "drink", "eat", "perch")
        if state not in _NO_SWAY and not getattr(brain, "paused", False):
            self.idle_sway = math.sin(t * 0.15) * 0.6
            self.dx += self.idle_sway

        reaction = getattr(brain, "activity_reaction", "none")
        self._reaction = reaction if (state not in _NO_SWAY and not getattr(brain, "paused", False)) else "none"
        self._dance_tilt = wobble_tilt
        if self._reaction == "music":
            # Subtle lifelike feline musical sway (gentle head tilt + rhythmic ear/tail response, NO hopping)
            self._dance_tilt += math.sin(t * 2.4) * 3.4

        self._draw_paw_trails(brain)
        render_state = state
        vpose = getattr(brain, "visual_pose", None)
        vdur = float(getattr(brain, "visual_pose_duration", 0.0) or 0.0)
        if state == "sit" and vpose in ("eat", "purr_idle") and float(getattr(brain, "elapsed", 0.0) or 0.0) < vdur:
            render_state = vpose
        if render_state == "sleep":
            self._sleep(t, render_state, pupil)
        elif render_state == "roll":
            self._roll(t, pupil)
        elif render_state == "stretch":
            self._stretch(t, pupil)
        elif render_state in ("wander", "follow"):
            self._walk(t, render_state, pupil, speed=9.0 if render_state == "follow" else 8.0,
                       ground_speed=self._measure_ground_speed(brain, t))
        elif render_state == "play":
            self._play(t, brain, pupil, ball_local)
        elif render_state == "hiss":
            self._hiss(t, pupil)
        elif render_state == "drink":
            cat_poses.draw_drink(self, t, pupil)
        elif render_state == "eat":
            cat_poses.draw_eat(self, t, pupil)
        elif render_state == "scratch":
            cat_poses.draw_scratch(self, t, pupil)
        elif render_state == "box_sit":
            cat_poses.draw_box_sit(self, t, brain, pupil)
        elif render_state == "perch":
            cat_poses.draw_perch(self, t, pupil)
        elif render_state == "jump":
            cat_poses.draw_jump(self, t, pupil)
        elif render_state == "laser_chase":
            cat_poses.draw_laser_chase(self, t, brain, pupil)
        elif render_state == "purr_idle":
            cat_poses.draw_purr_idle(self, t, pupil)
        else:
            self._sit(t, render_state, brain, pupil)

        self.dx = self.dy = 0.0
        self.flip = False
        self._dance_tilt = 0.0
        self._reaction = "none"
        if ball is not None:
            self._ball(brain, t, ball)

        self._draw_world_overlays(brain, t)
        weather_kind = getattr(brain, "weather", None)
        if weather_kind:
            from weather import draw_weather
            draw_weather(self, weather_kind, t)

        emote = getattr(brain, "emote", None)
        if emote:
            emote_items = AnimeEmotes.draw(
                self.canvas,
                self._xy(*self._head_logical),
                emote,
                progress=t,
                scale=self.scale * self._growth_scale,
                tag=self.TAG,
            )
            self.item_count += len(emote_items)

        if self.effect_orchestrator is not None:
            self.effect_orchestrator.draw()

        if draw_bubble and message:
            self._bubble(message)

        if (self.retro_enabled or getattr(brain, "retro_mode", False)) and getattr(self, "retro_filter", None) is not None:
            self.retro_filter.apply(self.canvas, tag=self.TAG, width=self.width, height=self.height)

    def _draw_paw_dot(self, x, y, stipple, life=1.0):
        mac_tk = _IS_MAC and hasattr(self.canvas, "tk")
        s = self.scale * (0.45 + 0.55 * max(0.0, min(1.0, life)) if mac_tk else 1.0)
        r_pad = 4.2 * s
        kw = {} if mac_tk else {"stipple": stipple}
        self.canvas.create_oval(
            x - r_pad, y - r_pad * 0.8, x + r_pad, y + r_pad * 0.8,
            fill="#52606d", outline="", tags=self.TAG, **kw,
        )
        rt = 1.9 * s
        for ox, oy in ((-4.2, -5.5), (0.0, -6.8), (4.2, -5.5)):
            tx, ty = x + ox * s, y + oy * s
            self.canvas.create_oval(
                tx - rt, ty - rt, tx + rt, ty + rt,
                fill="#52606d", outline="", tags=self.TAG, **kw,
            )
        self.item_count += 4

    def _draw_paw_trails(self, brain):
        """Draw evaporating paw trails underneath the cat so they never blotch the fur."""
        bx = float(getattr(brain, "x", 0.0) or 0.0)
        by = float(getattr(brain, "y", 0.0) or 0.0)
        paw_trails = getattr(brain, "paw_trails", None)
        if not paw_trails:
            return
        mac_tk = _IS_MAC and hasattr(self.canvas, "tk")
        if isinstance(paw_trails, PawPrintTrail) or hasattr(paw_trails, "prints"):
            for p in paw_trails.prints:
                life = 1.0 - max(0.0, min(1.0, p.age / max(0.001, p.ttl)))
                if mac_tk and life < 0.35:
                    continue
                stipple = (
                    "gray75" if life > 0.72 else "gray50" if life > 0.45
                    else "gray25" if life > 0.2 else "gray12"
                )
                self._draw_paw_dot(p.x - bx, p.y - by, stipple, life=life)
        else:
            for pt in paw_trails:
                if isinstance(pt, dict):
                    px, py = float(pt.get("x", 0.0)) - bx, float(pt.get("y", 0.0)) - by
                    alpha = float(pt.get("alpha", 1.0))
                else:
                    px, py = float(getattr(pt, "x", 0.0)) - bx, float(getattr(pt, "y", 0.0)) - by
                    alpha = float(getattr(pt, "alpha", 1.0))
                if mac_tk and alpha < 0.35:
                    continue
                stipple = (
                    "gray75" if alpha > 0.72 else "gray50" if alpha > 0.45
                    else "gray25" if alpha > 0.2 else "gray12"
                )
                self._draw_paw_dot(px, py, stipple, life=alpha)

    def _draw_world_overlays(self, brain, t):
        """Draw desktop props (box/bed/laser) and task fishes."""
        bx = float(getattr(brain, "x", 0.0) or 0.0)
        by = float(getattr(brain, "y", 0.0) or 0.0)

        props = getattr(brain, "props", None)
        if props:
            on_bed = bool(getattr(brain, "on_bed", False))
            for prop in props:
                if isinstance(prop, dict):
                    if not prop.get("active", True):
                        continue
                    kind = str(prop.get("kind", "")).lower()
                    px = float(prop.get("x", 0.0)) - bx
                    py = float(prop.get("y", 0.0)) - by
                    pw = float(prop.get("width", 0.0))
                    ph = float(prop.get("height", 0.0))
                else:
                    if not getattr(prop, "active", True):
                        continue
                    kind = str(getattr(prop, "kind", "")).lower()
                    px = float(getattr(prop, "x", 0.0)) - bx
                    py = float(getattr(prop, "y", 0.0)) - by
                    pw = float(getattr(prop, "width", 0.0))
                    ph = float(getattr(prop, "height", 0.0))
                if kind == "box":
                    items = draw_cardboard_box(
                        self.canvas, px + pw * 0.5, py + ph, scale=self.scale, tag=self.TAG
                    )
                    self.item_count += len(items)
                elif kind == "bed":
                    items = draw_cat_bed(
                        self.canvas, px + pw * 0.5, py + ph * 0.5,
                        scale=self.scale, occupied=on_bed, tag=self.TAG,
                    )
                    self.item_count += len(items)
                elif kind == "laser":
                    items = draw_laser_dot(
                        self.canvas, px, py, t=t, scale=self.scale, tag=self.TAG
                    )
                    self.item_count += len(items)

        fishes = getattr(brain, "fishes", None)
        if fishes:
            for fish in fishes:
                if isinstance(fish, dict):
                    if fish.get("caught"):
                        continue
                    fx = float(fish.get("x", 0.0)) - bx
                    fy = float(fish.get("y", 0.0)) - by
                    label = str(fish.get("title", fish.get("label", "")) or "")
                    phase = float(fish.get("phase", t) or t)
                else:
                    if getattr(fish, "caught", False):
                        continue
                    fx = float(getattr(fish, "x", 0.0)) - bx
                    fy = float(getattr(fish, "y", 0.0)) - by
                    label = str(getattr(fish, "title", getattr(fish, "label", "")) or "")
                    phase = float(getattr(fish, "phase", t) or t)
                items = draw_task_fish(
                    self.canvas, fx, fy, t=phase, label=label, scale=self.scale, tag=self.TAG
                )
                self.item_count += len(items)
