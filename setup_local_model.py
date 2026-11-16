"""Run once after installing Ollama: python setup_local_model.py."""
import json
import urllib.request
from local_runtime import ensure_local_service
from local_models import MODEL_PROFILES
from settings import Settings


def main():
    ensure_local_service()
    model = Settings.load().get("ai_local_model", "qwen2.5:7b")
    if model not in MODEL_PROFILES:
        raise ValueError("Kurulum yardımcısından onaylı bir yerel model seçin.")
    request = urllib.request.Request("http://127.0.0.1:11434/api/pull",
                                     data=json.dumps({"model": model, "stream": True}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    progress = -1
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=1800) as response:
        for line in response:
            event = json.loads(line)
            if event.get("error"):
                raise RuntimeError(event["error"])
            if event.get("total"):
                value = int(event.get("completed", 0) * 100 / event["total"]) // 5 * 5
                if value != progress:
                    progress = value
                    print(f"Model download: {value}%", flush=True)
            else:
                print(event.get("status", ""), flush=True)


if __name__ == "__main__":
    main()
