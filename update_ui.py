"""GitHub güncelleme akışı: arka planda kontrol/indirme, Tk işleri yalnız ana iş parçacığında (poll)."""
from __future__ import annotations

import logging
import queue
import tempfile
import threading
import time
from tkinter import messagebox

import updater
from version import APP_VERSION

STARTUP_DELAY = 30.0   # açılıştan sonra sessiz kontrol için bekleme (sn)


class UpdateFlow:
    def __init__(self, app, started=None):
        self.app = app
        self.info: updater.UpdateInfo | None = None
        self.busy = False
        self._events: queue.Queue = queue.Queue()
        self._started = time.monotonic() if started is None else started
        self._auto_done = False
        self.status = f"Sürüm {APP_VERSION}"

    # -- background work --------------------------------------------------
    def _run(self, kind, work):
        def target():
            try:
                self._events.put((kind, work()))
            except Exception as error:  # noqa: BLE001 - shown to the user, never crashes the app
                logging.info("update %s failed: %s", kind, type(error).__name__)
                self._events.put(("error:" + kind, error))
        self.busy = True
        threading.Thread(target=target, daemon=True).start()

    def check(self, silent=False):
        if self.busy:
            return
        self.status = "Güncellemeler denetleniyor…"
        self._run("silent" if silent else "check", updater.check_latest)

    def install(self):
        """Kullanıcı onayıyla indir, SHA-256 doğrula, kurulum sihirbazını aç ve uygulamayı kapat."""
        if self.busy or self.info is None:
            return
        info = self.info
        size = f" (~{info.size // (1024 * 1024)} MB)" if info.size else ""
        if not messagebox.askyesno("Kömür güncellemesi",
                                   f"Kömür {info.version} indirilsin ve kurulum sihirbazı açılsın mı?{size}\n\n"
                                   "Dosya GitHub'dan (sushikiddo/komur) indirilir ve SHA-256 ile doğrulanır. "
                                   "Kurulum imzasız olduğu için Windows uyarı gösterebilir. Kömür kurulumdan önce kapanır."):
            return
        self.status = "İndiriliyor…"
        self._run("download", lambda: updater.download_verified(info, tempfile.mkdtemp(prefix="komur-update-")))

    # -- main thread ------------------------------------------------------
    def poll(self, now=None):
        now = time.monotonic() if now is None else now
        if (not self._auto_done and now - self._started >= STARTUP_DELAY):
            self._auto_done = True
            if self.app.settings.get("update_check", True) and \
                    updater.should_check(self.app.settings.get("update_last_check"), time.time()):
                self.check(silent=True)
        try:
            kind, result = self._events.get_nowait()
        except queue.Empty:
            return
        self.busy = False
        if kind in ("check", "silent"):
            self.app.settings.set("update_last_check", time.time())   # yalnız başarılı denetim sayılır
            self.info = result
            if result is None:
                self.status = f"Kömür güncel (sürüm {APP_VERSION})."
                if kind == "check":
                    self.app.say("Güncelim, yeni sürüm yok.", 6)
            else:
                self.status = f"Yeni sürüm hazır: {result.version}"
                self.app.say(f"Kömür {result.version} çıktı! Ayarlar'dan güncelleyebilirsin.", 12)
        elif kind == "download":
            try:
                updater.launch_installer(result)
            except OSError as error:
                self.status = f"Kurulum başlatılamadı: {type(error).__name__}"
                return
            self.app.close()
        else:  # error:*
            message = str(result) if isinstance(result, updater.UpdateError) else "Bağlantı kurulamadı."
            self.status = f"Güncelleme hatası: {message}"
            if kind != "error:silent":
                self.app.say(self.status, 8)
