"""Geliştirici köprüsü: seçili depodaki commit'lere ve pytest sonuçlarına kedi tepkisi.

Yalnız yerel dosyalar okunur (.git/logs/HEAD ve .pytest_cache/v/cache/lastfailed);
ağa bir şey gitmez, hiçbir şey yazılmaz. Olaylar ``{"command", "message"}`` sözlükleridir.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from persona_dreams import GitTerminalWatcher

COMMIT_EVENT = {"event": "commit", "command": "dance",
                "message": "Yeni commit! Kutlama dansı! 🎉"}
TESTS_FAILED_EVENT = {"event": "tests_failed", "command": "hiss",
                      "message": "Fısss! {n} test patlamış, bug kokusu alıyorum!"}
TESTS_GREEN_EVENT = {"event": "tests_green", "command": "chirp",
                     "message": "Testler yeşile döndü! Mır mır! ✅"}


def find_repo_root(path: str | Path) -> Path | None:
    """``path`` ya da üst dizinlerinden .git içeren ilk dizin."""
    try:
        start = Path(path).resolve()
    except OSError:
        return None
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


class PytestWatcher:
    """pytest'in lastfailed önbelleğini izler; yalnız değişim anında olay üretir."""

    def __init__(self, root: Path):
        self.path = root / ".pytest_cache" / "v" / "cache" / "lastfailed"
        self._stamp: float | None = None
        self._failed: int | None = self._read_if_changed()   # açılış durumu taban, tepki yok

    def _read_if_changed(self) -> int | None:
        """Dosya değiştiyse başarısız test sayısını döndür (dosya yoksa 0), değişmediyse None."""
        try:
            stamp = self.path.stat().st_mtime
        except OSError:
            stamp = 0.0
        if stamp == self._stamp:
            return None
        self._stamp = stamp
        if not stamp:
            return 0
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return len(data) if isinstance(data, dict) else 0

    def poll(self) -> dict[str, Any] | None:
        count = self._read_if_changed()
        if count is None:
            return None
        previous, self._failed = self._failed, count
        if previous is None:
            return None
        if count > 0 and count != previous:
            event = dict(TESTS_FAILED_EVENT)
            event["message"] = event["message"].format(n=count)
            return event
        if count == 0 and previous > 0:
            return dict(TESTS_GREEN_EVENT)
        return None


class DevBridge:
    """Bir depo için commit + test izleyicisi. Depo yoksa sessizce boş döner."""

    def __init__(self, repo_path: str | Path | None = None):
        self.root: Path | None = None
        self._git: GitTerminalWatcher | None = None
        self._tests: PytestWatcher | None = None
        self.set_repo(repo_path or Path.cwd())

    def set_repo(self, repo_path: str | Path) -> bool:
        root = find_repo_root(repo_path)
        self.root = root
        if root is None:
            self._git = self._tests = None
            return False
        self._git = GitTerminalWatcher(repo_path=root)
        self._git.check_git()          # mevcut son commit'i taban al
        self._tests = PytestWatcher(root)
        return True

    def poll(self) -> list[dict[str, Any]]:
        if self.root is None:
            return []
        events = []
        if self._git is not None and self._git.check_git() is not None:
            events.append(dict(COMMIT_EVENT))
        if self._tests is not None:
            test_event = self._tests.poll()
            if test_event is not None:
                events.append(test_event)
        return events
