"""Capture owned Tk previews of the compact chat and activity reactions.

Run from the project root on a desktop session. Captures only the preview
windows created here; it does not inspect or capture other applications.
"""
from pathlib import Path
import sys
import time
import tkinter as tk
from types import SimpleNamespace

from PIL import ImageGrab

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from behavior import Bounds, CatBrain
from chat_bubble import ChatBubble
from renderer import CatRenderer
from settings import Settings

OUT = PROJECT / "docs" / "previews"
OUT.mkdir(parents=True, exist_ok=True)


def capture(window, destination):
    window.update_idletasks()
    window.update()
    time.sleep(0.35)
    window.update()
    x, y = window.winfo_rootx(), window.winfo_rooty()
    width, height = window.winfo_width(), window.winfo_height()
    if width <= 1 or height <= 1:
        raise RuntimeError(f"Preview window has invalid bounds: {width}x{height}")
    ImageGrab.grab(bbox=(x, y, x + width, y + height)).save(destination)


def chat_preview():
    root = tk.Tk()
    root.withdraw()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    settings = Settings()
    settings.save = lambda: None
    assistant = SimpleNamespace(
        app=SimpleNamespace(root=root,
                            brain=SimpleNamespace(x=sw // 2 - 70, y=sh // 2),
                            w=143, h=154, settings=settings),
        chat_log=[("Sen", "Merhaba Kömür!"),
                  ("Kömür", "Buradayım. Yazabilir veya Konuş'a basabilirsin.")],
        listening=False, show_history=lambda: None, toggle_listening=lambda: None,
        share_screen=lambda: None, share_clipboard=lambda: None, set_voice_enabled=lambda value: None,
        send_text=lambda value: False, cancel_listening=lambda: None,
        cancel_response=lambda: None)
    bubble = ChatBubble(assistant)
    bubble.window.overrideredirect(False)
    bubble.show()
    try:
        capture(bubble.window, OUT / "compact-chat-v4.png")
    finally:
        bubble.destroy()
        root.destroy()


def activity_preview():
    root = tk.Tk()
    root.title("Kömür — etkinlik tepkileri")
    root.configure(bg="#edf0f2")
    labels = (("Müzik", "music"), ("Video", "video"), ("Dinleniyor", "none"))
    for col, (label, reaction) in enumerate(labels):
        card = tk.Frame(root, bg="#edf0f2", padx=8, pady=8)
        card.grid(row=0, column=col, sticky="nsew")
        tk.Label(card, text=label, bg="#edf0f2", fg="#26313b",
                 font=("Segoe UI", 10, "bold")).pack(pady=(0, 4))
        canvas = tk.Canvas(card, width=180, height=194, bg="#edf0f2",
                           highlightthickness=0, borderwidth=0)
        canvas.pack()
        brain = CatBrain(Bounds(0, 0, 0, 0), width=180, height=194, seed=3)
        brain.state = "sit"
        brain.elapsed = 2
        brain.activity_reaction = reaction
        CatRenderer(canvas, 180, 194).draw(brain, 2)
    root.update_idletasks()
    root.geometry(f"{root.winfo_reqwidth()}x{root.winfo_reqheight()}+{max(0, root.winfo_screenwidth()//2-root.winfo_reqwidth()//2)}+{max(0, root.winfo_screenheight()//2-root.winfo_reqheight()//2)}")
    try:
        capture(root, OUT / "activity-v4.png")
    finally:
        root.destroy()


if __name__ == "__main__":
    chat_preview()
    activity_preview()
    print(f"Saved previews to {OUT}")
