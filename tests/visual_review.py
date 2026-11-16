"""Manual contact sheet; start from project root, close with visual-review.stop."""
import sys
from pathlib import Path
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from behavior import CatBrain, Bounds
from renderer import CatRenderer

root = tk.Tk()
root.title("Kömür — Görsel doğrulama")
root.configure(bg="#edf0f2")
states = ("sit", "play", "roll", "bored", "yawn", "sleep", "stretch", "wander")
for row, color in enumerate(("#edf0f2", "#31363c")):
    for column, state in enumerate(states):
        frame = tk.Frame(root, bg=color)
        frame.grid(row=row, column=column)
        tk.Label(frame, text=state, bg=color, fg="#141b20" if row == 0 else "#ffffff").pack()
        canvas = tk.Canvas(frame, width=143, height=154, highlightthickness=0, bg=color)
        canvas.pack()
        brain = CatBrain(Bounds(0, 0, 0, 0), width=143, height=154, seed=1)
        brain.state = state
        brain.elapsed = 2
        brain.pounce = .8
        CatRenderer(canvas, 143, 154).draw(brain, 2)

def poll():
    if Path("visual-review.stop").exists():
        root.destroy()
    else:
        root.after(200, poll)

root.after(200, poll)
root.mainloop()
