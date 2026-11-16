"""Opt-in live local-model and public-web verification; no PC mutations."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai import CatAI
from pc_actions import PCActions
from settings import Settings


class ReadOnlyActions(PCActions):
    def execute(self, name, args=None, confirmed=False):
        if name not in {"web_read", "web_research", "get_time", "system_info"}:
            return "Olmadı: canlı test yalnızca okuma işlemlerine izin verir."
        return super().execute(name, args, confirmed)


def main():
    ai = CatAI(Settings({"ai_backend": "local"}).get, ReadOnlyActions(), lambda: "Canlı test; etkinlik paylaşımı kapalı.")
    result = {"connection": ai.check_connection(), "turns": []}
    print(result["connection"], flush=True)
    for question in (
        "Merhaba Kömür. Kendini kısaca tanıt ve 2+2'nin sonucunu söyle.",
        "https://www.python.org/downloads/ sayfasını oku ve kaynak bağlantısıyla güncel Python sürümünü söyle.",
    ):
        start = time.monotonic()
        reply = ai.respond(question)
        item = {"question": question, "backend": reply.backend, "reply": reply.reply,
                "error": reply.error, "actions": reply.actions_done,
                "seconds": round(time.monotonic() - start, 2)}
        result["turns"].append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    Path("live-local-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    assert all(turn["backend"] == "Yerel model (Ollama)" for turn in result["turns"])
    assert "https://www.python.org" in result["turns"][1]["reply"]
    assert result["turns"][1]["actions"]
    assert "3.15.2" in result["turns"][1]["reply"]


if __name__ == "__main__":
    main()
