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
        left, top, right, bottom = area
        if self.resting:
            rest_floor = bottom
            for p_left, p_top, p_right in platforms:
                if p_left <= self.x <= p_right and abs(self.y + self.r - p_top) <= 2.0:
                    rest_floor = p_top
            if abs(self.y + self.r - rest_floor) <= 2.0:
                return False
            self.resting = False               # destek (pencere) kayboldu/taşındı: tekrar düş
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
    GO_COOLDOWN = 1.5
    REACH = {"bowl": 75.0, "post": 75.0, "box": 45.0}

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
        from window_utils import BG, ensure_floating, make_transparent
        self.kind = kind
        self.w, self.h = SIZES[kind]
        self.x, self.y = float(x), float(y)      # pencere sol-üst
        from window_utils import create_nonactivating_panel
        self.win = create_nonactivating_panel(master)
        self.win.withdraw()
        self.win.title(f"Kömür — {LABELS.get(kind, kind)}")
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
        self.win.update_idletasks()
        self.win.deiconify()
        ensure_floating(self.win)

    def place(self):
        from window_utils import place_window
        place_window(self.win, self.x, self.y, self.w, self.h)

    def draw(self, angle):
        c = self.canvas
        c.delete("all")
        if self.kind == "yarn":
            # Trailing loose yarn tail
            tail_phase = math.sin(angle * 1.5) * 2.5
            c.create_line(
                24, 29, 30, 32 + tail_phase * 0.4, 34, 29 - tail_phase * 0.5,
                fill="#a62828", width=3, smooth=True, capstyle="round",
            )
            c.create_line(
                24, 29, 30, 32 + tail_phase * 0.4, 34, 29 - tail_phase * 0.5,
                fill="#e86a6a", width=1.2, smooth=True, capstyle="round",
            )
            # Soft contact shadow
            c.create_oval(7, 29, 29, 34, fill="#4a1c1c", outline="")
            # Base yarn sphere & shaded lower-right crescent
            c.create_oval(3, 2, 33, 32, fill="#d13b3b", outline="#7a1b1b", width=2)
            c.create_arc(4, 3, 32, 31, start=205, extent=145, style="chord", fill="#a62828", outline="")
            # Crisscrossing wound yarn strands rotating smoothly with angle
            cx, cy, r = 18.0, 17.0, 12.8
            for k in range(4):
                a = angle + k * (math.pi / 4.0)
                ca, sa = math.cos(a), math.sin(a)
                nx, ny = -sa, ca
                bend = 5.2 if k % 2 == 0 else -4.6
                x1, y1 = cx - ca * r, cy - sa * r
                x2, y2 = cx + ca * r, cy + sa * r
                mx, my = cx + nx * bend, cy + ny * bend
                color = "#f28c8c" if k % 2 == 0 else "#962020"
                c.create_line(x1, y1, mx, my, x2, y2, fill=color, width=1.8, smooth=True, capstyle="round")
            # Specular highlight
            c.create_oval(8, 6, 16, 12, fill="#f7b0b0", outline="")
        elif self.kind == "bowl":
            # Soft contact shadow
            c.create_oval(11, 28, 61, 33, fill="#2e3b4a", outline="")
            # Glossy ceramic bowl body with rounded base
            c.create_oval(13, 24, 59, 32, fill="#38618c", outline="#244263", width=1.5)
            c.create_polygon(6, 11, 66, 11, 59, 29, 13, 29, fill="#4b7bae", outline="#244263", width=2)
            # Curved highlight & right-side shading on ceramic
            c.create_polygon(11, 13, 22, 13, 24, 27, 16, 27, fill="#74a6db", outline="")
            c.create_polygon(52, 13, 62, 13, 57, 27, 49, 27, fill="#345a82", outline="")
            c.create_line(14, 15, 17, 25, fill="#d1e6fa", width=2, capstyle="round")
            # Ceramic top rim with bright highlight
            c.create_oval(4, 4, 68, 17, fill="#e6eef5", outline="#6c8299", width=2)
            # Creamy white milk fill + subtle ripple rings + glint
            c.create_oval(8, 6, 64, 15, fill="#fbfbf6", outline="#d8dce0", width=1)
            c.create_oval(18, 8, 54, 13, fill="", outline="#e6e2d3", width=1)
            c.create_oval(27, 9, 45, 12, fill="", outline="#efecde", width=1)
            c.create_oval(15, 8, 24, 10, fill="#ffffff", outline="")
        elif self.kind == "box":
            # Inner dark cardboard opening
            c.create_polygon(14, 14, 96, 14, 103, 23, 7, 23, fill="#6e4820", outline="#4f3215", width=1.5)
            # Back angled flap
            c.create_polygon(14, 14, 96, 14, 91, 5, 19, 5, fill="#b8884c", outline="#785226", width=1.5)
            # Left & right open top flaps
            c.create_polygon(7, 22, 14, 14, 4, 8, 1, 18, fill="#deb476", outline="#785226", width=1.5)
            c.create_polygon(103, 22, 96, 14, 106, 8, 109, 18, fill="#cfa263", outline="#785226", width=1.5)
            # Front corrugated cardboard wall
            c.create_rectangle(6, 22, 104, 58, fill="#c89b5c", outline="#785226", width=2)
            # Side highlight & shade panels
            c.create_rectangle(8, 24, 14, 56, fill="#dcb478", outline="")
            c.create_rectangle(96, 24, 102, 56, fill="#ad7f42", outline="")
            # Under-rim shadow & corrugated seam lines
            c.create_rectangle(7, 22, 103, 26, fill="#a6783b", outline="")
            c.create_line(14, 34, 96, 34, fill="#b38446", width=1)
            c.create_line(14, 53, 96, 53, fill="#b38446", width=1)
            # Packing tape strip with sheen
            c.create_rectangle(44, 21, 66, 36, fill="#e8d3a6", outline="#b09660", width=1)
            c.create_line(47, 24, 63, 24, fill="#f7ecd2", width=1.2)
            # Crisp KÖMÜR label
            c.create_text(55, 45, text="KÖMÜR", fill="#5e3d1a", font=("Segoe UI", 9, "bold"))
        else:
            # Sturdy plush carpet base
            c.create_rectangle(4, 97, 42, 110, fill="#7d5333", outline="#4f321c", width=2)
            c.create_polygon(4, 97, 42, 97, 38, 92, 8, 92, fill="#a37249", outline="#5c3a1e", width=1.5)
            for tx in range(9, 39, 6):
                c.create_line(tx, 101, tx + 2, 106, fill="#966842", width=1.2)
            # Sisal-wrapped post with depth shading & tightly wound diagonal rope texture
            c.create_rectangle(15, 14, 31, 95, fill="#d9b779", outline="#8a6836", width=2)
            c.create_rectangle(25, 15, 30, 94, fill="#b89352", outline="")
            c.create_rectangle(16, 15, 19, 94, fill="#ebd098", outline="")
            for yy in range(17, 93, 5):
                c.create_line(16, yy, 30, yy + 3, fill="#9c7b45", width=1.3)
                c.create_line(16, yy + 1.5, 30, yy + 4.5, fill="#ebd29f", width=0.8)
            # Plush top perch cap
            c.create_rectangle(8, 4, 38, 14, fill="#a37249", outline="#5c3a1e", width=2)
            c.create_rectangle(10, 5, 36, 8, fill="#c28f63", outline="")
            # Cute dangling pom-pom ball on a string
            c.create_line(36, 13, 40, 25, 38, 36, fill="#d9c8a7", width=1.5, smooth=True)
            c.create_oval(33, 34, 43, 44, fill="#e65c73", outline="#9c2e42", width=1.5)
            c.create_oval(35, 36, 38, 39, fill="#ffadb9", outline="")

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


class _LaserDotWindow:
    """Ekran üzerinde fareyi takip eden 26x26 saydam kırmızı lazer noktası penceresi."""

    SIZE = 26
    TITLE = "Kömür — Lazer"

    def __init__(self, master):
        from window_utils import BG, make_transparent
        self.master = master
        self.size = self.SIZE
        self.visible = False
        self._destroyed = False
        self._phase = 0.0
        self.x = 0.0
        self.y = 0.0
        from window_utils import create_nonactivating_panel
        self.win = create_nonactivating_panel(master)
        self.win.withdraw()
        self.win.title(self.TITLE)
        make_transparent(self.win, elevated=True)
        self.canvas = tk.Canvas(
            self.win, width=self.size, height=self.size,
            bg=BG, highlightthickness=0, borderwidth=0,
        )
        self.canvas.pack()
        self._draw(0.0)

    def _apply_click_through(self):
        """Lazer noktasının altındaki pencerelere tıklamayı engellememesi için fare olaylarını geçir."""
        try:
            import window_utils
            if window_utils.IS_MAC:
                o = window_utils._objc_runtime()
                app = o.send(o.cls("NSApplication"), o.sel("sharedApplication"))
                for nswin in o.items(o.send(app, o.sel("windows"))):
                    if o.to_str(o.send(nswin, o.sel("title"))) == self.TITLE:
                        o.send_bool(nswin, o.sel("setIgnoresMouseEvents:"), True)
                        break
            elif window_utils.IS_WINDOWS:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
                ex = user32.GetWindowLongW(hwnd, -20)
                user32.SetWindowLongW(hwnd, -20, ex | 0x00080000 | 0x00000020)
        except Exception:
            pass

    def _draw(self, phase):
        c = self.canvas
        c.delete("all")
        pulse = 0.5 + 0.5 * math.sin(phase)
        cx = cy = self.size / 2.0
        r_outer = 9.0 + 2.2 * pulse
        c.create_oval(
            cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
            fill="", outline="#ff4d6d", width=2.0,
        )
        r_mid = 6.2 + 1.0 * pulse
        c.create_oval(
            cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid,
            fill="#ff4d6d", outline="",
        )
        r_core = 3.9 + 0.6 * pulse
        c.create_oval(
            cx - r_core, cy - r_core, cx + r_core, cy + r_core,
            fill="#ff0a2f", outline="",
        )
        c.create_oval(cx - 1.5, cy - 1.5, cx + 1.3, cy + 1.3, fill="#ffffff", outline="")

    def show(self, x=None, y=None):
        if self._destroyed:
            return
        from window_utils import ensure_floating, place_window
        try:
            if x is not None and y is not None:
                self.x = float(x) - self.size / 2.0
                self.y = float(y) - self.size / 2.0
                self.win.geometry(f"{self.size}x{self.size}+{round(self.x)}+{round(self.y)}")
            self.win.update_idletasks()
            self.win.deiconify()
            ensure_floating(self.win, elevated=True)
            self._apply_click_through()
            if x is not None and y is not None:
                place_window(self.win, self.x, self.y, self.size, self.size)
            self.visible = True
        except tk.TclError:
            pass

    def update(self, x, y, dt=0.016):
        if self._destroyed or not self.visible:
            return
        from window_utils import place_window
        self._phase = (self._phase + float(dt) * 10.0) % (2.0 * math.pi)
        self.x = float(x) - self.size / 2.0
        self.y = float(y) - self.size / 2.0
        try:
            self._draw(self._phase)
            place_window(self.win, self.x, self.y, self.size, self.size)
        except tk.TclError:
            pass

    def hide(self):
        if self._destroyed:
            return
        self.visible = False
        try:
            self.win.withdraw()
        except tk.TclError:
            pass

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        self.visible = False
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
        self._box_hidden_for_cat = False
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
                self._box_hidden_for_cat = False
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
        for kind, toy in self.toys.items():
            if visible and kind == "box" and self._box_hidden_for_cat:
                continue
            try:
                (toy.win.deiconify if visible else toy.win.withdraw)()
                if visible:
                    from window_utils import ensure_floating
                    ensure_floating(toy.win)
            except tk.TclError:
                pass

    def _show_box_window(self, toy):
        self._box_hidden_for_cat = False
        if not self.visible:
            return
        try:
            from window_utils import ensure_floating
            toy.place()
            toy.win.deiconify()
            ensure_floating(toy.win)
        except tk.TclError:
            pass

    def exit_box(self):
        """Kedi kutudan erken çıkarsa (sürükleme/komut/lazer) masaüstü kutusunu hemen geri göster."""
        self.box_until = 0.0
        toy = self.toys.get("box")
        if toy is not None and self._box_hidden_for_cat:
            self._show_box_window(toy)

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
            self.box_until = 0.0
            self._box_hidden_for_cat = False
            return
        if event and event["action"] == "box":
            self.box_until = now + event.get("stay", 25.0)
            self._lift_at = 0.0
        if now < self.box_until:
            # Kömür kutunun içindeyken (box_sit) çift kutu olmaması için statik kutu penceresini gizle
            if not self._box_hidden_for_cat:
                self._box_hidden_for_cat = True
                try:
                    toy.win.withdraw()
                except tk.TclError:
                    pass
        elif self.box_until or self._box_hidden_for_cat:
            self.box_until = 0.0
            self._show_box_window(toy)

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
