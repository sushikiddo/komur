"""Kontrol paneli (Davranış / Görünüm / Sistem sekmeleri) ve ayar işleyicileri.

Düz fonksiyonlar; ``app`` DesktopCat örneğidir. Panel penceresi ``app.panel``'de, Tk değişkenleri
(name_var, skin_var, ...) DesktopCat'te kalır. cat.py içe aktarılmaz.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import autostart
import skins
import sound
from settings import SIZE_LABELS, SIZE_SCALES

TITLE = "Kömür — Kontrol paneli"


def show_panel(app):
    if app.panel is not None and app.panel.winfo_exists():
        app.panel.deiconify()
        app.panel.lift()
        app.panel.focus_force()
        return
    app.panel = tk.Toplevel(app.root)
    app.panel.title(TITLE)
    app.panel.resizable(False, False)
    app.panel.attributes("-topmost", True)
    nb = ttk.Notebook(app.panel)
    nb.pack(fill="both", expand=True, padx=2, pady=2)
    build_actions_tab(app, nb)
    build_look_tab(app, nb)
    build_system_tab(app, nb)
    app.panel.protocol("WM_DELETE_WINDOW", app.panel.withdraw)
    app._refresh_status()

def build_actions_tab(app, nb):
    content = ttk.Frame(nb, padding=18)
    nb.add(content, text="Davranış")
    ttk.Label(content, text=app.settings.get("name"),
              font=("Segoe UI", 22, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(content, text="Masaüstündeki küçük dostun",
              font=("Segoe UI", 10)).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 14))
    ttk.Label(content, textvariable=app.status_var).grid(
        row=2, column=0, columnspan=2, pady=(0, 12))
    buttons = [
        ("♥ Sev", "pet"), ("Mama ver", "feed"), ("Topla oyna", "play"),
        ("Süpür", "knead"), ("Kuş sesi", "chirp"), ("Fıss", "hiss"),
        ("Hapsıyor", "sneeze"),
        ("Fareyi takip et", "follow"), ("Gezin / Bırak", "wander"),
        ("Uyu", "sleep"), ("Uyan", "wake"),
        ("Yerde yuvarlan", "roll"), ("Esne", "yawn"), ("Sıkıl", "bored"),
    ]
    for index, (label, name) in enumerate(buttons):
        ttk.Button(content, text=label, width=20,
                   command=lambda n=name: app.command(n)).grid(
            row=3 + index // 2, column=index % 2, padx=4, pady=4, sticky="ew")
    row = 3 + (len(buttons) + 1) // 2
    ttk.Button(content, text="Duraklat / Devam et", command=app.toggle_pause).grid(
        row=row, column=0, padx=4, pady=4, sticky="ew")
    ttk.Button(content, text="Diğer ekrana geç", command=app.next_monitor).grid(
        row=row, column=1, padx=4, pady=4, sticky="ew")
    shortcut = ("Ctrl + Shift + K: paneli aç" if app.hotkey_id
                else "Sağ tık veya çift tık: paneli aç")
    ttk.Label(content, text="Tıkla: sev  •  Sürükle: taşı\n" + shortcut +
              "\nTakip açıkken Gezin ile durdurabilirsin.",
              justify="left").grid(row=row + 1, column=0, columnspan=2, sticky="w", pady=14)

def build_look_tab(app, nb):
    content = ttk.Frame(nb, padding=18)
    nb.add(content, text="Görünüm")
    ttk.Label(content, text="İsim").grid(row=0, column=0, sticky="w", pady=4)
    name_entry = ttk.Entry(content, textvariable=app.name_var, width=22)
    name_entry.grid(row=0, column=1, sticky="ew", pady=4)
    name_entry.bind("<Return>", lambda e: on_name_change(app))
    name_entry.bind("<FocusOut>", lambda e: on_name_change(app))

    ttk.Label(content, text="Tüy rengi").grid(row=1, column=0, sticky="w", pady=4)
    skin_box = ttk.Combobox(content, state="readonly", width=20,
                            values=[skins.label(k) for k in skins.skin_order()])
    order = skins.skin_order()
    skin_box.current(order.index(app.settings.get("skin"))
                     if app.settings.get("skin") in order else 0)
    skin_box.grid(row=1, column=1, sticky="ew", pady=4)
    skin_box.bind("<<ComboboxSelected>>",
                  lambda e: on_skin_change(app, order[skin_box.current()]))

    ttk.Label(content, text="Boyut").grid(row=2, column=0, sticky="w", pady=4)
    size_keys = list(SIZE_SCALES.keys())
    size_box = ttk.Combobox(content, state="readonly", width=20,
                            values=[SIZE_LABELS[k] for k in size_keys])
    size_box.current(size_keys.index(app.settings.get("size"))
                     if app.settings.get("size") in size_keys else 1)
    size_box.grid(row=2, column=1, sticky="ew", pady=4)
    size_box.bind("<<ComboboxSelected>>",
                  lambda e: on_size_change(app, size_keys[size_box.current()]))

    ttk.Label(content, text="Saydamlık").grid(row=3, column=0, sticky="w", pady=4)
    scale = ttk.Scale(content, from_=20, to=100, variable=app.opacity_var,
                      command=lambda v: on_opacity_change(app))
    scale.grid(row=3, column=1, sticky="ew", pady=4)

    ttk.Label(content, text="Arkadaş sayısı").grid(row=4, column=0, sticky="w", pady=4)
    ttk.Spinbox(content, from_=0, to=3, width=5, textvariable=app.friends_var,
                command=lambda: on_friends_change(app)).grid(row=4, column=1, sticky="w", pady=4)

def build_system_tab(app, nb):
    content = ttk.Frame(nb, padding=18)
    nb.add(content, text="Sistem")
    ttk.Checkbutton(content, text="Sesler (miyav / mırlama)",
                    variable=app.sound_var, command=lambda: on_sound_change(app)).grid(
        row=0, column=0, sticky="w", pady=6)
    ttk.Checkbutton(content, text="İhtiyaç & ruh hali sistemi",
                    variable=app.needs_var, command=lambda: on_needs_change(app)).grid(
        row=1, column=0, sticky="w", pady=6)
    auto = ttk.Checkbutton(content, text="Windows ile başlat",
                           variable=app.autostart_var, command=lambda: on_autostart_change(app))
    auto.grid(row=2, column=0, sticky="w", pady=6)
    if not autostart.available():
        auto.state(["disabled"])

    ttk.Label(content, text="Ses Kalitesi").grid(row=3, column=0, sticky="w", pady=4)
    quality_box = ttk.Combobox(content, state="readonly", width=20,
                               values=["Yüksek (Gerçekçi WAV)", "Normal (Senteli)"])
    quality_box.current(0 if app.settings.get("sound_quality") == "high" else 1)
    quality_box.grid(row=3, column=1, sticky="ew", pady=4)
    quality_box.bind("<<ComboboxSelected>>",
                     lambda e: on_quality_change(app, ["high", "normal"][quality_box.current()]))

    ttk.Label(content, text="Efekt Yoğunluğu").grid(row=4, column=0, sticky="w", pady=4)
    density_box = ttk.Combobox(content, state="readonly", width=20,
                               values=["Düşük", "Normal", "Yüksek"])
    density_box.current(app.settings.get("effects_density", 2) - 1)
    density_box.grid(row=4, column=1, sticky="ew", pady=4)
    density_box.bind("<<ComboboxSelected>>",
                     lambda e: on_density_change(app, density_box.current() + 1))

    if getattr(app, "tray", None) and app.tray.available:
        ttk.Label(content, text="Sistem tepsisi: etkin (sağ tık: menü)").grid(
            row=5, column=0, sticky="w", pady=6)
    ttk.Separator(content, orient="horizontal").grid(
        row=6, column=0, sticky="ew", pady=10)
    ttk.Button(content, text="Paneli gizle", command=app.panel.withdraw).grid(
        row=7, column=0, sticky="ew", pady=4)
    ttk.Button(content, text="Kömür'ü kapat", command=app.close).grid(
        row=8, column=0, sticky="ew", pady=4)
    ttk.Separator(content, orient="horizontal").grid(
        row=9, column=0, sticky="ew", pady=10)
    ttk.Label(content, text="Kedile Konuş (AI Yardımcı)").grid(
        row=10, column=0, sticky="w", pady=4)
    ttk.Button(content, text="Konuşma penceresini aç",
               command=app._on_speak_click).grid(
        row=11, column=0, sticky="ew", pady=4)
    ttk.Label(content, text="Günlük: %LOCALAPPDATA%\\Komur\\komur.log",
              font=("Segoe UI", 8)).grid(row=9, column=0, sticky="w", pady=(10, 0))


# -- panel callbacks --------------------------------------------------
def on_name_change(app):
    name = app.name_var.get().strip() or "Kömür"
    app.name_var.set(name)
    app.settings.set("name", name)
    app.say(f"Artık adım {name}!", 4)

def on_skin_change(app, skin):
    app.settings.set("skin", skin)
    app.skin_var.set(skin)
    app._apply_skin()
    for mate in app.companions:
        skins.apply_skin(mate.renderer, skin)
    app.say("Yeni kürk!", 4)

def on_size_change(app, size):
    app.settings.set("size", size)
    app.size_var.set(size)
    app._apply_size()
    app._rebuild_companions()
    app._apply_opacity()

def on_opacity_change(app):
    value = int(app.opacity_var.get())
    app.settings.set("opacity", value)
    app._apply_opacity()

def on_friends_change(app):
    app.settings.set("friends", int(app.friends_var.get()))
    app._rebuild_companions()
    app._apply_opacity()

def on_sound_change(app):
    enabled = bool(app.sound_var.get())
    app.settings.set("sound", enabled)
    if enabled:
        sound.play("meow", enabled=True)

def on_needs_change(app):
    enabled = bool(app.needs_var.get())
    app.settings.set("needs", enabled)
    app.brain.needs_enabled = enabled
    for mate in app.companions:
        mate.brain.needs_enabled = enabled

def on_autostart_change(app):
    want = bool(app.autostart_var.get())
    result = autostart.set_enabled(want)
    app.autostart_var.set(result)
    app.settings.set("autostart", result)

def on_quality_change(app, quality):
    app.settings.set("sound_quality", quality)
    app.quality_var.set(quality)
    app.effect_orchestrator.set_quality(quality)
    app.say(f"Ses kalitesi: {'Yüksek' if quality == 'high' else 'Normal'}", 3)

def on_density_change(app, density):
    app.settings.set("effects_density", density)
    app.density_var.set(density)
    app.effect_orchestrator.particles.MAX_PARTICLES = {1: 300, 2: 600, 3: 1000}[density]
    app.say(f"Efekt yoğunluğu: {'Düşük' if density == 1 else 'Normal' if density == 2 else 'Yüksek'}", 3)
