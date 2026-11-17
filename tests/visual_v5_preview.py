"""Render v5 renderer previews (accessories, night, popcorn) to docs/previews/v5/.
Needs Pillow + a desktop session; only captures the preview window created here."""
from pathlib import Path
import sys
import time
import tkinter as tk
from types import SimpleNamespace

from PIL import Image, ImageGrab

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from renderer import CatRenderer

OUT = PROJECT / "docs" / "previews" / "v5"
OUT.mkdir(parents=True, exist_ok=True)

CASES = [(s, a, tod, r) for s in ("sit",)
         for a, tod, r in ((None, "day", "none"), ("bow", "day", "none"), ("scarf", "day", "none"),
                           ("hat", "day", "none"), ("glasses", "day", "none"),
                           (None, "night", "none"), (None, "day", "video"), (None, "day", "music"))]

root = tk.Tk()
root.geometry("260x280+40+40")
root.attributes("-topmost", True)
root.lift()
root.focus_force()
canvas = tk.Canvas(root, width=260, height=280, bg="#8fb0c8", highlightthickness=0)
canvas.pack()
renderer = CatRenderer(canvas)
tiles = []
for state, acc, tod, reaction in CASES:
    brain = SimpleNamespace(state=state, facing=1, low_light=False, activity_reaction=reaction)
    renderer.draw(brain, 2.0, accessory=acc, time_of_day=tod)
    root.update_idletasks(); root.update(); root.lift(); time.sleep(0.25); root.update()
    x, y = canvas.winfo_rootx(), canvas.winfo_rooty()
    tiles.append(ImageGrab.grab(bbox=(x, y, x + 260, y + 280)))
cols = 4
sheet = Image.new("RGB", (260 * cols, 280 * (len(tiles) // cols)))
for i, tile in enumerate(tiles):
    sheet.paste(tile, ((i % cols) * 260, (i // cols) * 280))
sheet.save(OUT / "v5_sheet.png")
root.destroy()
print(OUT / "v5_sheet.png")
