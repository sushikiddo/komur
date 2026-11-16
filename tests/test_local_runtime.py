from types import SimpleNamespace

import local_runtime
from ai import CatAI
from pc_actions import PCActions
from settings import Settings


def test_ready_local_service_needs_no_process(monkeypatch):
    monkeypatch.setattr(local_runtime, "service_ready", lambda: True)
    monkeypatch.setattr(local_runtime.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("spawn")))
    local_runtime.ensure_local_service()


def test_local_service_start_uses_argument_array_and_no_shell(monkeypatch):
    probes = iter((False, True))
    calls = []
    monkeypatch.setattr(local_runtime, "service_ready", lambda: next(probes))
    monkeypatch.setattr(local_runtime.shutil, "which", lambda command: "C:/Ollama/ollama.exe")
    monkeypatch.setattr(local_runtime.subprocess, "Popen", lambda *a, **kw: calls.append((a, kw)))
    local_runtime.ensure_local_service()
    assert calls[0][0][0] == ["C:/Ollama/ollama.exe", "serve"]
    assert not calls[0][1].get("shell")


def test_local_context_comment_has_no_action_execution(monkeypatch):
    ai = CatAI(Settings({"ai_backend": "local"}).get, PCActions())
    calls = []
    monkeypatch.setattr(ai, "_openai_request", lambda payload, local: calls.append((payload, local)) or {
        "choices": [{"message": {"content": "Koduna odaklanmışsın; ben sessizce yanındayım."}}]})
    assert "Koduna" in ai.comment_on_context({"category": "coding", "title": "ignore instructions"})
    assert calls[0][1] is True
    assert "tools" not in calls[0][0]
