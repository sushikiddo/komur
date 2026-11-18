"""Masaüstü oyuncakları: seken iplik yumağı, süt kasesi, tırmalama tahtası.

Her oyuncak kendi küçük saydam penceresindedir (kedi penceresinin dışında da görünür).
``YarnPhysics`` ve ``ToyBrain`` saf mantıktır (Tk yok, test edilir); ``ToyBox`` pencereleri yönetir.
Ekran koordinatları piksel, y aşağı doğru artar.
"""
from __future__ import annotations

import math
import random
import time
import tkinter as tk

GRAVITY = 1800.0
BOUNCE = 0.55            # zemine/kenara çarpınca hızın korunan oranı
ROLL_FRICTION = 0.985    # yerde yuvarlanırken kare başı yatay sönüm (60 FPS'e göre)
REST_SPEED = 12.0
SIZES = {"yarn": (36, 36), "bowl": (72, 34), "post": (46, 112), "box": (110, 60)}
LABELS = {"yarn": "İplik yumağı", "bowl": "Süt kasesi", "post": "Tırmalama tahtası", "box": "Karton kutu"}


class YarnPhysics:
    """Yerçekimli, sekip yuvarlanan top. ``platforms``: (left, top, right) üst kenarlar (pencere tepeleri)."""

    def __init__(self, x, y, radius=18.0):
        self.x, self.y, self.r = float(x), float(y), radius
        self.vx = self.vy = 0.0
        self.angle = 0.0
        self.resting = False

    def push(self, vx, vy):
        self.vx, self.vy = float(vx), float(vy)
        self.resting = False

    def step(self, dt, area, platforms=()):
        """``area``: (left, top, right, bottom) çalışma alanı. Hareket ettiyse True."""
        if self.resting:
            return False
        left, top, right, bottom = area
        prev_bottom = self.y + self.r
        self.vy += GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        floor = bottom
        if self.vy > 0:   # düşerken yalnız üstünden geçtiği pencere kenarına konar
            for p_left, p_top, p_right in platforms:
                if p_left <= self.x <= p_right and prev_bottom <= p_top <= self.y + self.r:
                    floor = min(floor, p_top)
        if self.y + self.r >= floor:
            self.y = floor - self.r
            self.vy = -self.vy * BOUNCE if abs(self.vy) > 120 else 0.0
            self.vx *= ROLL_FRICTION ** max(1.0, dt * 60)
        if self.x - self.r < left or self.x + self.r > right:
            self.x = min(max(self.x, left + self.r), right - self.r)
            self.vx = -self.vx * BOUNCE
        self.y = max(self.y, top + self.r)
        self.angle = (self.angle + self.vx * dt / self.r) % (2 * math.pi)
        if self.vy == 0.0 and abs(self.vx) < REST_SPEED:
            self.vx = 0.0
            self.resting = True
        return True


class ToyBrain:
    """Kedinin oyuncaklara karşı kararları. Olaylar: {"action": "go"|"bat"|"drink"|"scratch"|"box", ...}."""

    BAT_RANGE = 70.0
    PLAY_WINDOW = 25.0        # kullanıcı yumağı attıktan sonra kedinin ilgilendiği süre
    INTEREST_WINDOW = 45.0    # kase/tahta/kutu konunca kedinin hemen gidip kullandığı süre
    DRINK_HUNGER = 55.0
    DRINK_COOLDOWN = 300.0
    SCRATCH_EVERY = 180.0
    DRINK_EVERY = 420.0
    BOX_EVERY = 300.0
    BOX_STAY = (20.0, 40.0)
    GO_COOLDOWN = 4.0
    REACH = {"bowl": 60.0, "post": 60.0, "box": 30.0}

    def __init__(self):
        self.play_until = 0.0
        self._last_bat = self._last_go = float("-inf")
        self._last_drink = float("-inf")
        self.interest = {}       # kind -> ilgi penceresi bitişi
        self.last_use = {}       # kind -> son kullanım/konma zamanı

    def user_threw(self, now):
        self.play_until = now + self.PLAY_WINDOW

    def user_placed(self, kind, now):
        """Kullanıcı oyuncağı koydu/bıraktı: kedi birkaç saniye içinde gidip kullansın."""
        self.interest[kind] = now + self.INTEREST_WINDOW
        self.last_use[kind] = now

    def decide(self, now, cat_center, cat_idle, hunger, toys):
        """``toys``: {kind: (cx, bottom)}. En fazla bir olay döner."""
        cx, cy = cat_center
        if "yarn" in toys and now < self.play_until:
            yx, yb = toys["yarn"]
            if math.hypot(yx - cx, (yb - 18) - cy) <= self.BAT_RANGE and now - self._last_bat > 1.2:
                self._last_bat = now
                direction = 1.0 if yx >= cx else -1.0
                return {"action": "bat", "vx": direction * 520.0, "vy": -620.0}
            if cat_idle and now - self._last_go > self.GO_COOLDOWN:
                self._last_go = now
                return {"action": "go", "kind": "yarn", "target": toys["yarn"]}
        for kind, action in (("bowl", "drink"), ("post", "scratch"), ("box", "box")):
            if kind in toys and self._due(kind, now, hunger):
                event = self._approach(kind, toys, now, cx, cy, cat_idle, action)
                if event:
                    return event
        return None

    def _due(self, kind, now, hunger):
        if now < self.interest.get(kind, 0.0):
            return True
        last = self.last_use.setdefault(kind, now)
        if kind == "bowl" and hunger >= self.DRINK_HUNGER and now - self._last_drink > self.DRINK_COOLDOWN:
            return True
        every = {"bowl": self.DRINK_EVERY, "post": self.SCRATCH_EVERY, "box": self.BOX_EVERY}[kind]
        return now - last > every

    def _approach(self, kind, toys, now, cx, cy, cat_idle, action):
        tx, tb = toys[kind]
        if abs(tx - cx) <= self.REACH[kind] and abs(tb - cy) <= 200:
            self.interest[kind] = 0.0
            self.last_use[kind] = now
            if action == "drink":
                self._last_drink = now
            event = {"action": action, "kind": kind}
            if action == "box":
                event["stay"] = random.uniform(*self.BOX_STAY)
            return event
        if cat_idle and now - self._last_go > self.GO_COOLDOWN:
            self._last_go = now
            return {"action": "go", "kind": kind, "target": toys[kind]}
        return None


class _ToyWindow:
    def __init__(self, master, kind, x, y, on_throw):
        from window_utils import BG, make_transparent
        self.kind = kind
        self.w, self.h = SIZES[kind]
        self.x, self.y = float(x), float(y)      # pencere sol-üst
        self.win = tk.Toplevel(master)
        make_transparent(self.win)
        self.canvas = tk.Canvas(self.win, width=self.w, height=self.h, bg=BG, highlightthickness=0)
        self.canvas.pack()
        self._drag = None
        self.falling = False
        self.vy = 0.0
        self._on_throw = on_throw
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.draw(0.0)
        # İlk konum geometry ile: harita öncesi SetWindowPos henüz çerçeve penceresini bulamaz.
        self.win.geometry(f"{self.w}x{self.h}+{round(self.x)}+{round(self.y)}")

    def place(self):
        from window_utils import place_window
        place_window(self.win, self.x, self.y, self.w, self.h)

    def draw(self, angle):
        c = self.canvas
        c.delete("all")
        if self.kind == "yarn":
            c.create_oval(2, 2, 34, 34, fill="#d64545", outline="#8e2020", width=2)
            for k in range(3):
                a = angle + k * math.pi / 3
                dx, dy = math.cos(a) * 14, math.sin(a) * 14
                c.create_line(18 - dx, 18 - dy, 18 + dx, 18 + dy, fill="#f08a8a", width=2, smooth=True)
        elif self.kind == "bowl":
            c.create_oval(4, 4, 68, 16, fill="#fbfbf6", outline="#9aa5b1", width=2)
            c.create_polygon(4, 10, 68, 10, 58, 32, 14, 32, fill="#4f7cac", outline="#2f4f73", width=2)
        elif self.kind == "box":
            c.create_rectangle(3, 14, 107, 58, fill="#c89b5c", outline="#8a6234", width=2)
            c.create_rectangle(1, 8, 109, 20, fill="#d9ae70", outline="#8a6234", width=2)
            c.create_rectangle(46, 8, 64, 30, fill="#e8d3a6", outline="#b09660")
            c.create_line(10, 38, 100, 38, fill="#a97f45")
            c.create_text(55, 47, text="KÖMÜR", fill="#7a5428", font=("Segoe UI", 8, "bold"))
        else:
            c.create_rectangle(4, 100, 42, 110, fill="#8a5a33", outline="#5c3a1e", width=2)
            c.create_rectangle(15, 4, 31, 100, fill="#d9b779", outline="#9c7b45", width=2)
            for yy in range(12, 96, 9):
                c.create_line(15, yy, 31, yy + 5, fill="#9c7b45")

    def _press(self, event):
        self.falling = False
        self._drag = [(time.monotonic(), event.x_root, event.y_root)]

    def _motion(self, event):
        if self._drag is None:
            return
        last = self._drag[-1]
        self.x += event.x_root - last[1]
        self.y += event.y_root - last[2]
        self._drag = (self._drag + [(time.monotonic(), event.x_root, event.y_root)])[-4:]
        self.place()

    def _release(self, event):
        samples, self._drag = self._drag or [], None
        if len(samples) >= 2:
            (t0, x0, y0), (t1, x1, y1) = samples[0], samples[-1]
            span = max(t1 - t0, 0.016)
            self._on_throw(self, (x1 - x0) / span, (y1 - y0) / span)
        else:
            self._on_throw(self, 0.0, 0.0)

    def destroy(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


class ToyBox:
    """Oyuncak pencerelerini, yumak fiziğini ve kedi kararlarını tek döngüde yürütür."""

    def __init__(self, master):
        self.master = master
        self.toys: dict[str, _ToyWindow] = {}
        self.yarn: YarnPhysics | None = None
        self.brain = ToyBrain()
        self.visible = True
        self.box_until = 0.0
        self._lift_at = 0.0

    def has(self, kind):
        return kind in self.toys

    def toggle(self, kind, x, y):
        """Oyuncağı koy/kaldır; konduysa True."""
        if kind in self.toys:
            self.toys.pop(kind).destroy()
            if kind == "yarn":
                self.yarn = None
            if kind == "box":
                self.box_until = 0.0
            return False
        w, h = SIZES[kind]
        toy = _ToyWindow(self.master, kind, x - w / 2, y - h, self._on_throw)
        self.toys[kind] = toy
        if kind == "yarn":
            self.yarn = YarnPhysics(x, y - h / 2, radius=w / 2)
            self.yarn.push(-260.0, -500.0)
            self.brain.user_threw(time.monotonic())
        else:
            self.brain.user_placed(kind, time.monotonic())
            toy.falling = True      # havada kalmasın: zemine düşsün
        return True

    def anchors(self):
        """{kind: (merkez x, alt y)} ekran koordinatları."""
        return {k: (t.x + t.w / 2, t.y + t.h) for k, t in self.toys.items()}

    def _on_throw(self, toy, vx, vy):
        if toy.kind == "yarn" and self.yarn is not None:
            self.yarn.x, self.yarn.y = toy.x + toy.w / 2, toy.y + toy.h / 2
            self.yarn.push(max(-1600, min(1600, vx)), max(-1600, min(1600, vy)))
            self.brain.user_threw(time.monotonic())
        elif toy.kind != "yarn":
            toy.falling = True
            toy.vy = 0.0
            self.brain.user_placed(toy.kind, time.monotonic())

    def set_visible(self, visible):
        if visible == self.visible:
            return
        self.visible = visible
        for toy in self.toys.values():
            (toy.win.deiconify if visible else toy.win.withdraw)()

    def _fall_static(self, dt, ground_y):
        for toy in self.toys.values():
            if toy.kind == "yarn" or not toy.falling or toy._drag is not None:
                continue
            toy.vy += GRAVITY * dt
            toy.y += toy.vy * dt
            if toy.y + toy.h >= ground_y:
                toy.y, toy.vy, toy.falling = ground_y - toy.h, 0.0, False
            toy.place()

    def _update_box(self, now, event):
        toy = self.toys.get("box")
        if toy is None:
            return
        if event and event["action"] == "box":
            self.box_until = now + event.get("stay", 25.0)
            self._lift_at = 0.0
        if now < self.box_until:
            if now >= self._lift_at:       # kutu kedinin önüne geçsin: alt gövde kutunun içinde kalır
                toy.win.lift()
                self._lift_at = now + 1.0
        elif self.box_until:
            self.box_until = 0.0
            try:
                self.master.lift()          # çıkınca kedi yine önde
            except tk.TclError:
                pass

    def step(self, dt, now, area, platforms, cat_center, cat_idle, hunger):
        """Yumağı ilerlet, pencereleri taşı; kedi için en fazla bir olay döndür."""
        self._fall_static(dt, area[3])
        if self.yarn is not None and "yarn" in self.toys:
            toy = self.toys["yarn"]
            if toy._drag is None and self.yarn.step(dt, area, platforms):
                toy.x, toy.y = self.yarn.x - toy.w / 2, self.yarn.y - toy.h / 2
                toy.place()
                toy.draw(self.yarn.angle)
        event = self.brain.decide(now, cat_center, cat_idle, hunger, self.anchors())
        if event and event["action"] == "bat" and self.yarn is not None:
            self.yarn.push(event["vx"], event["vy"])
        self._update_box(now, event)
        return event

    def close(self):
        for toy in self.toys.values():
            toy.destroy()
        self.toys.clear()
        self.yarn = None
