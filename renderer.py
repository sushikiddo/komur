"""Draw an animated tuxedo cat in a 260 by 280 logical frame.

Colors are class attributes so a palette/skin can be swapped by overriding them
(see skins.py). Geometry is expressed in the logical 260x280 space and scaled to
the real canvas size by ``_xy``. Every derived shade (ear inner, belly, closed
eye lines…) is blended at draw time from the palette attributes, so a skin
recolor keeps the drawing consistent.

Poses (chosen from ``brain.state``):
    sit / look / purr_idle / chirp / knead / groom / yawn / sneeze  -> sitting
    wander / follow                                                -> walking
    play                                                           -> crouch/pounce
    bored                                                          -> drooping sit
    roll                                                           -> reclining side-roll
    stretch                                                        -> downward stretch
    hiss                                                           -> arched back
    sleep                                                          -> curled up
Unknown states fall back to sitting. ``facing`` < 0 mirrors the whole frame.

Optional brain attributes (read with getattr, all have defaults):
    ball_x, ball_y (window px), ball_vx, ball_vy, pounce (0..1),
    pupil_dilation (0..1 override), low_light (bool), elapsed (s in state).
"""
import math
import time

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


class CatRenderer:
    INK = "#0a0d13"
    FUR = "#111820"
    FUR_LIGHT = "#26313b"
    FUR_EDGE = "#39434b"
    WHITE = "#fffaf0"
    WHITE_SHADE = "#d8dfdf"
    GOLD = "#f8cd35"
    GOLD_LIGHT = "#fff17c"
    GOLD_DARK = "#c98720"
    PINK = "#ea8192"
    MOUTH = "#7c858c"
    BALL = "#e99444"
    BALL_DARK = "#8d4c32"
    BALL_LIGHT = "#ffda90"
    TAG = "cat_renderer"
    GROUND = 262.0
    LOW_LIGHT_HOURS = frozenset((21, 22, 23, 0, 1, 2, 3, 4, 5, 6))
    accessory = None       # None | "bow" | "scarf" | "hat" | "glasses"
    time_of_day = "day"    # "day" | "evening" | "night"
    _dance_tilt = 0.0
    _last_anim_time = None
    _head_logical = (116.0, 98.0)
    _growth_scale = 1.0
    _growth_head_scale = 1.0
    _gaze_override = None
    _ear_override = None
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
        self._head_logical = (116.0, 98.0)
        self._growth_scale = 1.0
        self._growth_head_scale = 1.0
        self._gaze_override = None
        self._ear_override = None
        self._gait = None            # feline_locomotion.FelineGait (ilk yürüyüşte)
        self._walk_sample = None     # (t, x, y) gerçek gövde hızını ölçmek için

    def set_retro_mode(self, enabled: bool):
        """Enable or disable the 90s retro pixel/dither post-filter."""
        self.retro_enabled = bool(enabled)

    def set_effect_orchestrator(self, eo):
        """Wire the effect orchestrator into the renderer."""
        self.effect_orchestrator = eo

    # -- derived palette ----------------------------------------------------
    def _palette(self):
        dark_fur = luminance(self.FUR) < 0.45
        self._belly = blend(self.INK, "#000000", 0.25)
        self._ear_inner = blend(self.PINK, self.INK, 0.42)
        self._ear_inner_light = blend(self.PINK, self.FUR_LIGHT, 0.25)
        self._nose = blend(self.PINK, self.INK, 0.38)
        self._mouth_in = blend(self.PINK, self.INK, 0.72)
        self._tongue = self.PINK
        self._fur_line = (blend(self.FUR_EDGE, self.WHITE, 0.4) if dark_fur
                          else blend(self.INK, self.FUR, 0.4))
        self._outline = self.FUR_EDGE
        self._eye_rim = self.INK if dark_fur else blend(self.INK, self.FUR, 0.2)

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
    def _tapered_outline(pts, widths):
        """Polygon outline for a centerline with per-point widths, rounded tip."""
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
        tip = (ex + dx / length * widths[-1] * 0.55, ey + dy / length * widths[-1] * 0.55)
        return left + [tip] + right[::-1]

    def _tapered(self, pts, widths, fill, outline="", width=1.2):
        return self._poly(self._tapered_outline(pts, widths), fill, outline, width, smooth=True)

    # -- fur primitives -----------------------------------------------------
    def _fur_mass(self, pts, cx, cy, inner=0.86, lift=4.0, highlight=None, outline_w=1.4):
        """A body part: INK base with an edge outline, lighter FUR core shifted
        towards the light (top), optional FUR_LIGHT highlight stroke."""
        self._poly(pts, self.INK, self._outline, outline_w, smooth=True)
        self._poly(self._scaled(pts, cx, cy, inner, 0, -lift), self.FUR, "", 1, smooth=True)
        if highlight:
            self._line(highlight, self.FUR_LIGHT, 3.2)

    def _tail(self, pts, widths, outline_w=1.3, puffed=False):
        """A tapered tail following ``pts`` with secondary highlight and spring physics."""
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
                blended.append((
                    px * 0.55 + (root_x + dx) * 0.45,
                    py * 0.55 + (root_y + dy) * 0.45,
                ))
            pts = blended
        self._tapered(pts, widths, self.INK, self._outline, outline_w)
        inner_w = [w * (0.6 if puffed else 0.5) for w in widths]
        self._tapered([(x, y - 1.5) for x, y in pts], inner_w, self.FUR)

    def _sock(self, x, y, rx=13, ry=7.5, toes=True, lift=0.0):
        """A white paw (tuxedo 'sock') resting at ground-level ``y``."""
        self._oval(x - rx, y - ry - lift, x + rx, y + ry - lift, self.WHITE, self.WHITE_SHADE, 1)
        if toes and self.scale >= 0.6:
            for off in (-rx * 0.38, rx * 0.12):
                self._line([(x + off, y + 1 - lift), (x + off + 0.6, y + ry * 0.75 - lift)],
                           self.WHITE_SHADE, 1.1)

    def _leg(self, x_top, y_top, x_bot, y_bot, width=18, sock=True, toes=True, far=False):
        """A straight-ish leg with a white sock at the bottom."""
        hw = width / 2
        self._poly([(x_top - hw, y_top), (x_top + hw, y_top),
                    (x_bot + hw * 0.95, y_bot), (x_bot - hw * 0.95, y_bot)],
                   self.INK if not far else self._belly, self._outline, 1.1)
        if sock:
            sy = y_bot - 14
            self._poly([(x_bot - hw * 0.9, sy), (x_bot + hw * 0.9, sy),
                        (x_bot + hw * 0.95, y_bot), (x_bot - hw * 0.95, y_bot)],
                       self.WHITE, "", 1, smooth=False)
        self._sock(x_bot, y_bot + 2, hw * 0.85 + 4, 7, toes=toes)

    # -- head ---------------------------------------------------------------
    def _head(self, cx, cy, t, *, size=1.0, tilt=0.0, eyes="open", pupil=0.3,
              gaze=(0.0, 0.0), lid=0.0, mouth="closed", ears="up", twitch=True,
              whiskers=True, open_amount=12.0):
        """Draw the head centred at (cx, cy). ``tilt`` is degrees (clockwise).
        eyes: open | closed | squeezed.  mouth: closed | yawn | hiss | chirp |
        groom | sneeze.  ears: up | back | flat | droop."""
        self._head_logical = (cx, cy)
        size = size * self._growth_head_scale
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

        # ears first (they sit behind the skull outline)
        for s in (-1, 1):
            tw = 0.0
            if twitch:
                period = 7.3 if s < 0 else 9.1
                phase = (t + (0 if s < 0 else 2.0)) % period
                if phase < 0.3:
                    tw = math.sin(phase / 0.3 * math.pi * 2) * 4
            if ears == "flat":
                tip = (s * 66, -24)
                outer = (s * 46, -2)
            elif ears == "back":
                tip = (s * 56 + tw, -52)
                outer = (s * 46, -8)
            elif ears == "droop":
                tip = (s * 48 + tw, -56)
                outer = (s * 46, -8)
            else:
                tip = (s * 38 + tw * s, -72)
                outer = (s * 46, -10)
            if self._ear_override is not None:
                angle_attr = "left_angle" if s < 0 else "right_angle"
                angle_val = getattr(self._ear_override, angle_attr, None)
                if angle_val is not None:
                    tip = (tip[0] + float(angle_val) * 0.4, tip[1] + abs(float(angle_val)) * 0.2)
                else:
                    ear_tw = float(getattr(self._ear_override, "twitch_left" if s < 0 else "twitch_right", 0.0) or 0.0)
                    layback = float(getattr(self._ear_override, "layback", 0.0) or 0.0)
                    tip = (
                        tip[0] + s * ear_tw * 0.6 + s * layback * 6.0,
                        tip[1] + layback * 8.0,
                    )
            inner_base = (s * 10, -36)
            ear = shape([inner_base, tip, outer])
            self._poly(ear, self.INK, self._outline, 1.3)
            gx = (inner_base[0] + tip[0] + outer[0]) / 3
            gy = (inner_base[1] + tip[1] + outer[1]) / 3
            inner = [(gx + (px - gx) * 0.55 + (tip[0] - gx) * 0.08,
                      gy + (py - gy) * 0.55 + (tip[1] - gy) * 0.08)
                     for px, py in (inner_base, tip, outer)]
            self._poly(shape(inner), self._ear_inner, "", 1)
            if self.scale >= 0.6:
                self._poly(shape([(gx + (px - gx) * 0.3, gy + (py - gy) * 0.3)
                                  for px, py in (inner_base, tip, outer)]),
                           self._ear_inner_light, "", 1)

        skull = [(0, -40), (27, -35), (43, -14), (45, 12), (29, 36), (0, 43),
                 (-29, 36), (-45, 12), (-43, -14), (-27, -35)]
        self._poly(shape(skull), self.INK, self._outline, 1.4, smooth=True)
        self._poly(shape(self._scaled(skull, 0, 0, 0.86, 0, -5)), self.FUR, "", 1, smooth=True)
        self._line(shape([(-24, -31), (0, -37), (24, -31)]), self.FUR_LIGHT, 3.2)
        if self.scale >= 0.6:
            self._line(shape([(36, -12), (41, 6)]), self.FUR_LIGHT, 2.2)
            self._line(shape([(-36, -12), (-41, 6)]), self.FUR_LIGHT, 2.2)

        # white muzzle + chin (tuxedo pattern)
        muzzle = [(-19, 6), (-25, 22), (-15, 38), (0, 42), (15, 38), (25, 22),
                  (19, 6), (8, 2), (-8, 2)]
        self._poly(shape(muzzle), self.WHITE, self.WHITE_SHADE, 0.9, smooth=True)

        # eyes
        for s in (-1, 1):
            ex, ey = s * 19, -4
            almond = [(ex - s * 13, ey + 2), (ex - s * 7, ey - 6), (ex, ey - 8),
                      (ex + s * 8, ey - 6), (ex + s * 13, ey - 1), (ex + s * 13, ey - 1),
                      (ex + s * 8, ey + 6), (ex, ey + 8), (ex - s * 7, ey + 6),
                      (ex - s * 13, ey + 2)]
            if eyes == "closed":
                self._line(shape([(ex - 12, ey), (ex, ey + 5), (ex + 12, ey)]),
                           self._fur_line, 2.2)
                continue
            if eyes == "squeezed":
                self._line(shape([(ex - 12, ey + 3), (ex, ey - 3), (ex + 12, ey + 3)]),
                           self._fur_line, 2.4)
                if self.scale >= 0.6:
                    self._line(shape([(ex - 9, ey + 8), (ex, ey + 4), (ex + 9, ey + 8)]),
                               self._fur_line, 1.2)
                continue
            self._poly(shape(self._scaled(almond, ex, ey, 1.18)), self._eye_rim, "", 1, smooth=True)
            self._poly(shape(almond), self.GOLD_DARK, "", 1, smooth=True)
            self._poly(shape(self._scaled(almond, ex, ey, 0.8, 0, 1.6)), self.GOLD, "", 1, smooth=True)
            if self.scale >= 0.6:
                self._oval(*tf(ex - s * 6 + gaze[0] * 0.3, ey + 1), *tf(ex - s * 1 + gaze[0] * 0.3, ey + 6),
                           self.GOLD_LIGHT)
            pw = 1.6 + 4.6 * max(0.0, min(1.0, pupil))
            ph = 6.5
            px, py = ex + gaze[0], ey + gaze[1]
            self._oval(*tf(px - pw, py - ph), *tf(px + pw, py + ph), self.INK)
            self._oval(*tf(px - pw * 0.6 - 1.2, py - 5), *tf(px - pw * 0.6 + 0.9, py - 2.6), self.WHITE)
            if lid > 0:
                top = ey - 10
                cover = top + 18 * lid
                self._poly(shape([(ex - 16, top), (ex + 16, top), (ex + 16, cover - 3),
                                  (ex, cover), (ex - 16, cover - 3)]),
                           self.FUR, "", 1, smooth=True)

        # nose
        self._poly(shape([(-5, 12), (5, 12), (0, 18)]), self._nose, "", 1)

        # mouth variants
        if mouth == "yawn":
            opening = open_amount
            self._poly(shape([(-9, 17), (9, 17), (10, 20 + opening * 0.55),
                              (0, 20 + opening), (-10, 20 + opening * 0.55)]),
                       self._mouth_in, self._nose, 0.8, smooth=True)
            self._oval(*tf(-5, 20 + opening * 0.55), *tf(5, 22 + opening), self._tongue)
        elif mouth == "hiss":
            self._poly(shape([(-11, 17), (11, 17), (12, 27), (0, 33), (-12, 27)]),
                       self._mouth_in, self._nose, 0.8, smooth=True)
            self._poly(shape([(-9, 18), (-5, 18), (-7, 25)]), self.WHITE, "", 1)
            self._poly(shape([(5, 18), (9, 18), (7, 25)]), self.WHITE, "", 1)
            self._oval(*tf(-4, 26), *tf(4, 31), self._tongue)
        elif mouth == "chirp":
            self._oval(*tf(-3.5, 20), *tf(3.5, 26), self._mouth_in)
            self._line(shape([(0, 18), (0, 20)]), self.MOUTH, 1.2)
        elif mouth == "sneeze":
            self._oval(*tf(-6, 19), *tf(6, 29), self._mouth_in)
            self._line(shape([(0, 18), (0, 19.5)]), self.MOUTH, 1.2)
        elif mouth == "groom":
            self._line(shape([(0, 18), (0, 22)]), self.MOUTH, 1.2)
            self._poly(shape([(2, 22), (13, 25), (7, 34)]), self._tongue, "", 1, smooth=True)
        else:
            self._line(shape([(0, 18), (0, 22)]), self.MOUTH, 1.2)
            self._line(shape([(0, 22), (-5, 26), (-10, 23)]), self.MOUTH, 1.2)
            self._line(shape([(0, 22), (5, 26), (10, 23)]), self.MOUTH, 1.2)

        if whiskers:
            for s in (-1, 1):
                root = (s * 12, 19)
                for (mx, my, tx, ty) in ((34, 11, 54, 5), (36, 18, 58, 17), (34, 24, 54, 30)):
                    self._line(shape([root, (s * mx, my), (s * tx, ty)]), self.WHITE, 1.1)

        self._accessory(shape, size)

    def _accessory(self, shape, size=1.0):
        """Draw the chosen accessory in head-local coordinates (``shape`` maps
        them through the head's position, size and tilt), so it follows the head
        in every pose. Chin is at y~42, eyes at (+-19, -4), crown at y~-40."""
        kind = self.accessory
        if LayeredCostumes.draw(self, kind, shape, size=size, t=self.micro_time):
            return
        if kind == "bow":
            red, dark = self.ACC_RED, self.ACC_RED_DARK
            self._poly(shape([(0, 50), (-20, 41), (-20, 59)]), red, dark, 1, smooth=False)
            self._poly(shape([(0, 50), (20, 41), (20, 59)]), red, dark, 1, smooth=False)
            self._poly(shape([(-5, 44), (5, 44), (5, 56), (-5, 56)]), dark, "", 1, smooth=True)
        elif kind == "scarf":
            red, dark = self.ACC_RED, self.ACC_RED_DARK
            self._poly(shape([(-34, 33), (-18, 43), (0, 46), (18, 43), (34, 33), (36, 45),
                              (18, 56), (0, 59), (-18, 56), (-36, 45)]),
                       red, dark, 1, smooth=True)
            self._line(shape([(-26, 42), (-22, 52)]), self.WHITE, 2)
            self._line(shape([(-8, 47), (-6, 57)]), self.WHITE, 2)
            self._line(shape([(10, 47), (8, 57)]), self.WHITE, 2)
            self._line(shape([(26, 42), (22, 52)]), self.WHITE, 2)
            self._poly(shape([(14, 52), (28, 50), (30, 74), (18, 76)]), red, dark, 1)
        elif kind == "hat":
            self._poly(shape([(-14, -42), (-12, -62), (-2, -68), (10, -64), (14, -42)]),
                       self.ACC_RED, self.ACC_RED_DARK, 1, smooth=True)
            self._poly(shape([(-13, -47), (13, -47), (14, -42), (-14, -42)]),
                       self.GOLD, "", 1)
            self._ellipse(shape([(0, -41)])[0], 22 * size, 5 * size,
                          self.ACC_RED_DARK, self.INK, 1)
        elif kind == "glasses":
            for s in (-1, 1):
                x0, y0 = s * 19, -4
                self._ellipse(shape([(x0, y0)])[0], 13 * size, 12 * size,
                              "", self.ACC_METAL, 2)
                self._line(shape([(x0 - s * 6, y0 - 8), (x0 - s * 11, y0 - 3)]),
                           self.WHITE, 1)
            self._line(shape([(-6, -6), (0, -9), (6, -6)]), self.ACC_METAL, 2)
            for s in (-1, 1):
                self._line(shape([(s * 33, -6), (s * 45, -10)]), self.ACC_METAL, 1.6)

    # -- awake-state helpers ------------------------------------------------
    def _blinking(self, t, offset=0.0):
        return ((t + offset) % 4.9) < 0.13

    def _pupil(self, brain, state):
        override = getattr(brain, "pupil_dilation", None)
        if override is not None:
            try:
                return max(0.0, min(1.0, float(override)))
            except (TypeError, ValueError):
                pass
        if state == "play":
            return 1.0
        if state == "hiss":
            return 0.12
        base = 0.45 if state == "look" else 0.3
        low = bool(getattr(brain, "low_light", False))
        if not low:
            try:
                low = time.localtime().tm_hour in self.LOW_LIGHT_HOURS
            except (OSError, ValueError, OverflowError):
                low = False
        return max(base, 0.8) if low else base

    # -- poses --------------------------------------------------------------
    def _sit(self, t, state, brain, pupil):
        g = self.GROUND
        breath = math.sin(t * 2 * math.pi / 3.4)
        sway_t = (t * 0.6, t * 0.6 - 0.9)
        sw = math.sin(t * 1.3) * 6
        sw2 = math.sin(t * 1.3 - 0.9) * 10
        if state == "play":
            sw, sw2 = math.sin(t * 7) * 4, math.sin(t * 7 - 1.1) * 7
        elapsed = float(getattr(brain, "elapsed", 0.0) or 0.0)

        # haunch (behind)
        self._oval(96, 162, 214, g, self.INK, self._outline, 1.4)
        self._oval(104, 170, 206, g - 12, self.FUR)
        self._line([(130, 172), (166, 164), (196, 182)], self.FUR_LIGHT, 3.2)
        # tail curls around the front-right
        self._tail([(196, 244), (222, 256), (244, 246), (246, 226 + sw), (236, 208 + sw2),
                    (222, 202 + sw2)], [14, 13, 11, 9, 7, 5])
        # torso
        lift = breath * 1.4
        torso = [(86, 126 - lift), (146, 126 - lift), (166, 158), (170, 212), (152, 252),
                 (116, 258), (80, 250), (66, 210), (70, 158)]
        self._fur_mass(torso, 118, 195, inner=0.9, lift=4)
        bib = [(100, 131 - lift), (132, 131 - lift), (150, 170), (148, 222), (134, 246),
               (104, 246), (88, 222), (86, 170)]
        self._poly(bib, self.WHITE, self.WHITE_SHADE, 1, smooth=True)
        if self.scale >= 0.6:
            self._line([(96, 160), (112, 168), (126, 160)], self.WHITE_SHADE, 1.3)

        # front legs (knead lifts them alternately, groom raises one)
        lift_l = lift_r = 0.0
        if state == "knead":
            lift_l = max(0.0, math.sin(t * 5)) * 7
            lift_r = max(0.0, -math.sin(t * 5)) * 7
        if state == "groom":
            # left leg down, right paw raised to the mouth
            self._leg(98, 205, 99, g - 2, 19)
            bob = math.sin(t * 6) * 4
            self._tapered([(138, 222), (150, 192), (146, 158 + bob)], [20, 18, 15],
                          self.INK, self._outline, 1.2)
            self._sock(146, 152 + bob, 12, 9, toes=False)
        else:
            self._leg(98, 205, 99 - lift_l * 0.2, g - 2 - lift_l, 19)
            self._leg(136, 205, 137 - lift_r * 0.2, g - 2 - lift_r, 19)
        self._sock(184, g - 2, 15, 7)

        # head
        hx, hy = 116, 98 - lift
        eyes, mouth, ears, lid = "open", "closed", "up", 0.0
        gaze = (3.0, 0.0)
        tilt = 0.0
        if state == "look":
            gaze = (math.sin(t * 1.1) * 7, math.cos(t * 0.7) * 2)
            hx += math.sin(t * 1.1) * 4
            tilt = math.sin(t * 0.55) * 6
        elif state == "purr_idle":
            lid = 0.55 + 0.1 * math.sin(t * 2)
            hy += 2
        elif state == "bored":
            lid = 0.65 + 0.08 * math.sin(t * 1.4)
            ears = "droop"
            gaze = (4.0, 3.0)
            hy += 4
        elif state == "chirp":
            mouth = "chirp"
            hy -= 3
            gaze = (2.0, -3.0)
            tilt = -5
        elif state == "yawn":
            eyes, mouth = "squeezed", "yawn"
            hy += 3
            tilt = 3
        elif state == "groom":
            tilt = 10
            hx += 6
            hy += 6
            gaze = (4.0, 4.0)
            lid = 0.35
            mouth = "groom"
        elif state == "sneeze":
            phase = elapsed % 1.0 if elapsed else 0.3
            if phase < 0.45:
                hy -= 6 * (phase / 0.45)
                tilt = -8 * (phase / 0.45)
                eyes, mouth = "squeezed", "sneeze"
            else:
                hy += 7
                tilt = 10
                eyes, mouth = "squeezed", "sneeze"
                ears = "back"
        elif state == "knead":
            lid = 0.3
            gaze = (2.0, 2.0)
        if eyes == "open" and self._blinking(t):
            eyes = "closed"
        self._head(hx, hy, t, tilt=tilt, eyes=eyes, pupil=pupil, gaze=gaze, lid=lid,
                   mouth=mouth, ears=ears,
                   open_amount=10 + 8 * (0.5 + 0.5 * math.sin(t * 2.5)))

    def _gait_limb(self, leg, width, far):
        """IK zincirini sivrilen bacak olarak çiz; ayakta beyaz çorap."""
        n = len(leg.joints)
        widths = [width * (1.0 - 0.28 * i / (n - 1)) for i in range(n)]
        self._tapered(leg.joints, widths, self._belly if far else self.INK, self._outline, 1.1)
        fx, fy = leg.foot
        lift = self.GROUND - 2 - fy
        self._sock(fx, self.GROUND, width * 0.42 + 4, 6.5 if far else 7,
                   toes=not far and not leg.lifted, lift=lift)

    def _measure_ground_speed(self, brain, t):
        """Ekran px/sn gövde hızını mantıksal px/sn'ye çevir (ayak kaymasını önler). Ölçülemezse None."""
        x, y = getattr(brain, "x", None), getattr(brain, "y", None)
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        prev, self._walk_sample = self._walk_sample, (t, x, y)
        if prev is None or not 0.0 < t - prev[0] < 0.5:
            return None
        return abs(x - prev[1]) / (t - prev[0]) / max(self.scale, 1e-6)

    def _walk(self, t, state, pupil, speed=8.0, ground_speed=None):
        g = self.GROUND
        if self._gait is None:
            from feline_locomotion import FelineGait
            self._gait = FelineGait()
        if ground_speed is None:
            ground_speed = speed * 7.0
        pose = self._gait.pose(t, ground_speed, {
            "LH": (82, 214), "LF": (184, 216), "RH": (94, 212), "RF": (174, 214),
        }, g - 2)
        bob = pose.bob
        sw = math.sin(t * 1.6) * 7
        sw2 = math.sin(t * 1.6 - 1.0) * 10
        # far legs first (sağ taraf, gölgede)
        for name in ("RH", "RF"):
            self._gait_limb(pose.legs[name], 15, far=True)
        # tail raised behind
        self._tail([(66, 198 + bob), (46, 178 + bob), (34, 150 + sw * 0.4), (38, 124 + sw),
                    (52, 108 + sw2)], [13, 12, 10, 8, 5])
        body = [(60, 178), (100, 160), (150, 156), (188, 164), (208, 188), (202, 216),
                (170, 230), (120, 236), (80, 232), (56, 208)]
        body = [(x, y + bob) for x, y in body]
        self._fur_mass(body, 130, 196, inner=0.88, lift=4,
                       highlight=[(84, 170 + bob), (132, 161 + bob), (182, 170 + bob)])
        # near legs (sol taraf); destek alan ön bacakta kürek kemiği kabarır
        if pose.shoulder:
            self._line([(166, 172 + bob - pose.shoulder), (184, 168 + bob - pose.shoulder * 1.4),
                        (198, 176 + bob - pose.shoulder)], self.FUR_LIGHT, 2.4)
        for name in ("LH", "LF"):
            self._gait_limb(pose.legs[name], 18, far=False)
        # chest bib
        self._poly([(176, 178 + bob), (204, 186 + bob), (208, 210 + bob), (194, 228 + bob),
                    (172, 224 + bob), (166, 200 + bob)], self.WHITE, self.WHITE_SHADE, 1, smooth=True)
        eyes = "closed" if self._blinking(t) else "open"
        gaze = (4.0, 1.0) if state == "follow" else (3.0, 0.0)
        self._head(190, 150 + bob, t, size=0.95, eyes=eyes, pupil=pupil, gaze=gaze)

    def _play(self, t, brain, pupil, ball_local):
        g = self.GROUND
        pounce = getattr(brain, "pounce", None)
        try:
            pounce = max(0.0, min(1.0, float(pounce))) if pounce is not None else None
        except (TypeError, ValueError):
            pounce = None
        if pounce is None:
            # no pounce info: periodic lunge
            cyc = t % 2.6
            pounce = max(0.0, math.sin((cyc - 1.6) / 1.0 * math.pi)) if cyc > 1.6 else 0.0
        wiggle = math.sin(t * 11) * 2.0 * (1 - pounce)
        sw = math.sin(t * 7) * 5
        sw2 = math.sin(t * 7 - 1.1) * 9
        lunge = pounce * 18
        # hind paws (crouched)
        self._sock(72, g - 1, 13, 7, toes=False)
        self._sock(96, g - 1, 13, 7, toes=False)
        self._tail([(52 + wiggle, 202), (34, 178), (30, 150), (42, 126 + sw), (60, 118 + sw2)],
                   [13, 12, 10, 8, 5])
        body = [(48 + wiggle, 184 - pounce * 6), (82 + wiggle, 160 - pounce * 8),
                (122, 164 - pounce * 6), (164 + lunge * 0.3, 190), (204 + lunge * 0.5, 206),
                (214 + lunge * 0.6, 228), (198 + lunge * 0.6, 246), (150, 248), (100, 246),
                (60 + wiggle, 238), (42 + wiggle, 214)]
        self._fur_mass(body, 130, 206, inner=0.88, lift=3,
                       highlight=[(70 + wiggle, 170 - pounce * 7), (120, 166 - pounce * 6),
                                  (170, 190)])
        # chest bib under the throat
        self._poly([(176 + lunge * 0.4, 206), (206 + lunge * 0.5, 214), (210 + lunge * 0.6, 236),
                    (192 + lunge * 0.5, 246), (170, 240), (164, 220)],
                   self.WHITE, self.WHITE_SHADE, 1, smooth=True)
        # front legs: tucked, or one extended towards the ball
        bx, by = ball_local
        if pounce > 0.15:
            reach = pounce
            tx = 206 + (bx - 14 - 206) * reach
            ty = g - 2 + (min(by, g - 2) - (g - 2)) * reach
            tx = max(206, tx)
            self._leg(182, 232, 184, g - 2, 17, toes=False)
            self._tapered([(204 + lunge * 0.5, 226), ((206 + tx) / 2, (226 + ty) / 2 - 6), (tx, ty)],
                          [20, 17, 14], self.INK, self._outline, 1.2)
            self._sock(tx + 2, ty, 13, 8, toes=True)
        else:
            self._leg(182, 232, 184, g - 2, 17, toes=False)
            self._leg(206, 232, 208, g - 2, 17, toes=True)
        hx = 194 + lunge * 0.55
        hy = 196 - pounce * 4
        gaze_x = max(-6.0, min(6.0, (bx - hx) * 0.08))
        gaze_y = max(-3.0, min(5.0, (by - hy) * 0.06))
        eyes = "closed" if self._blinking(t, 1.7) else "open"
        self._head(hx, hy, t, size=0.95, tilt=math.sin(t * 3) * 2, eyes=eyes, pupil=pupil,
                   gaze=(gaze_x, gaze_y), ears="back" if pounce > 0.5 else "up")

    def _stretch(self, t, pupil):
        g = self.GROUND
        reach = math.sin(t * 4) * 3
        sw = math.sin(t * 1.5) * 5
        sw2 = math.sin(t * 1.5 - 1.0) * 8
        # hind legs upright at the rear
        self._leg(92, 200, 93, g - 2, 16, far=True, toes=False)
        self._tail([(60, 186), (40, 160), (34, 130), (42, 104 + sw), (58, 92 + sw2)],
                   [13, 12, 10, 8, 5])
        body = [(56, 172), (90, 152), (130, 158), (166, 182), (190, 206), (196, 232),
                (180, 246), (130, 244), (84, 236), (50, 214)]
        self._fur_mass(body, 125, 200, inner=0.88, lift=3,
                       highlight=[(74, 164), (120, 160), (164, 182)])
        self._leg(72, 204, 72, g - 2, 17)
        # front legs stretched along the floor
        self._tapered([(176, 232), (204 + reach * 0.5, 246), (226 + reach, 254)],
                      [20, 16, 13], self._belly, self._outline, 1.2)
        self._sock(231 + reach, g - 4, 13, 7, toes=False)
        self._tapered([(184, 236), (208 + reach * 0.5, 250), (233 + reach, 258)],
                      [20, 16, 13], self.INK, self._outline, 1.2)
        self._sock(237 + reach, g, 14, 8)
        self._poly([(172, 212), (198, 220), (204, 240), (186, 248), (168, 240), (164, 226)],
                   self.WHITE, self.WHITE_SHADE, 1, smooth=True)
        self._head(196, 214, t, size=0.95, tilt=6, eyes="squeezed", pupil=pupil,
                   mouth="yawn" if (t % 6) < 1.8 else "closed", ears="back",
                   open_amount=6 + 4 * math.sin(t * 5))

    def _hiss(self, t, pupil):
        g = self.GROUND
        shake = math.sin(t * 30) * 0.8
        # legs stiff
        self._leg(94, 222, 94, g - 3, 15, far=True, toes=False)
        self._leg(176, 222, 176, g - 3, 15, far=True, toes=False)
        # puffed tail straight up
        puff = [(70, 208), (58, 182), (50, 150), (48, 120), (52, 96)]
        self._tail(puff, [16, 20, 22, 20, 14], outline_w=1.6, puffed=True)
        zig = []
        for i, (x, y) in enumerate(self._tapered_outline(puff, [16, 20, 22, 20, 14])):
            zig.append((x + (3 if i % 2 else -2), y + (2 if i % 2 else -1)))
        self._line(zig, self._outline, 1.2, smooth=False)
        body = [(66, 202), (80, 162), (110, 138), (140, 134), (170, 148), (190, 174),
                (196, 202), (186, 224), (150, 234), (110, 234), (78, 226)]
        body = [(x + shake, y) for x, y in body]
        self._fur_mass(body, 132, 190, inner=0.88, lift=3)
        # raised hackles along the back
        back = [(80, 160), (96, 146), (112, 138), (128, 134), (144, 134), (160, 140),
                (176, 152)]
        self._line([(x + (3 if i % 2 else -3), y - (6 if i % 2 else 1)) for i, (x, y) in
                    enumerate(back)], self._outline, 1.4, smooth=False)
        self._leg(84, 224, 84, g - 2, 17)
        self._leg(190, 224, 190, g - 2, 17)
        self._poly([(176, 196), (202, 206), (204, 226), (188, 236), (168, 230), (164, 212)],
                   self.WHITE, self.WHITE_SHADE, 1, smooth=True)
        self._head(184 + shake, 184, t, size=0.95, tilt=4, eyes="open", pupil=pupil,
                   gaze=(3.0, -1.0), mouth="hiss", ears="flat", twitch=False)

    def _sleep(self, t, state, pupil):
        g = self.GROUND
        breath = math.sin(t * 2 * math.pi / 3.2)
        grow = 1 + 0.022 * breath
        body = [(60, 188), (100, 172), (150, 170), (196, 180), (216, 210), (206, 246),
                (170, g), (110, g), (64, 252), (42, 224)]
        body = [(130 + (x - 130) * (1 + 0.008 * breath), g - (g - y) * grow) for x, y in body]
        # tail wraps around the front
        flick = 0.0
        phase = t % 8.0
        if phase < 0.5:
            flick = math.sin(phase / 0.5 * math.pi) * 6
        self._tail([(202, 238), (188, 258), (160, 268), (130, 270), (104, 268 - flick * 0.5),
                    (84, 262 - flick)], [13, 12, 10, 8, 6, 4])
        self._fur_mass(body, 130, 216, inner=0.86, lift=4,
                       highlight=[(92, 182 - 2 * breath), (150, 176 - 2 * breath),
                                  (196, 192 - 2 * breath)])
        self._poly([(118, 206), (150, 200), (170, 214), (166, 238), (146, 250), (122, 246),
                    (110, 228)], self.WHITE, self.WHITE_SHADE, 1, smooth=True)
        # paws under the chin
        self._sock(100, g - 2, 14, 7)
        self._sock(124, g - 1, 14, 7, toes=False)
        waking = state in ("stretch", "yawn")
        hy = 222 - breath * 1.2
        if waking:
            self._head(92, 214, t, size=0.92, tilt=-8, eyes="squeezed", pupil=pupil,
                       mouth="yawn", ears="droop", open_amount=10 + 6 * math.sin(t * 2.5))
        else:
            self._head(88, hy, t, size=0.92, tilt=-18, eyes="closed", pupil=pupil,
                       mouth="closed", ears="droop", twitch=True)
            # soft drifting z's
            for i in range(3):
                p = (t * 0.33 + i * 0.34) % 1.0
                if p > 0.92:
                    continue
                zx = 150 + 26 * p + 6 * math.sin(p * 7 + i)
                zy = 168 - 62 * p
                size = max(5, int((7 + 9 * p) * self.scale))
                color = blend(self.WHITE, self.FUR_EDGE, p * 0.85)
                self._text(zx, zy, "z", fill=color, font=("Segoe UI", size, "bold"))

    def _roll(self, t, pupil):
        """A compact reclined pose with the tuxedo bib and socks in view."""
        g = self.GROUND
        rock = math.sin(t * 3.6) * 2.5
        self._tail([(62, 221), (43, 211), (38, 194), (49, 182), (65, 187),
                    (72, 201), (64, 209)], [12, 11, 9, 8, 7, 5, 3])
        self._oval(52, 180 + rock, 210, 250 + rock, self.INK, self._outline, 1.4)
        self._oval(62, 187 + rock, 202, 242 + rock, self.FUR, "", 1)
        self._line([(87, 194 + rock), (132, 187 + rock), (178, 201 + rock)], self.FUR_LIGHT, 3)
        # Broad white chest patch gives this pose the same tuxedo markings.
        self._poly([(143, 187 + rock), (178, 189 + rock), (198, 211 + rock),
                    (188, 233 + rock), (160, 239 + rock), (139, 220 + rock)],
                   self.WHITE, self.WHITE_SHADE, 1, smooth=True)
        # Two relaxed forepaws and the near hind paw show their white socks.
        self._tapered([(152, 216 + rock), (187, 226 + rock), (206, 232 + rock)],
                      [17, 14, 12], self.INK, self._outline, 1.1)
        self._sock(207, 233 + rock, 13, 8, toes=True)
        self._tapered([(136, 222 + rock), (164, 238 + rock), (181, 245 + rock)],
                      [15, 13, 11], self._belly, self._outline, 1.0)
        self._sock(182, 245 + rock, 12, 7, toes=False)
        self._sock(78, 239 + rock, 13, 7, toes=False)
        self._sock(96, 246 + rock, 13, 7, toes=True)
        self._head(177, 178 + rock, t, size=0.87, tilt=18 + rock * 1.4,
                   eyes="closed" if self._blinking(t, 0.7) else "open",
                   pupil=pupil, gaze=(-2, 2), ears="droop", mouth="closed")

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
        self._oval(x - shadow_r, g - 2, x + shadow_r, g + 3, self.INK, "", 1, stipple="gray50")
        self._oval(x - 12, y - 12, x + 12, y + 12, self.BALL, self.BALL_DARK, 1.4)
        try:
            vx = float(getattr(brain, "ball_vx", getattr(brain, "_ball_vx", 60.0)))
        except (TypeError, ValueError):
            vx = 60.0
        angle = (float(getattr(brain, "ball_x", 0.0) or 0.0) / 18.0) * (1 if vx >= 0 else 1)
        seam = []
        for k in range(5):
            a = angle + k * 0.5 - 1.0
            seam.append((x + math.cos(a) * 9, y + math.sin(a) * 9))
        self._line(seam, self.BALL_DARK, 1.5)
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

    # -- popcorn tub (video reaction) -----------------------------------------
    def _kernel(self, x, y, r=4):
        self._oval(x - r, y - r, x + r, y + r, self.CORN_KERNEL, "#ddc887", 1)

    def _popcorn_lap(self, t):
        """Striped tub held in front of a sitting cat, both paws on the rim."""
        self._poly([(98, 218), (140, 218), (135, 258), (103, 258)],
                   self.CORN_BUCKET, "#9c5247", 1.4)
        for x in (108, 119, 130):
            self._line([(x, 222), (x, 254)], self.CORN_STRIPE, 3)
        for x, y in ((100, 217), (108, 212), (117, 215), (126, 211), (135, 215), (141, 218),
                     (113, 209), (122, 207)):
            self._kernel(x, y)
        # popping kernel
        p = (t * 1.3) % 1.0
        self._kernel(120 + 14 * math.sin(p * 5), 208 - 38 * math.sin(p * math.pi), 3.5)
        # paws on the rim
        self._sock(102, 220, 11, 7, toes=False)
        self._sock(138, 220, 11, 7, toes=False)

    def _popcorn_side(self):
        self._poly([(184, 208), (225, 208), (219, 253), (190, 253)],
                   self.CORN_BUCKET, "#9c5247")
        for x in (194, 205, 216):
            self._line([(x, 212), (x, 248)], self.CORN_STRIPE, width=3)
        for x, y in ((191, 207), (200, 202), (209, 206), (218, 202), (224, 208)):
            self._kernel(x, y)

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
        """Render one frame from a brain with state, elapsed and facing fields.

        ``message`` is accepted for backward compatibility but no longer drawn
        inside the cat canvas (use bubble.SpeechBubble); pass ``draw_bubble=True``
        to get the old in-canvas text."""
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
                dt, (196.0, 244.0), vel_xy=(vx, vy), facing=facing,
                wag_phase=t * (7.0 if state == "play" else 1.5),
                wag_amp=0.25 if state == "play" else 0.12,
            )
            self.tail_spring.points = pts_spring

        self.flip = facing < 0
        ball = None
        if state == "play":
            ball = self._ball_logical(brain)
            self.flip = ball[0] < 128
            ball_local = (260 - ball[0], ball[1]) if self.flip else ball

        if state not in ("sleep", "play", "hiss") and not getattr(brain, "paused", False):
            self.idle_sway = math.sin(t * 0.15) * 0.8
            self.dx += self.idle_sway

        reaction = getattr(brain, "activity_reaction", "none")
        self._dance_tilt = wobble_tilt
        if reaction == "music" and state not in ("sleep", "play", "hiss") and not getattr(brain, "paused", False):
            self._dance_tilt += math.sin(t * 2.5) * 7
        if reaction == "music" and state not in ("sleep", "play", "hiss") and not getattr(brain, "paused", False):
            self.dx += math.sin(t * 5.0) * 7
            self.dy += abs(math.sin(t * 5.0)) * -5
        if state == "sleep":
            self._sleep(t, state, pupil)
        elif state == "roll":
            self._roll(t, pupil)
        elif state == "stretch":
            self._stretch(t, pupil)
        elif state in ("wander", "follow"):
            self._walk(t, state, pupil, speed=9.0 if state == "follow" else 8.0,
                       ground_speed=self._measure_ground_speed(brain, t))
        elif state == "play":
            self._play(t, brain, pupil, ball_local)
        elif state == "hiss":
            self._hiss(t, pupil)
        else:
            self._sit(t, state, brain, pupil)

        cat_flip = self.flip
        self.dx = self.dy = 0.0
        self.flip = False
        self._dance_tilt = 0.0
        if reaction == "video" and state not in ("sleep", "play", "hiss"):
            if state in ("wander", "follow", "stretch", "roll"):
                self._popcorn_side()
            else:
                self.flip = cat_flip
                self._popcorn_lap(t)
                self.flip = False
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

    def _draw_paw_dot(self, x, y, stipple):
        s = self.scale
        r_pad = 4.2 * s
        self.canvas.create_oval(
            x - r_pad, y - r_pad * 0.8, x + r_pad, y + r_pad * 0.8,
            fill="#52606d", outline="", stipple=stipple, tags=self.TAG,
        )
        rt = 1.9 * s
        for ox, oy in ((-4.2, -5.5), (0.0, -6.8), (4.2, -5.5)):
            tx, ty = x + ox * s, y + oy * s
            self.canvas.create_oval(
                tx - rt, ty - rt, tx + rt, ty + rt,
                fill="#52606d", outline="", stipple=stipple, tags=self.TAG,
            )
        self.item_count += 4

    def _draw_world_overlays(self, brain, t):
        """Draw live paw trails, desktop props (box/bed/laser), and task fishes."""
        bx = float(getattr(brain, "x", 0.0) or 0.0)
        by = float(getattr(brain, "y", 0.0) or 0.0)

        paw_trails = getattr(brain, "paw_trails", None)
        if paw_trails:
            if isinstance(paw_trails, PawPrintTrail) or hasattr(paw_trails, "prints"):
                for p in paw_trails.prints:
                    life = 1.0 - max(0.0, min(1.0, p.age / max(0.001, p.ttl)))
                    stipple = (
                        "gray75" if life > 0.72 else "gray50" if life > 0.45
                        else "gray25" if life > 0.2 else "gray12"
                    )
                    self._draw_paw_dot(p.x - bx, p.y - by, stipple)
            else:
                for pt in paw_trails:
                    if isinstance(pt, dict):
                        px, py = float(pt.get("x", 0.0)) - bx, float(pt.get("y", 0.0)) - by
                        alpha = float(pt.get("alpha", 1.0))
                    else:
                        px, py = float(getattr(pt, "x", 0.0)) - bx, float(getattr(pt, "y", 0.0)) - by
                        alpha = float(getattr(pt, "alpha", 1.0))
                    stipple = (
                        "gray75" if alpha > 0.72 else "gray50" if alpha > 0.45
                        else "gray25" if alpha > 0.2 else "gray12"
                    )
                    self._draw_paw_dot(px, py, stipple)

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
