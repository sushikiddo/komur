"""Owned, static view of the actual compact chat widget; no microphone/capture."""
from pathlib import Path
import sys
from types import SimpleNamespace
import tkinter as tk
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_bubble import ChatBubble
from settings import Settings

root = tk.Tk()
root.withdraw()
settings = Settings()
settings.save = lambda: None
assistant = SimpleNamespace(
    app=SimpleNamespace(root=root, brain=SimpleNamespace(x=350, y=470), w=143, h=154, settings=settings),
    chat_log=[("Sen", "Merhaba Kömür!"), ("Kömür", "Buradayım. Yazabilir veya Konuş'a basabilirsin. Geçmiş düğmesinden eski konuşmalarına ulaşabilirsin.")],
    listening=False, show_history=lambda: None, toggle_listening=lambda: None, share_screen=lambda: None,
    set_voice_enabled=lambda value: None, send_text=lambda value: False, cancel_listening=lambda: None)
widget = ChatBubble(assistant)
widget.window.overrideredirect(False)
widget.show()
def poll():
    if Path("compact-visual-review.stop").exists():
        root.destroy()
    else:
        root.after(200, poll)
root.after(200, poll)
root.mainloop()
