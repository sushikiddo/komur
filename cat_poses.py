"""Dedicated realistic plush vector activity animations for CatRenderer (260x280 logical space).

Each pose draws in logical coordinates facing +x (mirrored automatically by
``renderer.flip`` through ``renderer._xy``), derives all fur/eye/skin colors
from the active ``CatRenderer`` palette so all 7 skins recolor organically, and
avoids near-black chroma-key colors (< 12/255) and ``stipple=`` for macOS Tk.
"""
from __future__ import annotations

import math


def _blend(c1: str, c2: str, f: float) -> str:
    f = max(0.0, min(1.0, f))
    a = tuple(int(c1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    b = tuple(int(c2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(3))


# ---------------------------------------------------------------------------
# Shared warm prop palettes (all safely above macOS near-black key ramp)
# ---------------------------------------------------------------------------
_MILK_WHITE = "#fffaf0"
_MILK_RIPPLE = "#d7e6f2"
_MILK_EDGE = "#bdd2e4"

_KIBBLE_MAIN = "#b06e32"
_KIBBLE_LIGHT = "#d49450"
_KIBBLE_DARK = "#7a471b"

_SISAL_DUST = ("#d8b882", "#c4a068", "#ebd2a4", "#b28c54")

_BOX_BACK_DARK = "#6f4b25"
_BOX_BACK_SHADE = "#5b3b1a"
_BOX_FRONT = "#c49658"
_BOX_FRONT_SHADE = "#b48549"
_BOX_FLAP = "#d6aa6c"
_BOX_FLAP_SHADE = "#b08245"
_BOX_RIM = "#ddb477"
_BOX_OUTLINE = "#7d5528"
_BOX_SEAM = "#9a6f3b"
_BOX_TAPE = "#e6d1a4"
_BOX_TAPE_EDGE = "#c7ae7c"
_BOX_STAMP = "#68441e"


def _draw_claws(r, x: float, y: float, spread_dx: float = 8.5, spread_dy: float = 4.2):
    """Draw 3 delicate curved white feline claw tips extending from a paw."""
    for oy in (-spread_dy, 0.0, spread_dy):
        tip_x = x + spread_dx + (1.4 if oy == 0.0 else 0.0)
        tip_y = y + oy * 1.1 + 1.2
        r._poly(
            [(x, y + oy - 1.1), (tip_x, tip_y), (x + 1.0, y + oy + 1.1)],
            r.WHITE,
            r.WHITE_SHADE,
            0.7,
            smooth=False,
        )


# ---------------------------------------------------------------------------
# 1. Drink (milk lapping)
# ---------------------------------------------------------------------------
def draw_drink(r, t: float, pupil: float):
    """Plush crouched Kömür lapping milk with full-volume haunch, 3/4 head & gentle ripples."""
    g = r.GROUND
    breath = math.sin(t * 2.4) * 1.1
    lap_wave = math.sin(t * 13.0)
    tongue_out = 0.25 + 0.75 * max(0.0, lap_wave)
    head_bob = max(0.0, lap_wave) * 2.6
    sw = math.sin(t * 1.6) * 5.0
    sw2 = math.sin(t * 1.6 - 0.9) * 8.5

    # Far tucked hind paw + thick plush swaying tail
    r._sock(74, g - 2.5, 11.5, 5.8, toes=False)
    r._tail(
        [(54, 210), (34, 194), (26, 168), (38, 146 + sw), (56, 136 + sw2)],
        [14.5, 13.8, 12.2, 10.6, 8.6],
    )

    # Cozy plush crouched drinking torso
    body = [
        (48, 190 - breath), (80, 164 - breath), (120, 170 - breath * 0.7),
        (160, 188), (186, 208), (188, 234),
        (164, 248), (122, 246), (80, 244), (48, 222),
    ]
    r._fur_mass(
        body, 118, 208, inner=0.86, lift=3.0,
        highlight=[(74, 174 - breath), (118, 176 - breath * 0.6), (160, 196)],
    )
    # Plush folded muscular near hind haunch & hock
    r._curved_limb(
        [(78, 204), (60, 226), (76, 248), (94, g - 2.5)],
        [24.5, 18.2, 13.2, 10.6],
        sock=True, sock_start=0.80, toes=True, forward=1.0,
    )
    # Wide fluffy white chest bib
    r._bib(
        [(150, 204), (180, 214), (184, 236), (166, 246), (146, 238), (144, 220)],
        tufts=4,
    )

    # Plush front legs bracing naturally near the milk
    r._curved_limb(
        [(164, 218), (160, 238), (166, g - 3.5)],
        [18.0, 14.2, 11.0],
        sock=True, sock_start=0.76, far=True, toes=False, forward=1.0,
    )
    r._curved_limb(
        [(148, 216), (144, 238), (150, g - 2.5)],
        [19.5, 15.2, 11.8],
        sock=True, sock_start=0.76, toes=True, forward=1.0,
    )

    # Milk surface & concentric ripples right below muzzle
    mx, my = 216.0, 256.5
    for idx in range(2):
        phase = (t * 2.0 + idx * 0.5) % 1.0
        rx = 6.5 + phase * 15.0
        ry = 1.8 + phase * 3.4
        ring_col = _blend(_MILK_WHITE, _MILK_EDGE, phase * 0.72)
        r._oval(mx - rx, my - ry, mx + rx, my + ry, "", ring_col, 1.2 - phase * 0.5)
    r._oval(mx - 10.5, my - 2.4, mx + 10.5, my + 2.4, _MILK_RIPPLE, _MILK_WHITE, 0.9)

    # Adorable 3/4-profile dipped head with blissful eyes & rhythmic lapping pink tongue
    hx = 186.0 + tongue_out * 2.0
    hy = 212.0 + head_bob
    eyes = "happy" if (t % 3.8) < 2.5 else "open"
    r._head(
        hx, hy, t, size=0.84, tilt=22.0 + head_bob * 1.0,
        eyes=eyes, pupil=pupil, gaze=(4.0, 3.0), lid=0.58,
        mouth="lap", ears="relaxed", tongue_out=tongue_out, profile=0.64,
    )

    # Tiny milk droplet sparkles popping near the tongue
    for i, (ox, vx, h_max) in enumerate(((-5.0, -5.5, 10.0), (4.0, 5.0, 13.0))):
        p = (t * 2.5 + i * 0.45) % 1.0
        if p < 0.72:
            u = p / 0.72
            dx = mx + ox + vx * u
            dy = my - 3.5 - math.sin(u * math.pi) * h_max
            dr = max(1.1, 2.0 * (1.0 - 0.45 * u))
            r._oval(dx - dr, dy - dr, dx + dr, dy + dr, _MILK_WHITE, _MILK_EDGE, 0.6)


# ---------------------------------------------------------------------------
# 2. Eat (kibble munching)
# ---------------------------------------------------------------------------
def draw_eat(r, t: float, pupil: float):
    """Plush crouched Kömür eating with rhythmic chewing & subtle kibble crumbs."""
    g = r.GROUND
    chomp_wave = math.sin(t * 8.5)
    chomp = 0.5 + 0.5 * chomp_wave
    bob = chomp_wave * 3.6
    sw = math.sin(t * 2.6) * 4.5
    sw2 = math.sin(t * 2.6 - 0.9) * 8.0

    r._sock(74, g - 2.5, 11.5, 5.8, toes=False)
    r._tail(
        [(52, 208), (34, 188), (28, 162), (42, 140 + sw), (60, 132 + sw2)],
        [14.5, 13.8, 12.2, 10.6, 8.6],
    )

    body = [
        (48, 186), (82, 162), (124, 166), (164, 184),
        (188, 204), (190, 232), (166, 246), (122, 244),
        (80, 242), (48, 220),
    ]
    r._fur_mass(
        body, 118, 204, inner=0.86, lift=3.0,
        highlight=[(74, 170), (122, 172), (164, 192)],
    )
    r._curved_limb(
        [(78, 202), (60, 224), (76, 246), (94, g - 2.5)],
        [24.5, 18.2, 13.2, 10.6],
        sock=True, sock_start=0.80, toes=True, forward=1.0,
    )
    r._bib(
        [(152, 200), (182, 210), (186, 234), (168, 244), (146, 236), (144, 218)],
        tufts=4,
    )

    r._curved_limb(
        [(166, 216), (162, 238), (168, g - 3.5)],
        [18.0, 14.2, 11.0],
        sock=True, sock_start=0.76, far=True, toes=False, forward=1.0,
    )
    r._curved_limb(
        [(150, 214), (146, 238), (152, g - 2.5)],
        [19.5, 15.2, 11.8],
        sock=True, sock_start=0.76, toes=True, forward=1.0,
    )

    hx = 186.0 + chomp * 2.0
    hy = 204.0 + bob
    r._head(
        hx, hy, t, size=0.84, tilt=15.0 + bob * 0.9,
        eyes="happy", pupil=pupil, gaze=(3.8, 2.8),
        mouth="munch", ears="relaxed", chomp=chomp, profile=0.64,
    )

    cx0, cy0 = 216.0, 242.0
    for i, (vx, vy, col) in enumerate((
        (11.0, 12.0, _KIBBLE_MAIN),
        (17.0, 9.0, _KIBBLE_LIGHT),
        (6.0, 14.0, _KIBBLE_DARK),
    )):
        p = (t * 1.9 + i * 0.34) % 1.0
        if p < 0.70:
            u = p / 0.70
            kx = cx0 + vx * u
            ky = cy0 - math.sin(u * math.pi) * vy + u * 8.0
            kr = 2.1 - u * 0.7
            r._oval(kx - kr, ky - kr, kx + kr, ky + kr, col, _KIBBLE_DARK, 0.6)


# ---------------------------------------------------------------------------
# 3. Scratch (standing upright raking with extended claws & plush hind legs)
# ---------------------------------------------------------------------------
def draw_scratch(r, t: float, pupil: float):
    """Plush upright feline stretching-scratch with full-volume hind legs & curved raking arms."""
    g = r.GROUND
    rake = math.sin(t * 13.0)
    body_jolt = math.sin(t * 13.0) * 1.4
    sw = math.sin(t * 3.0) * 5.5
    sw2 = math.sin(t * 3.0 - 0.8) * 9.0

    # Thick plush balance tail swept gracefully behind
    r._tail(
        [(68, 220), (42, 218), (24, 200), (22, 176 + sw), (36, 156 + sw2)],
        [14.5, 13.8, 12.2, 10.6, 8.6],
        use_springs=False,
    )

    # Far plush hind leg: muscular thigh -> knee -> hock -> planted white paw
    r._curved_limb(
        [(100, 194), (112, 218), (98, 240), (104, g - 3.5)],
        [23.5, 17.8, 13.0, 10.6],
        sock=True, sock_start=0.78, far=True, toes=False, forward=1.0,
    )

    # Far plush front arm reaching high & raking
    far_paw_x = 200.0 + math.cos(t * 13.0) * 3.5
    far_paw_y = 156.0 - rake * 22.0
    r._curved_limb(
        [(148, 150 + body_jolt), (174, 152 - rake * 9.0), (far_paw_x, far_paw_y)],
        [18.5, 14.6, 11.2],
        sock=True, sock_start=0.76, far=True, toes=False, forward=1.0,
        paw_offset=(2.0, 0.0),
    )
    _draw_claws(r, far_paw_x + 9.5, far_paw_y - 0.5, spread_dx=8.0, spread_dy=3.8)

    # Plush upright stretched feline torso
    torso = [
        (62, 212), (76, 178), (98, 146), (126, 124 + body_jolt),
        (156, 132 + body_jolt), (168, 162), (150, 198),
        (124, 228), (92, 238), (66, 232),
    ]
    r._fur_mass(
        torso, 116, 182, inner=0.86, lift=3.0,
        highlight=[(80, 182), (106, 152), (132, 134 + body_jolt)],
    )
    r._bib(
        [
            (128, 136 + body_jolt), (154, 144 + body_jolt), (162, 174),
            (148, 206), (126, 214), (116, 188), (120, 156),
        ],
        tufts=4,
    )

    # Near plush muscular hind leg
    r._curved_limb(
        [(84, 196), (96, 220), (80, 242), (86, g - 2.5)],
        [25.5, 19.0, 13.8, 11.2],
        sock=True, sock_start=0.78, toes=True, forward=1.0,
    )

    # Near plush front arm alternating in opposite phase
    near_paw_x = 194.0 - math.cos(t * 13.0) * 3.5
    near_paw_y = 178.0 + rake * 22.0
    r._curved_limb(
        [(136, 158 + body_jolt), (166, 166 + rake * 9.0), (near_paw_x, near_paw_y)],
        [19.5, 15.6, 11.8],
        sock=True, sock_start=0.76, toes=True, show_beans=True, forward=1.0,
        paw_offset=(2.0, 0.0),
    )
    _draw_claws(r, near_paw_x + 10.0, near_paw_y - 0.5, spread_dx=8.8, spread_dy=4.2)

    # Alert 3/4-profile Kömür head with luminous eyes watching the raking paws
    lid = r._blink_amount(t, offset=1.1, allow_slow=False)
    r._head(
        146.0, 108.0 + body_jolt, t, size=0.84, tilt=-10.0,
        eyes="open", pupil=max(pupil, 0.54), gaze=(4.5, -1.5), lid=lid,
        ears="forward", profile=0.58,
    )

    # Subtle sisal scratch accents & fine dust flecks
    swipe_y = 166.0 + rake * 12.0
    for idx, ox in enumerate((-3.0, 2.5)):
        r._line(
            [(214 + ox, swipe_y - 12 + idx * 3), (218 + ox, swipe_y), (215 + ox, swipe_y + 13 + idx * 2)],
            r.WHITE_SHADE,
            1.1,
        )
    for i in range(4):
        p = (t * 2.4 + i * 0.25) % 1.0
        dx = 212.0 + (i % 3) * 5.0 + p * 16.0
        dy = 152.0 + i * 13.0 + p * 24.0 - math.sin(p * math.pi) * 8.0
        dr = max(1.1, 2.1 * (1.0 - p * 0.55))
        r._oval(dx - dr, dy - dr, dx + dr, dy + dr, _SISAL_DUST[i], "", 1)


# ---------------------------------------------------------------------------
# 4. Box Sit (adorable plush Kömür genuinely tucked INSIDE a cardboard box)
# ---------------------------------------------------------------------------
def draw_box_sit(r, t: float, brain, pupil: float):
    """Layered corrugated cardboard box with plush Kömür tucked inside & paws over rim."""
    elapsed = float(getattr(brain, "elapsed", t) or t)
    napping = bool(getattr(brain, "box_napping", False)) or ((elapsed % 12.0) >= 7.0)
    breath = math.sin(t * 2.0) * 1.3
    sw = math.sin(t * 1.6) * 5.0

    # --- Layer 1: Back open flaps & shadowed interior cavity ---
    r._poly(
        [(56, 172), (70, 138), (190, 138), (204, 172)],
        _BOX_FLAP_SHADE, _BOX_OUTLINE, 1.2, smooth=False,
    )
    r._poly(
        [(54, 174), (32, 154), (45, 145), (62, 168)],
        _BOX_FLAP, _BOX_OUTLINE, 1.1, smooth=False,
    )
    r._poly(
        [(206, 174), (228, 154), (215, 145), (198, 168)],
        _BOX_FLAP, _BOX_OUTLINE, 1.1, smooth=False,
    )
    r._poly(
        [(56, 172), (204, 172), (200, 250), (60, 250)],
        _BOX_BACK_DARK, _BOX_OUTLINE, 1.1, smooth=False,
    )
    r._line([(68, 174), (72, 246)], _BOX_BACK_SHADE, 1.3, smooth=False)
    r._line([(192, 174), (188, 246)], _BOX_BACK_SHADE, 1.3, smooth=False)

    # --- Layer 2: Plush Kömür tucked naturally inside the cavity ---
    if not napping:
        # Thick plush black tail tip peeking playfully over right edge
        r._tail(
            [(176, 192), (195, 170), (208, 152 + sw * 0.5), (202, 136 + sw)],
            [13.0, 12.0, 10.6, 8.2],
            use_springs=False,
        )
        shoulders = [
            (80, 198), (94, 156 - breath), (130, 150 - breath),
            (166, 156 - breath), (180, 198), (174, 224), (86, 224),
        ]
        r._fur_mass(shoulders, 130, 186, inner=0.86, lift=2.8)
        r._bib([(104, 154), (156, 154), (160, 186), (100, 186)], tufts=4)

        # Photo-faithful plush round black front-facing head peeking over the cardboard lip!
        hx = 130.0 + math.sin(t * 0.85) * 4.5
        hy = 128.0 - breath + math.sin(t * 1.5) * 1.8
        tilt = math.sin(t * 0.7) * 5.0
        gaze = (math.sin(t * 0.8) * 4.2, math.cos(t * 0.55) * 1.4)
        lid = r._blink_amount(t, offset=0.4, allow_slow=True)
        r._head(
            hx, hy, t, size=0.88, tilt=tilt,
            eyes="open", pupil=pupil, gaze=gaze, lid=lid, ears="up", profile=0.0,
        )
    else:
        shoulders = [
            (78, 204), (94, 170 - breath), (130, 164 - breath),
            (166, 170 - breath), (182, 204), (176, 226), (84, 226),
        ]
        r._fur_mass(shoulders, 130, 194, inner=0.86, lift=2.6)
        r._head(
            128.0, 158.0 - breath * 0.9, t, size=0.86, tilt=-8.0,
            eyes="closed", pupil=pupil, ears="droop", mouth="closed", profile=0.0,
        )

    # --- Layer 3: Front corrugated cardboard wall ---
    r._poly(
        [(54, 174), (206, 174), (202, 258), (58, 258)],
        _BOX_FRONT, _BOX_OUTLINE, 1.35, smooth=False,
    )
    r._poly(
        [(57, 242), (203, 242), (202, 258), (58, 258)],
        _BOX_FRONT_SHADE, "", 1, smooth=False,
    )
    r._line([(64, 186), (66, 252)], _BOX_SEAM, 1.1, smooth=False)
    r._line([(196, 186), (194, 252)], _BOX_SEAM, 1.1, smooth=False)
    r._line([(59, 248), (201, 248)], _BOX_SEAM, 1.1, smooth=False)

    r._poly(
        [(113, 176), (147, 176), (146, 194), (114, 194)],
        _BOX_TAPE, _BOX_TAPE_EDGE, 0.85, smooth=False,
    )
    r._poly(
        [(52, 171), (208, 171), (206, 180), (54, 180)],
        _BOX_RIM, _BOX_OUTLINE, 1.1, smooth=False,
    )

    font_size = max(7, int(12.5 * r.scale))
    r._text(130.0, 220.0, "KÖMÜR", fill=_BOX_STAMP, font=("Segoe UI", font_size, "bold"))
    r._line([(96, 231), (164, 231)], _BOX_STAMP, 1.2, smooth=False)

    # --- Layer 4: Plush white-tipped paws hooked gracefully over the front rim ---
    if not napping:
        for side, px in ((-1, 95.0), (1, 165.0)):
            r._curved_limb(
                [(px - side * 4.0, 165.0), (px, 172.0), (px + side * 1.5, 180.5)],
                [15.8, 13.0, 10.6],
                sock=True, sock_start=0.58, toes=True, forward=float(side),
                paw_rx=11.0, paw_ry=6.4, paw_offset=(0.0, 0.8),
            )
    else:
        r._curved_limb(
            [(100.0, 168.0), (103.0, 174.0), (105.0, 179.0)],
            [14.5, 12.0, 10.0],
            sock=True, sock_start=0.55, toes=False, forward=1.0,
            paw_rx=10.5, paw_ry=5.8, paw_offset=(0.0, 0.5),
        )


# ---------------------------------------------------------------------------
# 5. Perch (plush loafing on window ledge, thick tail dangling down below)
# ---------------------------------------------------------------------------
def draw_perch(r, t: float, pupil: float):
    """Plush Kömür loafing comfortably on a ledge (GROUND-6) with dangling fluffy tail."""
    ledge = r.GROUND - 6.0  # 256.0
    breath = math.sin(t * 1.9) * 1.4
    sw1 = math.sin(t * 1.35) * 8.0
    sw2 = math.sin(t * 1.35 - 0.85) * 14.5

    # Thick plush tail hanging lazily DOWN below the ledge (within y <= 275)
    tail_pts = [
        (78.0, ledge - 18.0),
        (58.0, ledge - 5.0),
        (52.0 + sw1 * 0.4, ledge + 5.0),
        (52.0 + sw1, ledge + 12.5),
        (56.0 + sw2, min(275.0, ledge + 19.0)),
    ]
    r._tail(tail_pts, [14.5, 13.5, 12.0, 10.4, 8.6], use_springs=False)

    # Cozy plush feline loaf body resting solidly on ledge
    body = [
        (68, ledge - 28), (92, ledge - 72 - breath), (140, ledge - 76 - breath),
        (180, ledge - 58 - breath), (198, ledge - 26), (192, ledge),
        (148, ledge + 1), (100, ledge + 1), (70, ledge - 5),
    ]
    r._fur_mass(
        body, 134, ledge - 36, inner=0.86, lift=3.2,
        highlight=[(96, ledge - 62 - breath), (140, ledge - 66 - breath), (174, ledge - 50 - breath)],
    )
    # Wide fluffy white chest bib resting on ledge
    r._bib(
        [
            (150, ledge - 52), (182, ledge - 44), (192, ledge - 16),
            (174, ledge - 1), (150, ledge - 8), (144, ledge - 32),
        ],
        tufts=4,
    )

    # Dainty white front paws tucked neatly over the ledge edge
    r._sock(162.0, ledge + 0.5, 11.5, 6.0, toes=True)
    r._sock(184.0, ledge + 2.0, 12.0, 6.4, toes=True)

    # Cute 3/4-profile curious head peering gently downward off the ledge
    hx = 172.0 + math.sin(t * 0.65) * 2.8
    hy = ledge - 84.0 - breath
    tilt = 7.0 + math.sin(t * 0.55) * 3.0
    gaze = (3.4 + math.sin(t * 0.85) * 2.0, 3.6)
    lid = r._blink_amount(t, offset=2.0, allow_slow=True)
    r._head(
        hx, hy, t, size=0.86, tilt=tilt,
        eyes="open", pupil=pupil, gaze=gaze, lid=lid, ears="up", twitch=True,
        profile=0.45,
    )


# ---------------------------------------------------------------------------
# 6. Jump (graceful mid-air plush feline leap arc)
# ---------------------------------------------------------------------------
def draw_jump(r, t: float, pupil: float):
    """Graceful mid-air parabolic leap with plush athletic body, full limbs & streaming fluffy tail."""
    arc = math.sin(t * 5.8) * 4.5
    sw = math.sin(t * 7.5) * 4.0
    sw2 = math.sin(t * 7.5 - 0.8) * 7.0

    for oy, x0, x1 in ((0.0, 18.0, 42.0), (24.0, 24.0, 48.0)):
        r._line([(x0, 146 + oy + arc), (x1, 140 + oy + arc)], r._outline, 1.0)

    # Streaming thick plush balance tail behind
    r._tail(
        [(68, 172 + arc), (44, 182 + arc), (24, 192 + arc + sw), (12, 196 + arc + sw2)],
        [14.5, 13.4, 11.6, 8.8],
        use_springs=False,
    )

    # Far plush limbs extending gracefully
    r._curved_limb(
        [(84, 174 + arc), (66, 194 + arc), (44, 212 + arc)],
        [20.5, 15.6, 11.4],
        sock=True, sock_start=0.72, far=True, toes=False, forward=-1.0,
        paw_offset=(2.0, 1.0),
    )
    r._curved_limb(
        [(176, 150 + arc), (204, 154 + arc), (228, 162 + arc)],
        [18.5, 14.6, 11.2],
        sock=True, sock_start=0.72, far=True, toes=False, forward=1.0,
        paw_offset=(2.0, 0.5),
    )

    # Plush athletic stretched body arching cleanly through the air
    body = [
        (64, 164 + arc), (102, 140 + arc), (146, 128 + arc),
        (186, 130 + arc), (200, 148 + arc), (186, 170 + arc),
        (146, 176 + arc), (102, 184 + arc), (68, 184 + arc),
    ]
    r._fur_mass(
        body, 134, 156 + arc, inner=0.86, lift=3.0,
        highlight=[(92, 146 + arc), (138, 134 + arc), (176, 136 + arc)],
    )
    r._bib(
        [
            (160, 136 + arc), (190, 142 + arc), (196, 162 + arc),
            (174, 170 + arc), (154, 162 + arc),
        ],
        tufts=4,
    )

    # Near plush limbs
    r._curved_limb(
        [(90, 176 + arc), (70, 200 + arc), (48, 222 + arc)],
        [23.0, 17.0, 12.2],
        sock=True, sock_start=0.72, toes=True, show_beans=True, forward=-1.0,
        paw_offset=(2.0, 1.0),
    )
    r._curved_limb(
        [(172, 154 + arc), (204, 162 + arc), (232, 174 + arc)],
        [20.0, 15.8, 12.0],
        sock=True, sock_start=0.72, toes=True, forward=1.0,
        paw_offset=(2.5, 0.5),
    )

    # Focused 3/4-profile Kömür head locked onto landing point
    r._head(
        196.0, 118.0 + arc, t, size=0.84, tilt=-6.0,
        eyes="open", pupil=max(pupil, 0.56), gaze=(4.5, 1.8),
        ears="forward", profile=0.68,
    )


# ---------------------------------------------------------------------------
# 7. Laser Chase (low predator stalk/gallop OR coiled hunter crouch & swat)
# ---------------------------------------------------------------------------
def draw_laser_chase(r, t: float, brain, pupil: float):
    """Plush predator hunt: realistic crouching stalk/walk when moving, coiled swat when close."""
    vx = float(getattr(brain, "vx", 0.0) or 0.0)
    vy = float(getattr(brain, "vy", 0.0) or 0.0)
    speed = math.hypot(vx, vy)

    if speed > 18.0:
        for oy in (0.0, 20.0):
            r._line([(12, 184 + oy), (34, 184 + oy)], r._outline, 1.1)
        logical_spd = max(110.0, min(140.0, speed / max(r.scale, 1e-6)))
        r._walk(
            t, "follow", 1.0, speed=15.0,
            ground_speed=logical_spd, crouch=13.0, ears="forward",
        )
        return

    g = r.GROUND
    cyc = (t * 1.45) % 1.0
    swat = math.sin((cyc - 0.62) / 0.38 * math.pi) if cyc > 0.62 else 0.0
    wiggle = math.sin(t * 16.0) * 4.0 * (1.0 - swat * 0.7)
    sw = math.sin(t * 10.5) * 5.5
    sw2 = math.sin(t * 10.5 - 1.0) * 10.0
    lunge = swat * 15.0

    r._sock(72, g - 2.0, 11.5, 5.8, toes=False)
    r._tail(
        [(50 + wiggle, 204), (32, 184), (26, 158), (40, 136 + sw), (58, 130 + sw2)],
        [14.5, 13.6, 12.0, 10.4, 8.4],
    )

    body = [
        (46 + wiggle, 188 - swat * 5), (82 + wiggle, 162 - swat * 7),
        (124, 170 - swat * 4), (166 + lunge * 0.3, 194),
        (198 + lunge * 0.5, 208), (208 + lunge * 0.6, 232),
        (192 + lunge * 0.6, 248), (144, 248), (96, 246),
        (58 + wiggle, 240), (44 + wiggle, 216),
    ]
    r._fur_mass(
        body, 126, 208, inner=0.86, lift=3.0,
        highlight=[(72 + wiggle, 172 - swat * 6), (122, 176 - swat * 4), (166, 198)],
    )
    r._curved_limb(
        [(78 + wiggle, 206), (60 + wiggle, 228), (76 + wiggle, 248), (94, g - 2.5)],
        [24.5, 18.2, 13.2, 10.8],
        sock=True, sock_start=0.80, toes=True, forward=1.0,
    )
    r._bib(
        [
            (168 + lunge * 0.4, 208), (198 + lunge * 0.5, 216),
            (204 + lunge * 0.6, 236), (186 + lunge * 0.5, 246),
            (164, 240), (160, 222),
        ],
        tufts=4,
    )

    r._curved_limb(
        [(176 + lunge * 0.3, 218), (174 + lunge * 0.3, 238), (180 + lunge * 0.3, g - 3.0)],
        [18.0, 14.4, 11.2],
        sock=True, sock_start=0.76, far=True, toes=False, forward=1.0,
    )
    if swat > 0.12:
        tx = min(240.0, 204.0 + swat * 32.0)
        ty = g - 5.0 - swat * 13.0
        r._curved_limb(
            [(192 + lunge * 0.4, 222), ((194 + tx) * 0.5, (222 + ty) * 0.5 - 7.5), (tx, ty)],
            [19.5, 15.6, 12.2],
            sock=True, sock_start=0.76, toes=True, forward=1.0,
            paw_offset=(2.0, 0.0),
        )
        _draw_claws(r, tx + 10.0, ty - 0.5, spread_dx=7.5, spread_dy=3.5)
    else:
        r._curved_limb(
            [(194, 218), (192, 238), (198, g - 2.5)],
            [19.5, 15.4, 11.8],
            sock=True, sock_start=0.76, toes=True, forward=1.0,
        )

    # Low 3/4-profile predator head with huge adorable boba-round dilated pupils (1.0)
    r._head(
        190.0 + lunge * 0.50, 196.0 - swat * 3.5, t,
        size=0.84, tilt=math.sin(t * 4.5) * 2.2,
        eyes="open", pupil=1.0, gaze=(4.5, 2.0),
        ears="forward", profile=0.65,
    )


# ---------------------------------------------------------------------------
# 8. Purr Idle (photo-faithful cozy plush purring Kömür sit)
# ---------------------------------------------------------------------------
def draw_purr_idle(r, t: float, pupil: float):
    """Contented plush purring Kömür sit with blissful curved eyes, soft chest rhythm & thick tail."""
    g = r.GROUND
    breath = math.sin(t * 2.0 * math.pi / 3.6)
    vib_x = math.sin(t * 26.0) * 0.42
    vib_y = math.cos(t * 26.0) * 0.28
    sw = math.sin(t * 1.05) * 4.0
    sw2 = math.sin(t * 1.05 - 0.9) * 7.0
    lift = breath * 1.5 - vib_y

    r._sit_body(lift=lift, vib_x=vib_x, tail_sw=(sw, sw2))

    # Plush black front legs with dainty white paws close together
    r._curved_limb(
        [(90 + vib_x * 0.4, 178 - lift * 0.4), (92 + vib_x * 0.3, 212), (98, 239), (104, g - 3.0)],
        [20.5, 16.0, 12.8, 10.6],
        sock=True, sock_start=0.78, toes=True, forward=1.0,
    )
    r._curved_limb(
        [(148 + vib_x * 0.4, 180 - lift * 0.4), (146 + vib_x * 0.3, 212), (140, 239), (134, g - 3.0)],
        [20.5, 16.0, 12.8, 10.6],
        sock=True, sock_start=0.78, toes=True, forward=-1.0,
    )

    hx = 120.0 + vib_x
    hy = 106.0 - lift
    tilt = math.sin(t * 1.1) * 4.2
    r._head(
        hx, hy, t, size=1.04, tilt=tilt, eyes="happy", pupil=pupil,
        gaze=(2.0, 0.5), mouth="closed", ears="relaxed", blush=False, profile=0.0,
    )


# ---------------------------------------------------------------------------
# 9. Peek (curiously peeking head & dainty white paws over a window edge!)
# ---------------------------------------------------------------------------
def draw_peek(r, t: float, pupil: float):
    """Adorable Kömür peeking curiously over a window edge with paws gripping the ledge."""
    g = r.GROUND
    bob = math.sin(t * 1.9) * 3.0
    tilt = math.sin(t * 1.1) * 4.2
    # Soft dark plush shoulders tucked just behind the ledge line
    r._poly(
        [(76, g + 2), (82, 232 + bob), (128, 226 + bob), (176, 232 + bob), (182, g + 2)],
        r._coat, "", 1, smooth=True,
    )
    # Fluffy snow-white tuxedo chest ruff peeking just above the ledge
    r._bib(
        [(94, 238 + bob), (164, 238 + bob), (156, g - 1), (102, g - 1)],
        tufts=3,
    )
    # Big adorable curious Kömür head peeking up over the edge!
    lid = r._blink_amount(t, allow_slow=True)
    gaze = (math.sin(t * 0.9) * 3.5, 0.8 + math.cos(t * 0.6) * 0.8)
    r._head(
        128.0, 212.0 + bob, t, size=1.05, tilt=tilt,
        eyes="open", pupil=max(pupil, 0.72), gaze=gaze, lid=lid,
        mouth="closed", ears="forward", profile=0.0,
    )
    # Two dainty snow-white paws gripping the ledge beside the chin!
    r._sock(82, g - 3.5 + bob * 0.2, 13.5, 7.2, toes=True, forward=1.0)
    r._sock(174, g - 3.5 + bob * 0.2, 13.5, 7.2, toes=True, forward=-1.0)


# ---------------------------------------------------------------------------
# 10. Notch Peek (macOS MacBook çentiğinden aşağı bakan tatlı Kömür!)
# ---------------------------------------------------------------------------
def draw_notch_peek(r, t: float, pupil: float):
    """Kömür hangs flush right below the MacBook Notch (y=0 touches the notch rim!)."""
    bob = math.sin(t * 1.8) * 1.6
    tilt = math.sin(t * 1.0) * 4.5
    sway = math.sin(t * 2.1) * 14.0
    # Playful tail emerging directly from behind the right side of the notch (y=0)
    tail = [
        (182, 0),
        (198 + sway * 0.35, 28),
        (202 + sway * 0.75, 58),
        (188 + sway, 84),
    ]
    r._tail(tail, widths=(13.5, 12.2, 10.8, 9.0))
    # Plush dark shoulders emerging seamlessly out of the black MacBook Notch (y=0)
    r._poly(
        [(84, 0), (172, 0), (168, 72 + bob), (128, 86 + bob), (88, 72 + bob)],
        r._coat, "", 1, smooth=True,
    )
    # Cozy snow-white tuxedo chest bib tucked neatly under the chin (below the head!)
    r._bib(
        [(108, 66 + bob), (148, 66 + bob), (142, 84 + bob), (114, 84 + bob)],
        tufts=3,
    )
    # Round adorable Kömür head peering right out from beneath the notch!
    lid = r._blink_amount(t, allow_slow=True)
    gaze = (math.sin(t * 0.85) * 3.8, 3.2 + math.cos(t * 0.6) * 0.8)
    r._head(
        128.0, 44.0 + bob, t, size=0.98, tilt=tilt,
        eyes="open", pupil=max(pupil, 0.74), gaze=gaze, lid=lid,
        mouth="closed", ears="forward", profile=0.0,
    )
    # Two dainty snow-white paws gripping the notch's bottom rim beside the ears!
    r._sock(74, 7.0 + bob * 0.15, 13.0, 7.0, toes=True, forward=1.0)
    r._sock(182, 7.0 + bob * 0.15, 13.0, 7.0, toes=True, forward=-1.0)
