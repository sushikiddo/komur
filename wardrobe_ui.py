"""4-slot visual costume wardrobe widget for Kontrol Paneli.

Allows combining up to 4 independent slots simultaneously (head + eyes + neck + body)
with clickable visual cards, active highlight badges, and instant live preview updates.
"""
from __future__ import annotations

import tkinter as tk

from costumes import (
    COSTUME_LABELS,
    SLOT_LABELS,
    SLOT_UI_ORDER,
    items_in_slot,
    normalize_accessories,
    summary_label,
)


def current_wardrobe_slots(settings) -> dict[str, str]:
    """Read normalized 4-slot wardrobe dict from Settings (backwards-compatible)."""
    if settings is None:
        return {}
    raw = settings.get("accessories")
    if isinstance(raw, dict) and raw:
        return normalize_accessories(raw)
    return normalize_accessories(settings.get("accessory"))


def build_wardrobe_card(
    parent,
    app,
    *,
    bg_card: str,
    bg_dark: str,
    border: str,
    accent: str,
    text_main: str,
    text_muted: str,
    on_toggle,
    on_clear,
):
    """Build a compact 4-slot interactive visual wardrobe inside ``parent``."""
    active_slot = {"name": "head"}

    header = tk.Frame(parent, bg=bg_card)
    header.pack(fill="x", pady=(0, 6))
    summary_var = tk.StringVar(value=summary_label(current_wardrobe_slots(app.settings)))
    tk.Label(
        header,
        textvariable=summary_var,
        bg=bg_card,
        fg=accent,
        font=("Segoe UI", 8, "bold"),
        anchor="w",
    ).pack(side="left", fill="x", expand=True)

    clear_btn = tk.Label(
        header,
        text="✕ Temizle",
        bg=bg_dark,
        fg=text_muted,
        font=("Segoe UI", 8, "bold"),
        padx=8,
        pady=3,
        cursor="hand2",
        highlightbackground=border,
        highlightthickness=1,
    )
    clear_btn.pack(side="right")

    tabs_row = tk.Frame(parent, bg=bg_card)
    tabs_row.pack(fill="x", pady=(0, 6))

    grid_box = tk.Frame(parent, bg=bg_card, height=112)
    grid_box.pack(fill="x", pady=(0, 6))
    grid_box.pack_propagate(False)

    grid_frame = tk.Frame(grid_box, bg=bg_card)
    grid_frame.pack(fill="both", expand=True)
    for col in range(3):
        grid_frame.columnconfigure(col, weight=1, uniform="wardrobe_col")

    tab_widgets: dict[str, tk.Label] = {}

    def _refresh():
        slots = current_wardrobe_slots(app.settings)
        summary_var.set("Kombin: " + summary_label(slots))
        cur = active_slot["name"]

        for s_key, lbl in tab_widgets.items():
            has_item = bool(slots.get(s_key))
            selected = s_key == cur
            base_txt = SLOT_LABELS[s_key]
            lbl.configure(
                text=f"{base_txt} •" if has_item else base_txt,
                bg=accent if selected else bg_dark,
                fg="#ffffff" if selected else (accent if has_item else text_main),
                highlightbackground=accent if (selected or has_item) else border,
            )

        for child in grid_frame.winfo_children():
            child.destroy()

        slot_items = items_in_slot(cur)
        chosen = slots.get(cur)
        for idx, item_key in enumerate(slot_items):
            is_on = item_key == chosen
            label_txt = COSTUME_LABELS.get(item_key, item_key)
            if is_on:
                label_txt = f"✓ {label_txt}"
            pill = tk.Label(
                grid_frame,
                text=label_txt,
                bg="#1d2f45" if is_on else bg_dark,
                fg="#ffffff" if is_on else text_main,
                font=("Segoe UI", 8, "bold" if is_on else "normal"),
                anchor="w",
                padx=6,
                pady=4,
                cursor="hand2",
                highlightbackground=accent if is_on else border,
                highlightthickness=2 if is_on else 1,
            )
            pill.grid(row=idx // 3, column=idx % 3, padx=2, pady=2, sticky="ew")

            def _click(_e, k=item_key):
                on_toggle(app, k)
                _refresh()

            pill.bind("<Button-1>", _click)

    def _select_slot(slot_name: str):
        active_slot["name"] = slot_name
        _refresh()

    for s_key in SLOT_UI_ORDER:
        tab_lbl = tk.Label(
            tabs_row,
            text=SLOT_LABELS[s_key],
            bg=bg_dark,
            fg=text_main,
            font=("Segoe UI", 8, "bold"),
            padx=7,
            pady=4,
            cursor="hand2",
            highlightbackground=border,
            highlightthickness=1,
        )
        tab_lbl.pack(side="left", fill="x", expand=True, padx=2)
        tab_lbl.bind("<Button-1>", lambda _e, s=s_key: _select_slot(s))
        tab_widgets[s_key] = tab_lbl

    def _on_clear(_e=None):
        on_clear(app)
        _refresh()

    clear_btn.bind("<Button-1>", _on_clear)
    _refresh()
    return _refresh
