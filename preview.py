"""Preview every animation side by side in one window (no transparency).

    python preview.py

Useful while tuning the renderer or trying skins: pass a skin name to recolor,
e.g. ``python preview.py zencefil``.
"""
import math
import sys
import tkinter as tk

from behavior import Bounds, CatBrain
from renderer import CatRenderer
import skins

CELL_W, CELL_H = 170, 190
COLS = 3
LABELS = {
    "wander": "Geziniyor", "sit": "Oturuyor", "look": "İzliyor", "groom": "Temizleniyor",
    "stretch": "Geriniyor", "sleep": "Uyuyor", "yawn": "Esniyor", "play": "Oynuyor",
    "follow": "Takip",
}


def main():
    skin = sys.argv[1] if len(sys.argv) > 1 else skins.DEFAULT_SKIN
    states = CatBrain.STATES
    rows = (len(states) + COLS - 1) // COLS
    root = tk.Tk()
    root.title("Kömür — animasyon önizlemesi")
    root.configure(bg="#cfd8dc")

    cells = []
    for i, state in enumerate(states):
        frame = tk.Frame(root, bg="#eceff1", bd=1, relief="solid")
        frame.grid(row=(i // COLS) * 2, column=i % COLS, padx=6, pady=(6, 0))
        tk.Label(root, text=LABELS.get(state, state), bg="#cfd8dc",
                 font=("Segoe UI", 9)).grid(row=(i // COLS) * 2 + 1, column=i % COLS)
        canvas = tk.Canvas(frame, width=CELL_W, height=CELL_H,
                           bg="#eceff1", highlightthickness=0)
        canvas.pack()
        renderer = skins.apply_skin(CatRenderer(canvas, CELL_W, CELL_H), skin)
        brain = CatBrain(Bounds(0, 0, 400, 400), seed=11)
        brain.state = state
        cells.append((brain, renderer, state))

    start = [None]

    def tick():
        import time
        if start[0] is None:
            start[0] = time.monotonic()
        t = time.monotonic() - start[0]
        for brain, renderer, state in cells:
            renderer.draw(brain, t, "")
        root.after(33, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
