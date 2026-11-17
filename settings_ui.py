"""Yardımcı penceresinin Ayarlar ve kurulum sekmesi: kurulum kodu ve işleyiciler.

Düz fonksiyonlar; ``ui`` AssistantUI örneğidir ve her pencere öğesi/Tk değişkeni onun üzerinde
kalır (``ui.backend``, ``ui.key_entry``, ...). AssistantUI aynı adlı ince yönlendirici metotları
tutar. assistant_ui içe aktarılmaz.
"""
import sqlite3
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

PROVIDER_LABELS = {"local": "Bilgisayarımda (ücretsiz)", "auto": "Otomatik",
                   "openai": "OpenAI API", "api": "Claude API", "cli": "Claude Code",
                   "offline": "Çevrimdışı komutlar"}


ACCESSORY_LABELS = {None: "Yok", "bow": "Papyon", "scarf": "Atkı", "hat": "Şapka", "glasses": "Gözlük"}
ACTIVITY_LABELS = {"sakin": "Sakin", "normal": "Normal", "hareketli": "Hareketli"}


def build_settings_page(ui):
    """Ayarlar ve kurulum sekmesinin içeriği; her pencere öğesi/değişken ``ui`` üzerinde kalır."""
    ui.backend = tk.StringVar(value=PROVIDER_LABELS.get(ui.app.settings.get("ai_backend"), PROVIDER_LABELS["local"]))
    connection = ttk.LabelFrame(ui.settings_page, text="AI bağlantısı", padding=8)
    connection.pack(fill="x", pady=6)
    connection.columnconfigure(1, weight=1)
    ttk.Label(connection, text="Sağlayıcı").grid(row=0, column=0, sticky="w")
    ttk.Combobox(connection, textvariable=ui.backend,
                 values=tuple(PROVIDER_LABELS.values()), state="readonly").grid(row=0, column=1, sticky="ew")
    local = ui.selected_provider() == "local"
    ui.model = tk.StringVar(value=ui.app.settings.get("ai_local_model" if local else "ai_openai_model"))
    ui.api_url = tk.StringVar(value=ui.app.settings.get("ai_local_base_url" if local else "ai_openai_base_url"))
    ui.api_key = tk.StringVar()
    for row, (label, variable) in enumerate((("OpenAI / yerel model", ui.model),
                                            ("API adresi", ui.api_url),
                                            ("API anahtarı (bu oturum)", ui.api_key)), start=1):
        ttk.Label(connection, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8))
        entry = ttk.Entry(connection, textvariable=variable, show="•" if row == 3 else "")
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        if row == 3:
            ui.key_entry = entry
        elif row == 1:
            ui.model_entry = entry
        elif row == 2:
            ui.url_entry = entry
    controls = ttk.Frame(connection)
    controls.grid(row=4, column=0, columnspan=2, sticky="e", pady=(5, 0))
    ui.apply_button = ttk.Button(controls, text="Ayarları uygula", command=ui.save_options)
    ui.apply_button.pack(side="left", padx=4)
    ui.check_button = ttk.Button(controls, text="Bağlantıyı dene", command=ui.check_connection)
    ui.check_button.pack(side="left")
    ttk.Label(connection, text="local: ücretsiz, anahtarsız, bilgisayarında. API anahtarı dosyaya yazılmaz.", wraplength=580).grid(
        row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))
    ui.context_enabled = tk.BooleanVar(value=ui.app.settings.get("activity_context"))
    ttk.Checkbutton(ui.settings_page, text="Aktif pencere başlığını AI ile paylaş ve etkinliğe göre konuş", variable=ui.context_enabled,
                    command=ui.set_activity_enabled).pack(anchor="w")
    for key, label in (("activity_reactions", "Müzik ve videoya yerel tepki ver (AI ile paylaşılmaz)"),
                       ("focus_mode", "Oyunlarda sessiz ve sakin kal"),
                       ("voice_preview", "Sesle yazdığımı göndermeden önce göster")):
        variable = tk.BooleanVar(value=ui.app.settings.get(key))
        ttk.Checkbutton(ui.settings_page, text=label, variable=variable,
                        command=lambda k=key, v=variable: ui.app.settings.set(k, v.get())).pack(anchor="w")
    ui.habit_enabled = tk.BooleanVar(value=ui.app.settings.get("habit_memory", True))
    ttk.Checkbutton(ui.settings_page, text="Alışkanlıklarımı öğren (yalnız uygulama adı + saat, yerelde)", variable=ui.habit_enabled,
                    command=ui.set_habit_enabled).pack(anchor="w")
    ui.wake_enabled = tk.BooleanVar(value=ui.app.settings.get("wake_word", False))
    ttk.Checkbutton(ui.settings_page, text="\"Hey Kömür\" ile uyandır (mikrofon sürekli dinler, yerelde)",
                    variable=ui.wake_enabled, command=ui.set_wake_enabled).pack(anchor="w")
    ui.wake_status = ttk.Label(ui.settings_page, text="", foreground="#a33", wraplength=580)
    ui.wake_status.pack(anchor="w")
    ui.daynight_enabled = tk.BooleanVar(value=ui.app.settings.get("day_night", True))
    ttk.Checkbutton(ui.settings_page, text="Saate göre gece/akşam tonu", variable=ui.daynight_enabled,
                    command=lambda: ui.app.settings.set("day_night", bool(ui.daynight_enabled.get()))).pack(anchor="w")
    look_bar = ttk.Frame(ui.settings_page)
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
    ui.history_enabled = tk.BooleanVar(value=ui.app.settings.get("history_enabled"))
    ttk.Checkbutton(ui.settings_page, text="Sohbet geçmişini bu bilgisayarda sakla", variable=ui.history_enabled,
                    command=ui.set_history_enabled).pack(anchor="w")
    ui.voice_enabled = tk.BooleanVar(value=ui.app.settings.get("voice_replies"))
    ttk.Checkbutton(ui.settings_page, text="Yanıtları Türkçe sesli oku", variable=ui.voice_enabled,
                    command=lambda: ui.set_voice_enabled(ui.voice_enabled.get())).pack(anchor="w")
    microphone_bar = ttk.Frame(ui.settings_page)
    microphone_bar.pack(fill='x', pady=4)
    ttk.Label(microphone_bar, text='Mikrofon:').pack(side='left')
    devices = ui.voice.list_input_devices()
    device_labels = {'Windows varsayılanı': None, **{f"{d['id']}: {d['name']}": d['id'] for d in devices}}
    mic = ttk.Combobox(microphone_bar, values=list(device_labels), state='readonly')
    mic.set(next((label for label, index in device_labels.items() if index == ui.voice.input_device), 'Windows varsayılanı'))
    mic.pack(side='left', fill='x', expand=True, padx=5)
    def select_microphone(event):
        ui.voice.input_device = device_labels[mic.get()]
        ui.app.settings.set('voice_input_device', ui.voice.input_device)
    mic.bind('<<ComboboxSelected>>', select_microphone)
    rate_bar = ttk.Frame(ui.settings_page)
    rate_bar.pack(fill='x')
    ttk.Label(rate_bar, text='Konuşma hızı:').pack(side='left')
    rate = tk.IntVar(value=ui.voice.speech_rate)
    def change_rate(value):
        ui.voice.speech_rate = int(float(value))
        ui.app.settings.set('speech_rate', ui.voice.speech_rate)
    tk.Scale(rate_bar, from_=-5, to=5, orient='horizontal', variable=rate,
             command=change_rate, showvalue=True, length=180).pack(side='left')
    ttk.Button(ui.settings_page, text="Ses ve AI kurulum yardımcısı", command=ui.launch_setup).pack(anchor="w", pady=12)
    ttk.Button(ui.settings_page, text="Bekleyen hatırlatıcıları iptal et", command=ui.clear_reminders).pack(anchor="w")
    ttk.Button(ui.settings_page, text="Hafızamı yönet", command=ui.manage_memory).pack(anchor="w", pady=3)
    ttk.Button(ui.settings_page, text="Ses, AI ve bilgisayar durumunu kontrol et", command=ui.check_health).pack(anchor="w")
    update_bar = ttk.Frame(ui.settings_page)
    update_bar.pack(fill="x", pady=(10, 0))
    ttk.Button(update_bar, text="Güncellemeleri denetle", command=lambda: ui.updates.check()).pack(side="left")
    ttk.Button(update_bar, text="Şimdi güncelle", command=lambda: ui.updates.install()).pack(side="left", padx=6)
    ui.update_status = ttk.Label(update_bar, text=ui.updates.status)
    ui.update_status.pack(side="left", padx=6)
    ui.update_auto = tk.BooleanVar(value=ui.app.settings.get("update_check", True))
    ttk.Checkbutton(ui.settings_page, text="Günde bir kez GitHub'da yeni sürüm denetle (kurulum yalnız onayla)",
                    variable=ui.update_auto,
                    command=lambda: ui.app.settings.set("update_check", bool(ui.update_auto.get()))).pack(anchor="w")
    ui.backend.trace_add("write", ui.provider_changed)
    ui.key_entry.configure(state="disabled" if local else "normal")
    ui.model_entry.configure(state="readonly" if local else "normal")
    ui.url_entry.configure(state="readonly" if local else "normal")


def save_options(ui):
    if ui.busy:
        return False
    local = ui.selected_provider() == "local"
    if ui.api_key.get().strip() and not local:
        ui.session_options["ai_openai_key"] = ui.api_key.get().strip()
        ui.api_key.set("")
    options = {"ai_local_model" if local else "ai_openai_model": ui.model.get().strip(),
               "ai_local_base_url" if local else "ai_openai_base_url": ui.api_url.get().strip()}
    ui.app.settings.update(ai_backend=ui.selected_provider(), activity_context=ui.context_enabled.get(),
                             history_enabled=ui.history_enabled.get(), voice_replies=ui.voice_enabled.get(), **options)
    if ui.compact is not None:
        ui.compact.voice_enabled.set(ui.voice_enabled.get())
    if not ui.voice_enabled.get():
        ui.voice.stop()
    ui.status.configure(text=ui.ai.backend_status())
    return True


def check_health(ui):
    from diagnostics import health_report
    ui.submit(lambda: "\n".join(health_report(ui.voice)), kind="connection")


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


def set_wake_enabled(ui):
    enabled = bool(ui.wake_enabled.get())
    ui.app.settings.set("wake_word", enabled)
    if enabled:
        ui.start_wake()
    else:
        ui.stop_wake()


def set_history_enabled(ui):
    ui.app.settings.set("history_enabled", ui.history_enabled.get())


def set_activity_enabled(ui):
    enabled = ui.context_enabled.get()
    ui.app.settings.set("activity_context", enabled)
    if enabled:
        ui.context_tainted = True
    else:
        ui.context_text = "Etkinlik paylaşımı kapalı."


def selected_provider(ui):
    return next((key for key, label in PROVIDER_LABELS.items() if label == ui.backend.get()), "local")


def provider_changed(ui, *args):
    local = ui.selected_provider() == "local"
    ui.model.set(ui.app.settings.get("ai_local_model" if local else "ai_openai_model"))
    ui.api_url.set(ui.app.settings.get("ai_local_base_url" if local else "ai_openai_base_url"))
    ui.key_entry.configure(state="disabled" if local else "normal")
    ui.model_entry.configure(state="readonly" if local else "normal")
    ui.url_entry.configure(state="readonly" if local else "normal")


def check_connection(ui):
    if ui.save_options():
        ui.status.configure(text="AI bağlantısı deneniyor…")
        ui.submit(ui.ai.check_connection, kind="connection")


def launch_setup(ui):
    home = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    helper = home / "bootstrap_setup.exe"
    if helper.is_file():
        command = [str(helper)]
    elif (home / "bootstrap_setup.py").is_file() and not getattr(sys, "frozen", False):
        command = [sys.executable, str(home / "bootstrap_setup.py")]
    else:
        messagebox.showinfo("Kurulum yardımcısı", "Kömür kurulum paketini yeniden açarak isteğe bağlı AI ve ses modellerini kurabilirsin.", parent=ui.window)
        return
    subprocess.Popen(command, creationflags=0x08000000 if sys.platform == "win32" else 0)
