"""Extra cute outfits & accessories for CatRenderer (drawn in head-local coordinates).

All colors stay safely above macOS's near-black chroma-key ramp (>= 12/255) and avoid
stipple patterns so macOS Tk 9.1 and Windows render identically.
"""
from __future__ import annotations

import math

EXTRA_COSTUMES = (
    "star_sticker",
    "bell_collar",
    "bandana",
    "crown",
    "flower_crown",
    "beret",
    "sunglasses",
    "angel_halo",
    "ribbon_ear",
    "cozy_sweater",
)

COSTUME_LABELS = {
    None: "Yok",
    "star_sticker": "⭐ Sarı Yıldız Sticker",
    "bell_collar": "🔔 Zilli Tasma",
    "bandana": "🧣 Bandana",
    "bow": "🎀 Papyon",
    "scarf": "🧣 Atkı",
    "cozy_sweater": "🧶 Örgü Pelerin",
    "crown": "👑 Altın Taç",
    "flower_crown": "🌸 Çiçek Tacı",
    "beret": "🎨 Ressam Beresi",
    "hat": "🎩 Şapka",
    "witch_hat": "🧙 Cadı Şapkası",
    "winter_set": "❄️ Kış Seti",
    "ribbon_ear": "🎀 Kulak Kurdelesi",
    "angel_halo": "😇 Melek Halesi",
    "glasses": "👓 Gözlük",
    "sunglasses": "🕶️ Güneş Gözlüğü",
    "headphones": "🎧 Kulaklık",
    "cyberpunk_collar": "⚡ Siber Tasma",
}

# Back-to-front draw order so multi-slot outfits layer naturally
SLOT_ORDER = ("body", "neck", "eyes", "head")
SLOT_UI_ORDER = ("head", "eyes", "neck", "body")
SLOT_LABELS = {
    "head": "👑 Kafa",
    "eyes": "👓 Göz",
    "neck": "🔔 Boyun",
    "body": "🧶 Gövde",
}
COSTUME_SLOT_MAP = {
    # head
    "star_sticker": "head",
    "crown": "head",
    "flower_crown": "head",
    "beret": "head",
    "hat": "head",
    "witch_hat": "head",
    "ribbon_ear": "head",
    "angel_halo": "head",
    "winter_set": "head",
    # eyes
    "glasses": "eyes",
    "sunglasses": "eyes",
    # neck
    "bell_collar": "neck",
    "bandana": "neck",
    "bow": "neck",
    "scarf": "neck",
    "cyberpunk_collar": "neck",
    "headphones": "neck",
    # body
    "cozy_sweater": "body",
}


def slot_for(kind: str | None) -> str | None:
    if not kind:
        return None
    return COSTUME_SLOT_MAP.get(kind, "head")


def items_in_slot(slot: str) -> list[str]:
    return [k for k in COSTUME_LABELS if k is not None and slot_for(k) == slot]


def normalize_accessories(raw) -> dict[str, str]:
    """Normalize legacy single string, iterable, or slot-dict into {slot: costume_key}."""
    if not raw:
        return {}
    if isinstance(raw, str):
        s = slot_for(raw)
        return {s: raw} if s else {}
    if isinstance(raw, dict):
        out: dict[str, str] = {}
        for slot, val in raw.items():
            if isinstance(val, str) and val:
                target = slot if slot in SLOT_ORDER else (slot_for(val) or "head")
                out[target] = val
        return out
    if isinstance(raw, (list, tuple, set)):
        out = {}
        for val in raw:
            if isinstance(val, str) and val:
                s = slot_for(val)
                if s:
                    out[s] = val
        return out
    return {}


def ordered_active_items(raw) -> list[str]:
    """Return active costume keys ordered back-to-front (body -> neck -> eyes -> head)."""
    slots = normalize_accessories(raw)
    return [slots[s] for s in SLOT_ORDER if slots.get(s)]


def toggle_slot_item(raw, kind: str | None) -> dict[str, str]:
    """Toggle a costume in its slot without disturbing other slots (returns a new dict)."""
    if kind is None:
        return {}
    slots = normalize_accessories(raw)
    s = slot_for(kind)
    if not s:
        return slots
    if slots.get(s) == kind:
        slots.pop(s, None)
    else:
        slots[s] = kind
    return slots


def summary_label(raw) -> str:
    """Short human-readable summary of active combo (e.g. '⭐ + 🔔' or 'Yok')."""
    items = ordered_active_items(raw)
    if not items:
        return "Yok"
    if len(items) == 1:
        return COSTUME_LABELS.get(items[0], items[0])
    icons = [COSTUME_LABELS.get(k, k).split(" ", 1)[0] for k in items]
    return " + ".join(icons) + f" ({len(items)})"


def _star_points(cx: float, cy: float, r_outer: float, r_inner: float, n: int = 5):
    pts = []
    for i in range(n * 2):
        ang = -math.pi * 0.5 + i * math.pi / n
        rad = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
    return pts


def draw_extra_costume(r, kind: str | None, shape, size: float = 1.0, t: float = 0.0) -> bool:
    """Draw one of the extended cute accessories/outfits. Returns True if drawn."""
    fn = _DRAWERS.get(kind)
    if fn is None:
        return False
    fn(r, shape, size, t)
    return True


def _draw_star_sticker(r, shape, size: float, _t: float):
    """Iconic real-Kömür photo smiling yellow star sticker on the forehead!"""
    cx, cy = 0.0, -21.5
    outer = _star_points(cx, cy, 11.2, 5.8)
    inner = _star_points(cx, cy, 8.6, 4.3)
    r._poly(shape(outer), "#fffdf7", "#dce2ea", 0.7, smooth=False)
    r._poly(shape(inner), "#ffe23b", "#e3a914", 0.7, smooth=False)
    # Tiny cute smiling face inside the star sticker
    for sx in (-2.0, 2.0):
        pt = shape([(cx + sx, cy - 0.6)])[0]
        r._ellipse(pt, 0.9 * size, 0.9 * size, "#2b2112", "", 1)
    r._line(shape([(cx - 2.0, cy + 1.4), (cx, cy + 2.8), (cx + 2.0, cy + 1.4)]), "#2b2112", 0.9)


def _draw_bell_collar(r, shape, size: float, t: float):
    """Classic red leather collar with shiny golden jingle bell."""
    r._poly(
        shape([(-33, 33), (-16, 42), (0, 45), (16, 42), (33, 33),
               (34, 41), (16, 50), (0, 53), (-16, 50), (-34, 41)]),
        "#c9313b", "#7a1822", 1.1, smooth=True,
    )
    r._line(shape([(-26, 39), (0, 48), (26, 39)]), "#f28482", 1.0)
    # Gold clasp ring & swinging jingle bell
    sway = math.sin(float(t) * 4.5) * 1.2
    bc = shape([(sway, 54.0)])[0]
    r._ellipse(bc, 7.2 * size, 7.0 * size, "#f4c430", "#9e6f08", 1.1)
    shine = shape([(sway - 2.2, 51.8)])[0]
    r._ellipse(shine, 2.0 * size, 1.8 * size, "#fff6cc", "", 1)
    r._line(shape([(sway - 4.4, 56.0), (sway + 4.4, 56.0)]), "#6e4704", 1.2)
    hole = shape([(sway, 56.4)])[0]
    r._ellipse(hole, 1.6 * size, 1.6 * size, "#6e4704", "", 1)


def _draw_bandana(r, shape, size: float, _t: float):
    """Cute crimson triangular neckerchief bandana with stitched white trim."""
    r._poly(
        shape([(-34, 32), (0, 44), (34, 32), (35, 41), (0, 52), (-35, 41)]),
        "#b52a37", "#6f151e", 1.0, smooth=True,
    )
    r._poly(
        shape([(-28, 39), (0, 46), (28, 39), (16, 58), (0, 72), (-16, 58)]),
        "#d63c48", "#7d1b24", 1.1, smooth=True,
    )
    r._line(shape([(-20, 44), (0, 65), (20, 44)]), "#fff5eb", 1.1)
    for dx, dy in ((-8, 49), (0, 55), (8, 49)):
        p = shape([(dx, dy)])[0]
        r._ellipse(p, 1.5 * size, 1.5 * size, "#fff5eb", "", 1)


def _draw_crown(r, shape, size: float, _t: float):
    """Cute royal golden mini-crown nestled cleanly between the ears."""
    pts = [
        (-19, -34), (-22, -52), (-10, -44), (0, -58),
        (10, -44), (22, -52), (19, -34),
    ]
    r._poly(shape(pts), "#f5c542", "#9e6f0c", 1.1, smooth=False)
    r._poly(shape([(-19, -38), (19, -38), (19, -33), (-19, -33)]), "#e0a522", "#9e6f0c", 0.9, smooth=False)
    # Pearls on tips
    for px, py in ((-22, -53), (0, -59), (22, -53)):
        r._ellipse(shape([(px, py)])[0], 2.4 * size, 2.4 * size, "#fff6d6", "#b88214", 0.8)
    # Royal gems on band
    for gx, col in ((-9, "#3a86ff"), (0, "#e63946"), (9, "#2ec4b6")):
        r._ellipse(shape([(gx, -36)])[0], 2.2 * size, 2.0 * size, col, "#fff8e8", 0.6)


def _draw_flower_crown(r, shape, size: float, _t: float):
    """Delicate spring flower wreath resting gently across the forehead."""
    # Leafy vine base
    r._line(shape([(-30, -24), (-14, -33), (0, -36), (14, -33), (30, -24)]), "#528c58", 2.6)
    for lx, ly in ((-24, -27), (-8, -34), (8, -34), (24, -27)):
        r._poly(
            shape([(lx - 5, ly + 2), (lx, ly - 4), (lx + 5, ly + 2)]),
            "#6bb06e", "#3d6e42", 0.7, smooth=True,
        )
    # Five dainty blossoms
    flowers = (
        (-25, -26, "#ffb3c6"),
        (-12, -33, "#fff6e5"),
        (0, -36, "#ff8fab"),
        (12, -33, "#d8bbff"),
        (25, -26, "#fff6e5"),
    )
    for fx, fy, petal in flowers:
        for i in range(5):
            ang = i * (2.0 * math.pi / 5.0)
            px = fx + math.cos(ang) * 3.8
            py = fy + math.sin(ang) * 3.8
            r._ellipse(shape([(px, py)])[0], 2.8 * size, 2.8 * size, petal, "", 1)
        r._ellipse(shape([(fx, fy)])[0], 2.4 * size, 2.4 * size, "#ffd166", "#d99b1e", 0.6)


def _draw_beret(r, shape, size: float, _t: float):
    """Stylish tilted Parisian artist beret."""
    # Main tilted beret dome
    dome = [
        (-26, -32), (-32, -45), (-14, -57), (10, -59),
        (30, -50), (32, -36), (18, -29), (-8, -30),
    ]
    r._poly(shape(dome), "#9e2a3b", "#5c1420", 1.1, smooth=True)
    # Soft beret top highlight
    hi = [(-16, -48), (4, -54), (22, -46), (8, -42), (-10, -42)]
    r._poly(shape(hi), "#bc3b4d", "", 1, smooth=True)
    # Classic little beret stem on top
    r._line(shape([(2, -57), (5, -63), (9, -64)]), "#5c1420", 2.4)


def _draw_sunglasses(r, shape, size: float, _t: float):
    """Sleek glossy dark sunglasses with diagonal white glare."""
    for s in (-1, 1):
        cx, cy = s * 18.6, -2.5
        lens = [
            (cx - 14.5, cy - 9.5), (cx + 14.5, cy - 9.5),
            (cx + 13.0, cy + 8.0), (cx, cy + 11.2), (cx - 13.0, cy + 8.0),
        ]
        r._poly(shape(lens), "#171c26", "#3a4354", 1.5, smooth=True)
        # Diagonal glossy reflection bar
        r._line(shape([(cx - 8.5, cy - 6.0), (cx - 1.5, cy + 4.5)]), "#e2e8f0", 1.8)
        r._line(shape([(cx - 3.0, cy - 6.5), (cx + 1.5, cy + 0.5)]), "#94a3b8", 1.1)
    # Metallic nose bridge & arms
    r._line(shape([(-5.0, -5.5), (0, -7.2), (5.0, -5.5)]), "#cbd5e1", 2.0)
    for s in (-1, 1):
        r._line(shape([(s * 32.5, -6.0), (s * 44.0, -9.0)]), "#3a4354", 1.8)


def _draw_angel_halo(r, shape, size: float, t: float):
    """Floating luminous golden angel halo gently hovering above the head."""
    bob = math.sin(float(t) * 3.2) * 2.5
    center = shape([(0.0, -60.0 + bob)])[0]
    r._ellipse(center, 25.0 * size, 7.2 * size, "", "#fff3b0", 4.0)
    r._ellipse(center, 24.0 * size, 6.4 * size, "", "#ffd60a", 2.2)


def _draw_ribbon_ear(r, shape, size: float, _t: float):
    """Sweet satin pastel-pink ribbon bow perched neatly at the base of the ear."""
    # Left ear inner base (~ -24, -36)
    cx, cy = -25.0, -35.0
    # Ribbon tails
    r._poly(shape([(cx - 1, cy + 3), (cx - 10, cy + 16), (cx - 5, cy + 17), (cx + 1, cy + 5)]), "#e8648c", "#a83358", 0.9)
    r._poly(shape([(cx + 1, cy + 3), (cx + 10, cy + 15), (cx + 5, cy + 17), (cx - 1, cy + 5)]), "#e8648c", "#a83358", 0.9)
    # Left & right satin loops
    r._poly(shape([(cx, cy), (cx - 14, cy - 9), (cx - 16, cy + 5), (cx - 2, cy + 4)]), "#ff85a8", "#a83358", 1.0, smooth=True)
    r._poly(shape([(cx, cy), (cx + 14, cy - 6), (cx + 14, cy + 8), (cx + 2, cy + 4)]), "#ff85a8", "#a83358", 1.0, smooth=True)
    # Central knot
    r._ellipse(shape([(cx, cy + 1.5)])[0], 4.2 * size, 4.2 * size, "#e8648c", "#a83358", 0.9)


def _draw_cozy_sweater(r, shape, size: float, _t: float):
    """Warm knitted autumn-teal shoulder cape/collar with cream knit chevron & wooden button."""
    cape = [
        (-34, 33), (-16, 41), (0, 44), (16, 41), (34, 33),
        (43, 52), (34, 65), (16, 70), (0, 72), (-16, 70), (-34, 65), (-43, 52),
    ]
    r._poly(shape(cape), "#2a6f7c", "#184650", 1.1, smooth=True)
    # Ribbed warm cream collar trim
    collar = [
        (-33, 33), (-16, 41), (0, 44), (16, 41), (33, 33),
        (35, 42), (16, 50), (0, 53), (-16, 50), (-35, 42),
    ]
    r._poly(shape(collar), "#f4e8d1", "#c2b092", 0.9, smooth=True)
    # Knit chevron zig-zag accent stripe
    zig = [(-32, 57), (-22, 62), (-11, 57), (0, 63), (11, 57), (22, 62), (32, 57)]
    r._line(shape(zig), "#f4e8d1", 1.7, smooth=False)
    # Cute little wooden button at throat
    btn = shape([(0.0, 48.0)])[0]
    r._ellipse(btn, 4.0 * size, 4.0 * size, "#a46a38", "#5e3818", 0.9)


_DRAWERS = {
    "star_sticker": _draw_star_sticker,
    "bell_collar": _draw_bell_collar,
    "bandana": _draw_bandana,
    "crown": _draw_crown,
    "flower_crown": _draw_flower_crown,
    "beret": _draw_beret,
    "sunglasses": _draw_sunglasses,
    "angel_halo": _draw_angel_halo,
    "ribbon_ear": _draw_ribbon_ear,
    "cozy_sweater": _draw_cozy_sweater,
}
