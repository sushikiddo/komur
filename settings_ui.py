"""Geçmiş penceresinin Ayarlar sekmesi: kurulum kodu ve işleyiciler.

Düz fonksiyonlar; ``ui`` AssistantUI örneğidir ve her pencere öğesi/Tk değişkeni onun üzerinde
kalır. assistant_ui içe aktarılmaz.
"""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

ACCESSORY_LABELS = {None: "Yok", "bow": "Papyon", "scarf": "Atkı", "hat": "Şapka", "glasses": "Gözlük"}
ACTIVITY_LABELS = {"sakin": "Sakin", "normal": "Normal", "hareketli": "Hareketli"}


def _check(ui, text, key, default=False, command=None):
    variable = tk.BooleanVar(value=ui.app.settings.get(key, default))
    ttk.Checkbutton(ui.settings_page, text=text, variable=variable,
                    command=command or (lambda: ui.app.settings.set(key, bool(variable.get())))).pack(anchor="w")
    return variable


def build_settings_page(ui):
    page = ui.settings_page
    ui.context_enabled = _check(ui, "Ne yaptığıma göre kısa laflar et (pencere başlığı kaydedilmez)",
                                "activity_context", command=lambda: ui.set_activity_enabled())
    _check(ui, "Müzik ve videoya tepki ver", "activity_reactions")
    _check(ui, "Oyunlarda sessiz ve sakin kal", "focus_mode", True)
    ui.habit_enabled = _check(ui, "Alışkanlıklarımı öğren (yalnız uygulama adı + saat, yerelde)",
                              "habit_memory", True, command=lambda: ui.set_habit_enabled())
    _check(ui, "Saate göre gece/akşam tonu", "day_night", True)
    ui.history_enabled = _check(ui, "Komut geçmişini bu bilgisayarda sakla", "history_enabled",
                                command=lambda: ui.set_history_enabled())
    look_bar = ttk.Frame(page)
    look_bar.pack(fill="x", pady=2)
    ttk.Label(look_bar, text="Aksesuar:").pack(side="left")
    ui.accessory_box = ttk.Combobox(look_bar, values=list(ACCESSORY_LABELS.values()), state="readonly", width=10)
    ui.accessory_box.set(ACCESSORY_LABELS.get(ui.app.settings.get("accessory"), "Yok"))
    ui.accessory_box.pack(side="left", padx=5)
    ui.accessory_box.bind("<<ComboboxSelected>>", lambda event: ui.set_accessory(ui.accessory_box.get()))
    ttk.Label(look_bar, text="Hareket:").pack(side="left", padx=(10, 0))
    ui.activity_box = ttk.Combobox(look_bar, values=list(ACTIVITY_LABELS.values()), state="readonly", width=10)
    ui.activity_box.set(ACTIVITY_LABELS.get(ui.app.settings.get("activity_level"), "Sakin"))
    ui.activity_box.pack(side="left", padx=5)
    ui.activity_box.bind("<<ComboboxSelected>>", lambda event: ui.set_activity_level(ui.activity_box.get()))
    ttk.Button(page, text="Bekleyen hatırlatıcıları iptal et", command=ui.clear_reminders).pack(anchor="w", pady=(12, 0))
    ttk.Button(page, text="Hafızamı yönet", command=ui.manage_memory).pack(anchor="w", pady=3)
    if ui.updates is not None:
        update_bar = ttk.Frame(page)
        update_bar.pack(fill="x", pady=(10, 0))
        ttk.Button(update_bar, text="Güncellemeleri denetle", command=lambda: ui.updates.check()).pack(side="left")
        ttk.Button(update_bar, text="Şimdi güncelle", command=lambda: ui.updates.install()).pack(side="left", padx=6)
        ui.update_status = ttk.Label(update_bar, text=ui.updates.status)
        ui.update_status.pack(side="left", padx=6)
        _check(ui, "Günde bir kez GitHub'da yeni sürüm denetle (kurulum yalnız onayla)", "update_check", True)


def manage_memory(ui):
    if not ui.memory:
        return
    from tkinter import simpledialog, filedialog
    win = tk.Toplevel(ui.app.root)
    win.title("Kömür — Hatırladıklarım")
    win.geometry("490x350")
    listing = tk.Listbox(win, font=("Segoe UI", 10))
    listing.pack(fill="both", expand=True, padx=10, pady=10)
    rows = []
    def refresh():
        rows[:] = ui.memory.notes(limit=100)
        listing.delete(0, "end")
        for row in rows:
            listing.insert("end", f"{row['id']}: {row['content']}")
    def edit():
        if not listing.curselection():
            return
        row = rows[listing.curselection()[0]]
        value = simpledialog.askstring("Notu düzenle", "Kömür ne hatırlasın?", initialvalue=row['content'], parent=win)
        if value and value.strip():
            try:
                ui.memory.update_note(row['id'], value)
                refresh()
            except ValueError as error:
                messagebox.showerror("Not", str(error), parent=win)
    def delete():
        if listing.curselection() and messagebox.askyesno("Notu unut", "Seçilen not silinsin mi?", parent=win):
            ui.memory.forget(rows[listing.curselection()[0]]['id'])
            refresh()
    def backup():
        path = filedialog.asksaveasfilename(parent=win, defaultextension=".sqlite3", filetypes=[("Kömür hafızası", "*.sqlite3")])
        if path:
            try:
                ui.memory.backup(path)
                messagebox.showinfo("Yedek", "Notlar, sohbetler ve hatırlatıcılar seçtiğin dosyaya yedeklendi.", parent=win)
            except (OSError, sqlite3.Error, ValueError) as error:
                messagebox.showerror("Yedek", str(error), parent=win)
    bar = ttk.Frame(win)
    bar.pack(pady=(0, 10))
    for text, command in (("Düzenle", edit), ("Unut", delete), ("Hafızayı yedekle", backup)):
        ttk.Button(bar, text=text, command=command).pack(side="left", padx=4)
    refresh()


def set_habit_enabled(ui):
    enabled = bool(ui.habit_enabled.get())
    ui.app.settings.set("habit_memory", enabled)
    if not enabled and ui.memory:
        ui.memory.clear_habits()


def set_accessory(ui, label):
    value = next((key for key, text in ACCESSORY_LABELS.items() if text == label), None)
    ui.app.settings.set("accessory", value)


def set_activity_level(ui, label):
    level = next((key for key, text in ACTIVITY_LABELS.items() if text == label), "sakin")
    ui.app.settings.set("activity_level", level)
    ui.app.brain.set_activity(level)


def set_history_enabled(ui):
    ui.app.settings.set("history_enabled", bool(ui.history_enabled.get()))


def set_activity_enabled(ui):
    enabled = ui.context_enabled.get()
    ui.app.settings.set("activity_context", enabled)
    if not enabled:
        ui.context_text = "Etkinlik paylaşımı kapalı."
