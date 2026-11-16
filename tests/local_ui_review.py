"""Opt-in real GUI/local-AI review. Close using local-ui-review.stop."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cat
from settings import Settings

options = Settings({"ai_backend": "local", "sound": False, "activity_context": False})
options.save = lambda: None
cat.Settings.load = lambda: options
app = cat.DesktopCat()
app.assistant.show()
app.assistant.entry.insert(0, "Merhaba Kömür, bugün nasılsın?")
app.assistant.send()
deadline = time.monotonic() + 200


def poll():
    if Path("local-ui-review.stop").exists():
        app.close()
        return
    if not app.assistant.busy:
        Path("local-ui-review.json").write_text(json.dumps({
            "backend": app.assistant.ai.last_backend,
            "chat": app.assistant.chat_log,
            "window": [app.w, app.h],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    if time.monotonic() > deadline:
        app.close()
        return
    app.root.after(200, poll)


app.root.after(200, poll)
app.run()
