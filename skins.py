"""Color skins for the cat. A skin overrides CatRenderer's palette attributes,
so the exact same vector drawing is recolored. The original tuxedo cat is
'komur'. Pure data + a tiny apply helper; no third-party packages."""

# Each skin maps CatRenderer palette attribute names to hex colors. Only the
# attributes present are overridden; everything else keeps the renderer default,
# so a skin only needs to specify what changes.
SKINS = {
    "komur": {
        "label": "Kömür (siyah smokin)",
        "INK": "#0a0d13", "FUR": "#111820", "FUR_LIGHT": "#26313b",
        "FUR_EDGE": "#39434b", "GOLD": "#f8cd35", "GOLD_LIGHT": "#fff17c",
        "GOLD_DARK": "#c98720",
    },
    "zencefil": {
        "label": "Zencefil (turuncu)",
        "INK": "#1a0a02", "FUR": "#c85e1a", "FUR_LIGHT": "#e68a3a",
        "FUR_EDGE": "#9a4710", "GOLD": "#a8e65a", "GOLD_LIGHT": "#d4f5a8",
        "GOLD_DARK": "#5a8c2e",
    },
    "gri": {
        "label": "Gri (Rus mavisi)",
        "INK": "#14181c", "FUR": "#5a6e7a", "FUR_LIGHT": "#7d8f9c",
        "FUR_EDGE": "#45545c", "GOLD": "#4ed9c7", "GOLD_LIGHT": "#9ef0e8",
        "GOLD_DARK": "#26998a",
    },
    "pamuk": {
        "label": "Pamuk (beyaz)",
        "INK": "#2d2623", "FUR": "#f5f0ea", "FUR_LIGHT": "#ffffff",
        "FUR_EDGE": "#e0d5ca", "GOLD": "#6a9fe0", "GOLD_LIGHT": "#b8d4f5",
        "GOLD_DARK": "#3a5a8a",
    },
    "gece": {
        "label": "Gece (lacivert)",
        "INK": "#030509", "FUR": "#122040", "FUR_LIGHT": "#25386a",
        "FUR_EDGE": "#2d4270", "GOLD": "#f0a030", "GOLD_LIGHT": "#ffd980",
        "GOLD_DARK": "#a06515",
    },
    "kahve": {
        "label": "Kahve (çikolata)",
        "INK": "#100804", "FUR": "#3d2414", "FUR_LIGHT": "#5c3a22",
        "FUR_EDGE": "#2e180c", "GOLD": "#e8c03a", "GOLD_LIGHT": "#f5e088",
        "GOLD_DARK": "#8a6e18",
    },
    "altin": {
        "label": "Altın (sarışın)",
        "INK": "#1a1406", "FUR": "#c9a83a", "FUR_LIGHT": "#e8d06a",
        "FUR_EDGE": "#a88a20", "GOLD": "#2a7ae8", "GOLD_LIGHT": "#7ab8f0",
        "GOLD_DARK": "#1a4a9a",
    },
}

DEFAULT_SKIN = "komur"
PALETTE_KEYS = ("INK", "FUR", "FUR_LIGHT", "FUR_EDGE", "GOLD", "GOLD_LIGHT", "GOLD_DARK")


def skin_order():
    """Skin keys in a stable display order, original first."""
    return [DEFAULT_SKIN] + [k for k in SKINS if k != DEFAULT_SKIN]


def label(skin):
    return SKINS.get(skin, SKINS[DEFAULT_SKIN])["label"]


def apply_skin(renderer, skin):
    """Override the renderer instance's palette attributes for the given skin.
    Falls back to the default skin for an unknown name. Safe to call repeatedly.
    """
    data = SKINS.get(skin) or SKINS[DEFAULT_SKIN]
    for key in PALETTE_KEYS:
        if key in data:
            setattr(renderer, key, data[key])
    return renderer
