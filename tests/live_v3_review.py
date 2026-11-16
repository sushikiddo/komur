"""Explicit live check using generated notes and an owned test window only."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai import CatAI
from memory_store import MemoryStore
from pc_actions import PCActions, ActionSpec, PendingAction
from screen_assist import ScreenAssist
from settings import Settings


def find_window(pid):
    windows = []
    user = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, unused):
        found = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(found))
        if found.value == pid and user.IsWindowVisible(hwnd):
            text = ctypes.create_unicode_buffer(512)
            user.GetWindowTextW(hwnd, text, len(text))
            if text.value == "Komur Screen Test":
                windows.append(int(hwnd))
        return True
    user.EnumWindows(callback_type(visit), 0)
    return windows[0] if windows else None


def main():
    report = {}
    with tempfile.TemporaryDirectory(prefix="komur-v3-live-") as folder:
        memory = MemoryStore(Path(folder) / "memory.db")
        memory.remember("Kullanıcının adı Deniz. En sevdiği renk yeşil.")
        memory = MemoryStore(Path(folder) / "memory.db")
        actions = PCActions()
        actions.register(ActionSpec("recall_memories", "Kaydedilmiş yerel notları ara",
                                    {"properties": {"query": {"type": "string"}}, "required": ["query"]}, memory.recall))
        ai = CatAI(Settings({"ai_backend": "local"}).get, actions, lambda: {"summary": memory.context(), "screen_shared": False})
        reply = ai.respond("Neler hatırlıyorsun?")
        report["memory"] = {"backend": reply.backend, "reply": reply.reply, "error": reply.error}
        assert "Deniz" in reply.reply and reply.backend == "Yerel model (Ollama)"
        result_path = Path(folder) / "clicked.txt"
        proc = subprocess.Popen(["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File",
                                 str(Path(__file__).with_name("screen_fixture_v3.ps1")), "-ResultPath", str(result_path)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        hwnd = None
        try:
            deadline = time.monotonic() + 15
            while not hwnd and time.monotonic() < deadline:
                hwnd = find_window(proc.pid)
                time.sleep(.1)
            assert hwnd, "Owned fixture did not start"
            screen = ScreenAssist()
            snapshot = screen.capture(hwnd)
            report["screen"] = {"title": snapshot["title"], "ocr": snapshot["ocr_text"], "error": snapshot["ocr_error"]}
            assert "271828" in snapshot["ocr_text"]
            reply = ai.explain_screen("Paylaştığım penceredeki test numarasını ve düğmenin adını söyle.", screen.context(snapshot))
            report["screen"]["reply"] = reply.reply
            assert "271828" in reply.reply
            snapshot = screen.capture(hwnd)
            actions.register(ActionSpec("screen_click", "Owned test button",
                {"properties": {"snapshot_id": {"type": "string"}, "target": {"type": "string"}},
                 "required": ["snapshot_id", "target"]},
                lambda snapshot_id, target: screen.click(snapshot_id, target, confirmed=True), dangerous=True))
            args = {"snapshot_id": snapshot["snapshot_id"], "target": "Example button"}
            pending = actions.execute("screen_click", args)
            assert isinstance(pending, PendingAction) and not result_path.exists()
            outcome = actions.execute("screen_click", args, confirmed=True)
            assert result_path.exists() and result_path.read_text() == "invoked", outcome
            report["click"] = {"approval_required": True, "result": outcome, "verified": True}
        finally:
            if hwnd:
                ctypes.windll.user32.PostMessageW(wintypes.HWND(hwnd), 0x0010, 0, 0)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=5)
    Path("live-v3-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
