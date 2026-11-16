"""Read-only diagnostics checks with all machine I/O mocked."""
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import diagnostics


def test_health_report_is_concise_and_reports_local_read_only_status(monkeypatch):
    monkeypatch.setattr(diagnostics, "_ram_gb", lambda: 16)
    monkeypatch.setattr(diagnostics, "_ollama_installed", lambda: True)
    monkeypatch.setattr(diagnostics, "_ollama_tags", lambda: ["qwen2.5:7b"])
    monkeypatch.setattr(diagnostics, "config_dir", lambda: Path("missing") / "Komur")
    monkeypatch.setattr(diagnostics.shutil, "disk_usage",
                        lambda path: SimpleNamespace(free=8 * 1024 ** 3))
    voice = SimpleNamespace(status=lambda: {
        "stt_message": "Sesle yazma hazır.", "tts_message": "Türkçe ses hazır."})

    lines = diagnostics.health_report(voice)

    assert any("16.0 GB RAM" in line for line in lines)
    assert any("Yerel model önerisi" in line for line in lines)
    assert any("Ollama: çalışıyor" in line for line in lines)
    assert any("8.0 GB boş alan" in line for line in lines)
    assert sum(line.startswith("Ses:") for line in lines) == 2
    report = "\n".join(lines)
    assert "api_key" not in report.lower()
    assert "private" not in report.lower()


def test_ollama_probe_uses_bounded_loopback_request(monkeypatch):
    observed = {}

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, limit):
            observed["limit"] = limit
            return b'{"models": [{"name": "qwen3:4b"}]}'

    def fake_urlopen(url, timeout):
        observed.update(url=url, timeout=timeout)
        return Response()

    monkeypatch.setattr(diagnostics, "urlopen", fake_urlopen)
    assert diagnostics._ollama_tags() == ["qwen3:4b"]
    assert observed["url"] == "http://127.0.0.1:11434/api/tags"
    assert observed["timeout"] == 1
    assert observed["limit"] <= 1024 * 1024


def test_missing_services_and_unavailable_voice_are_reported_without_details(monkeypatch):
    monkeypatch.setattr(diagnostics, "_ram_gb", lambda: None)
    monkeypatch.setattr(diagnostics, "_ollama_installed", lambda: False)
    monkeypatch.setattr(diagnostics, "_ollama_tags", lambda: None)
    monkeypatch.setattr(diagnostics, "config_dir", lambda: Path("."))
    monkeypatch.setattr(diagnostics.shutil, "disk_usage",
                        lambda path: SimpleNamespace(free=1024 ** 3))
    voice = SimpleNamespace(status=lambda: (_ for _ in ()).throw(RuntimeError("secret details")))

    report = "\n".join(diagnostics.health_report(voice))

    assert "ölçülemedi" in report
    assert "kurulu görünmüyor" in report
    assert "durum bilgisi alınamadı" in report
    assert "secret details" not in report
