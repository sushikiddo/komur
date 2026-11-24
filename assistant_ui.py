"""Komut yazma baloncuğu ve geçmiş penceresi. Tk tüm pencere öğelerinin sahibidir;
tek bir arka plan işçisi komutları sırayla çalıştırır (yapay zekâ yok)."""
import logging
import queue
import sqlite3
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from commands import CommandEngine
from focus import parse_focus_command
from context import ActivityTracker
from pc_actions import PCActions, ActionSpec
from memory_store import MemoryStore
from chat_bubble import ChatBubble
import settings_ui

CAT_BEHAVIORS = ("bored", "roll", "yawn", "play", "sleep", "wake", "pet", "feed", "wander", "follow", "dance", "watch")


class AssistantUI:
    def __init__(self, app):
        self.app = app
        self.events = queue.Queue()
        self.delta_events = queue.Queue()      # akan yanıt parçaları: (istek no, metin | None)
        self._stream_id = 0
        self._partial = ""
        self.behavior_requests = queue.Queue()
        self.chat_log = []
        self.compact = None
        try:
            self.memory = MemoryStore()
            self.chat_log = [("Sen" if row["role"] == "user" else "Kömür", row["content"])
                             for row in self.memory.messages()]
        except (OSError, sqlite3.Error):
            logging.exception("Local memory unavailable; continuing without persistence")
            self.memory = None
            self.chat_log.append(("Hafıza", "Geçmiş dosyası açılamadı; mevcut dosyan korunuyor, bu oturum kaydedilmeyecek."))
        self.tracker = ActivityTracker()
        self.context_text = "Etkinlik paylaşımı kapalı."
        self.actions = PCActions(on_timer=self.save_timer)
        self.actions.register(ActionSpec(
            "cat_behavior", "Kömür'ün davranışını değiştir: yuvarlanma, esneme, oyun, uyku veya takip.",
            {"properties": {"behavior": {"type": "string", "enum": list(CAT_BEHAVIORS)}},
             "required": ["behavior"]}, self.request_behavior))
        self.register_assistance_actions()
        self.commands = CommandEngine(self.app.settings.get, self.actions, self.command_context, habits=self.memory)
        if self.memory:
            for reminder in self.memory.pending_reminders():
                self.actions.timers.append({"label": reminder["label"], "due": time.monotonic() + max(0, reminder["due"] - time.time()),
                                            "memory_id": reminder["id"]})
        self.window = None
        self.busy = False
        self.closed = False
        self._habit_check = float("-inf")
        self.updates = None
        if sys.platform == "win32":       # güncelleyici yalnız Windows EXE sürümünü kurar
            from update_ui import UpdateFlow
            self.updates = UpdateFlow(self.app)

    def register_assistance_actions(self):
        def unavailable(*args, **kwargs):
            return "Olmadı: yerel hafıza dosyası açılamıyor."
        for spec in (
            ActionSpec("list_reminders", "Bekleyen yerel hatırlatıcıları numaralarıyla listele.",
                       {"properties": {}, "required": []}, self.list_reminders),
            ActionSpec("cancel_reminder", "Numarası belirtilen hatırlatıcıyı iptal et.",
                       {"properties": {"reminder_id": {"type": "integer"}}, "required": ["reminder_id"]},
                       self.cancel_reminder),
            ActionSpec("recurring_reminder", "Belirtilen dakika aralığıyla tekrar eden yerel hatırlatıcı kur.",
                       {"properties": {"minutes": {"type": "number"}, "label": {"type": "string"}}, "required": ["minutes", "label"]},
                       self.recurring_reminder),
            ActionSpec("remember_fact", "Kullanıcı açıkça hatırlamanı istediğinde yerel not kaydet.",
                       {"properties": {"text": {"type": "string"}}, "required": ["text"]}, self.memory.remember if self.memory else unavailable),
            ActionSpec("recall_memories", "Kaydedilmiş yerel notlarda ara.",
                       {"properties": {"query": {"type": "string"}}, "required": ["query"]}, self.memory.recall if self.memory else unavailable),
            ActionSpec("forget_memory", "Bir yerel notu numarasıyla unut. Onay gerekir.",
                       {"properties": {"note_id": {"type": "integer"}}, "required": ["note_id"]},
                       self.memory.forget if self.memory else unavailable, dangerous=True,
                       confirm_text=lambda args: f"Yerel hafızadaki {args.get('note_id')} numaralı not silinsin mi?"),
        ):
            self.actions.register(spec)

    def command_context(self):
        """Komut motoruna yalnız hava bilgisi gerekir ("hava nasıl")."""
        return {"weather": self.weather_text()}

    def weather_text(self):
        """"Antalya 18°C açık" ya da hava izleyicisi kapalı/veri yoksa ""."""
        watcher = getattr(getattr(self, "app", None), "weather", None)
        condition = getattr(watcher, "condition", None)
        if not condition:
            return ""
        try:
            from weather import LABELS_TR
            label = LABELS_TR.get(condition, "").split(" ")[0] or str(condition)
        except ImportError:
            label = str(condition)
        temp = getattr(watcher, "temp", None)
        temp_text = f" {round(temp)}°C" if isinstance(temp, (int, float)) else ""
        place = (getattr(watcher, "place", "") or getattr(watcher, "city", "") or "").strip()[:40]
        return f"{place}{temp_text} {label}".strip()

    def list_reminders(self):
        if not self.memory:
            return "Yerel hafıza kullanılamıyor."
        rows = self.memory.pending_reminders()
        return "\n".join(f"{r['id']}: {r['label']} — {time.strftime('%d.%m %H:%M', time.localtime(r['due']))}" for r in rows) or "Bekleyen hatırlatıcın yok."

    def cancel_reminder(self, reminder_id):
        if not self.memory:
            return "Olmadı: yerel hafıza kullanılamıyor."
        if not any(r['id'] == reminder_id for r in self.memory.pending_reminders()):
            return "Bu numarada bekleyen hatırlatıcı yok."
        self.memory.cancel_reminder(reminder_id)
        self.actions.timers[:] = [t for t in self.actions.timers if t.get('memory_id') != reminder_id]
        return "Hatırlatıcıyı iptal ettim."

    def recurring_reminder(self, minutes, label):
        import math
        if not self.memory:
            return "Olmadı: yerel hafıza kullanılamıyor."
        minutes = float(minutes)
        if not math.isfinite(minutes) or not 1 <= minutes <= 525600:
            return "Olmadı: tekrar aralığı 1 dakika ile 1 yıl arasında olmalı."
        seconds = minutes * 60
        reminder_id = self.memory.add_reminder(label, time.time() + seconds, seconds)
        self.actions.timers.append({'label': label, 'due': time.monotonic() + seconds, 'memory_id': reminder_id})
        return f"Her {minutes:g} dakikada bir hatırlatacağım: {label} (hatırlatıcı {reminder_id})."

    def save_timer(self, spec):
        if self.memory:
            spec["memory_id"] = self.memory.add_reminder(spec["label"], time.time() + spec["seconds"])

    def show(self):
        if self.compact is None:
            self.compact = ChatBubble(self)
        self.compact.show()
        self.compact.set_busy(self.busy)

    @property
    def compact_visible(self):
        return self.compact is not None and self.compact.visible

    def request_behavior(self, behavior):
        if behavior not in CAT_BEHAVIORS:
            return "Geçersiz kedi davranışı."
        self.behavior_requests.put(behavior)
        return f"Kömür davranışı sıraya alındı: {behavior}"

    def set_busy(self, value):
        self.busy = value
        if self.compact is not None:
            self.compact.set_busy(value)
        if self.window is not None and self.window.winfo_exists():
            for button in (self.send_button, self.clear_button):
                button.configure(state="disabled" if value else "normal")

    def submit(self, function, *args, kind="reply"):
        if self.busy or self.closed:
            return
        self.set_busy(True)
        def run():
            if self.closed:
                return
            try:
                self.events.put((kind, function(*args)))
            except Exception as error:
                logging.exception("Command failed")
                self.events.put(("error", "İşlem tamamlanamadı. " + str(error)))
        threading.Thread(target=run, daemon=True).start()

    def show_history(self):
        if self.compact_visible:
            self.compact.hide()
        if self.window is not None and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            return
        self.window = tk.Toplevel(self.app.root)
        self.window.title("Kömür — komut geçmişi ve ayarlar")
        self.window.geometry("640x560")
        self.window.minsize(520, 420)
        body = ttk.Frame(self.window, padding=12)
        body.pack(fill="both", expand=True)
        tabs = ttk.Notebook(body)
        tabs.pack(fill="both", expand=True)
        history_page = ttk.Frame(tabs, padding=6)
        self.settings_page = ttk.Frame(tabs, padding=10)
        tabs.add(history_page, text="Komut geçmişi")
        tabs.add(self.settings_page, text="Ayarlar")
        self.history = tk.Text(history_page, wrap="word", font=("Segoe UI", 11), state="disabled", height=12)
        scroll = ttk.Scrollbar(history_page, command=self.history.yview)
        self.history.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.history.pack(fill="both", expand=True, pady=8)
        tools = ttk.Frame(history_page)
        tools.pack(fill="x", pady=(0, 4))
        self.history_query = tk.StringVar()
        ttk.Entry(tools, textvariable=self.history_query).pack(side="left", fill="x", expand=True)
        ttk.Button(tools, text="Geçmişte ara", command=self.search_history).pack(side="left", padx=4)
        self.clear_button = ttk.Button(tools, text="Geçmişi temizle", command=self.clear_history)
        self.clear_button.pack(side="left")
        self.entry = ttk.Entry(history_page, font=("Segoe UI", 11))
        self.entry.pack(fill="x")
        self.entry.bind("<Return>", lambda event: self.send())
        self.send_button = ttk.Button(history_page, text="Gönder", command=self.send)
        self.send_button.pack(anchor="e", pady=5)
        settings_ui.build_settings_page(self)
        ttk.Button(history_page, text="Küçük kutuya dön", command=self.back_to_compact).pack(anchor="e")
        for speaker, text in self.chat_log:
            self.write_history(speaker, text)
        if not self.chat_log:
            self.append("Kömür", "Komut yaz: 'not defterini aç', 'sesi %30 yap', '5 dakika sonra mola hatırlat' veya 'yerde yuvarlan'.")
        self.set_busy(self.busy)
        self.entry.focus_set()

    def manage_memory(self):
        return settings_ui.manage_memory(self)

    def set_habit_enabled(self):
        return settings_ui.set_habit_enabled(self)

    def set_accessory(self, label):
        return settings_ui.set_accessory(self, label)

    def set_activity_level(self, label):
        return settings_ui.set_activity_level(self, label)

    def set_history_enabled(self):
        return settings_ui.set_history_enabled(self)

    def set_activity_enabled(self):
        return settings_ui.set_activity_enabled(self)

    def append(self, speaker, text):
        self.chat_log.append((speaker, text))
        if self.memory and self.app.settings.get("history_enabled") and speaker in ("Sen", "Kömür"):
            try:
                self.memory.add_message("user" if speaker == "Sen" else "assistant", text)
            except (OSError, sqlite3.Error):
                logging.exception("Could not persist conversation")
        self.write_history(speaker, text)
        if self.compact is not None:
            self.compact.refresh()

    def search_history(self):
        if not self.memory:
            return
        self.history.configure(state="normal")
        self.history.delete("1.0", "end")
        self.history.configure(state="disabled")
        for row in self.memory.messages(query=self.history_query.get().strip()):
            self.write_history("Sen" if row["role"] == "user" else "Kömür", row["content"])

    def clear_history(self):
        if self.busy or not self.memory:
            return
        self.set_busy(True)
        try:
            if not messagebox.askyesno("Yerel hafızayı temizle", "Bu bilgisayardaki sohbet geçmişi, kaydedilmiş notlar ve öğrenilen alışkanlıklar silinsin mi? Hatırlatıcılar korunacak.", parent=self.window):
                return
            self.memory.clear_conversation()
            self.commands.reset()
            self.chat_log.clear()
            self.history.configure(state="normal")
            self.history.delete("1.0", "end")
            self.history.configure(state="disabled")
            if self.compact is not None:
                self.compact.refresh()
        finally:
            self.set_busy(False)

    def clear_reminders(self):
        if self.busy:
            return
        self.set_busy(True)
        try:
            if not messagebox.askyesno("Hatırlatıcılar", "Bekleyen tüm hatırlatıcılar iptal edilsin mi?", parent=self.window):
                return
            if self.memory:
                self.memory.cancel_reminders()
            self.actions.timers.clear()
        finally:
            self.set_busy(False)

    def back_to_compact(self):
        self.window.withdraw()
        self.show()

    def approve_action(self, pending):
        parent = self.window if self.window and self.window.winfo_exists() else self.app.root
        return messagebox.askyesno("Kömür — işlem onayı", pending.description, parent=parent)

    def write_history(self, speaker, text):
        if self.window is not None and self.window.winfo_exists():
            self.history.configure(state="normal")
            self.history.insert("end", f"{speaker}: {text}\n\n")
            self.history.configure(state="disabled")
            self.history.see("end")

    def send(self):
        text = self.entry.get().strip()
        if self.send_text(text):
            self.entry.delete(0, "end")

    def send_text(self, text):
        if not text or self.busy:
            return False
        self.append("Sen", text)
        command = parse_focus_command(text)
        if command:
            self.append("Kömür", self.app.handle_focus_command(command))
            return True
        self.submit(self.commands.respond, text)
        return True

    def respond_streaming(self, text, token):
        """Worker iş parçacığı: parçaları yalnız kuyruğa koyar; Tk'ye tick() dokunur."""
        return self.ai.respond(text, on_delta=lambda piece: self.delta_events.put((token, piece)))

    def drain_deltas(self):
        """Ana iş parçacığı: eski/iptal edilmiş isteklerin parçalarını at, geçerlileri baloncuğa yansıt."""
        changed = False
        while True:
            try:
                token, piece = self.delta_events.get_nowait()
            except queue.Empty:
                break
            if token != self._stream_id or self._cancel_requested or self.closed:
                continue
            self._partial = "" if piece is None else (self._partial + piece)[-2000:]
            changed = True
        if changed and self.compact is not None:
            self.compact.set_partial(self._partial)

    def clear_partial(self):
        self._partial = ""
        if self.compact is not None:
            self.compact.set_partial("")

    def tick(self, now):
        if self.closed:
            return
        if self.compact_visible:
            self.compact.update_position()
        while not self.behavior_requests.empty():
            self.app.command(self.behavior_requests.get_nowait())
        if self.app.settings.get("activity_context"):
            self.tracker.sample(now)
            self.context_text = self.tracker.summary(now)
            gaming = self.app.settings.get("focus_mode", True) and getattr(getattr(self.app, 'activity_reactions', None), 'current', None) == 'gaming'
            if not gaming and not self.busy and self.app.brain.state != "sleep" and now >= self.app.message_until:
                event = self.tracker.suggest_remark(now)
                if event:
                    self.submit(self.commands.comment_on_context, event, kind="comment")
        else:
            self.context_text = "Etkinlik paylaşımı kapalı."
        for timer in list(self.actions.timers):
            if now >= timer["due"]:
                self.actions.timers.remove(timer)
                self.app.say(timer["label"], 15)
                self.append("Hatırlatma", timer["label"])
                if self.memory and timer.get("memory_id"):
                    next_due = self.memory.complete_reminder(timer["memory_id"])
                    if next_due:
                        self.actions.timers.append({**timer, 'due': now + max(0, next_due - time.time())})
        if self.updates is not None:
            self.updates.poll(now)
            status_label = getattr(self, "update_status", None)
            if status_label is not None and status_label.winfo_exists() and status_label.cget("text") != self.updates.status:
                status_label.configure(text=self.updates.status)
        if (now - self._habit_check >= 600 and not self.busy and self.app.brain.state != "sleep"
                and getattr(getattr(self.app, "activity_reactions", None), "current", None) not in ("gaming", "meeting")):
            self._habit_check = now
            try:
                hint = self.commands.habit_suggestion()
            except Exception:  # noqa: BLE001
                logging.debug("habit suggestion failed", exc_info=True)
                hint = None
            if hint:
                self.app.say_unsolicited(hint, 10)
        try:
            kind, result = self.events.get_nowait()
        except queue.Empty:
            return
        if kind != "reply":
            self.set_busy(False)
        if kind == "reply":
            self.append("Kömür", result.reply)
            self.app.say(result.reply, max(8, min(30, 4 + len(result.reply) * .06)))
            approved = []
            for pending in result.needs_confirmation:   # onay sorulurken giriş kilitli kalır
                if self.approve_action(pending):
                    approved.append(pending)
                else:
                    self.append("Kömür", "İşlem iptal edildi.")
            self.set_busy(False)
            if approved:
                if result.remaining_actions and len(approved) == len(result.needs_confirmation) == 1:
                    self.submit(self.commands.confirm_and_continue, approved[0], result.remaining_actions)
                else:
                    self.submit(lambda: "\n".join(self.commands.confirm(p) for p in approved), kind="confirmed")
        elif result:
            self.append("Kömür", str(result))
            self.app.say(str(result), 12)

    def close(self):
        self.closed = True
        if self.compact is not None:
            self.compact.destroy()
