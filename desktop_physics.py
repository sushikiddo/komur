"""Masaüstü fizik katmanı: pencere tünemesi, simge etkileşimi, görev çubuğu,
imleç uykusu, masaüstü eşyaları ve buharlaşan pati izleri.
"""
from __future__ import annotations

import ctypes
import math
from dataclasses import dataclass

import window_utils

try:
    from ctypes import wintypes
except ImportError:  # pragma: no cover
    wintypes = None

_UNSET = object()

ICON_SLOT_W = 80
ICON_SLOT_H = 90
ICON_MARGIN_X = 16
ICON_MARGIN_Y = 16


@dataclass
class Prop:
    kind: str
    x: float
    y: float
    width: float = 80.0
    height: float = 60.0
    active: bool = True


@dataclass(frozen=True)
class IconSlot:
    index: int
    x: int
    y: int
    w: int = ICON_SLOT_W
    h: int = ICON_SLOT_H


def _normalize_rect(rect):
    if rect is None:
        return None
    if hasattr(rect, "left") and hasattr(rect, "top"):
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    l, t, r, b = rect
    return (int(l), int(t), int(r), int(b))


def _probe_syslistview_icon_count():
    """Safely query desktop SysListView32 item count on Windows, or return None."""
    if not window_utils.IS_WINDOWS or wintypes is None:
        return None
    try:
        user32 = ctypes.windll.user32
        progman = user32.FindWindowW("Progman", None)
        defview = user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None) if progman else 0
        if not defview:
            found_defview = 0
            cb_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def enum_cb(hwnd, _lp):
                nonlocal found_defview
                dv = user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
                if dv:
                    found_defview = dv
                    return False
                return True

            user32.EnumWindows(cb_type(enum_cb), 0)
            defview = found_defview
        if not defview:
            return None
        listview = user32.FindWindowExW(defview, None, "SysListView32", None)
        if not listview:
            return None
        # LVM_GETITEMCOUNT = 0x1004
        count = int(user32.SendMessageW(listview, 0x1004, 0, 0))
        return count if count > 0 else None
    except (AttributeError, OSError):
        return None


def desktop_icon_grid(bounds=None, count=None):
    """Return desktop icon slots using SysListView32 count when available,
    falling back to standard left-edge 80x90px slots.
    """
    b = _normalize_rect(bounds) or (0, 0, 1920, 1080)
    left, top, right, bottom = b
    usable_h = max(ICON_SLOT_H, (bottom - top) - ICON_MARGIN_Y * 2)
    rows_per_col = max(1, usable_h // ICON_SLOT_H)

    if count is None:
        probed = _probe_syslistview_icon_count()
        count = min(probed, 24) if probed else min(rows_per_col, 8)

    slots = []
    for idx in range(max(0, int(count))):
        col = idx // rows_per_col
        row = idx % rows_per_col
        sx = left + ICON_MARGIN_X + col * ICON_SLOT_W
        sy = top + ICON_MARGIN_Y + row * ICON_SLOT_H
        if sx + ICON_SLOT_W <= right:
            slots.append(IconSlot(index=idx, x=sx, y=sy, w=ICON_SLOT_W, h=ICON_SLOT_H))
    return slots


class DesktopPhysics:
    """Masaüstü ortamı ile kedi arasındaki fizik ve etkileşim yöneticisi."""

    GRAVITY = 1800.0
    SHAKE_SPEED_THRESHOLD = 5000.0   # normal pencere sürükleme takip edilir, yalnız sert sallama düşürür
    CURSOR_IDLE_THRESHOLD = 120.0
    PAW_TRAIL_LIFETIME = 2.0
    PAW_TRAIL_STEP_DIST = 24.0
    LASER_CHASE_SPEED = 520.0
    TOAST_RUN_SPEED = 380.0
    CURSOR_MOVE_EPS = 2.0
    PROP_SNAP_RADIUS = 96.0
    JUMP_SECONDS = 0.4
    JUMP_HEIGHT = 70.0

    def __init__(self, cat_w=window_utils.WIDTH, cat_h=window_utils.HEIGHT, bounds=None):
        self.cat_w = float(cat_w)
        self.cat_h = float(cat_h)
        self.bounds = _normalize_rect(bounds) or (0, 0, 1920, 1080)

        self.x = float(self.bounds[0])
        self.y = float(self.bounds[3] - self.cat_h)
        self.vx = 0.0
        self.vy = 0.0

        self.surface = "ground"
        self.perched = False
        self.falling = False
        self.perch_rect = None
        self.perch_offset_x = 0.0
        self.perch_hwnd = None
        self._jump = None

        self.icon_peek = False
        self.icon_slap = False
        self.active_icon_index = None
        self.slapped_icons = {}

        self.toast_curious = False
        self.cursor_nap = False
        self.startled = False
        self.startle_timer = 0.0
        self.cursor_idle_time = 0.0
        self.last_pointer = None

        self.props = []
        self.active_prop = None
        self.in_box = False
        self.on_bed = False
        self.chasing_laser = False

        self.paw_trails = []
        self._last_paw_pos = None

    def _clamp_to_bounds(self, x, y, bounds):
        bl, bt, br, bb = bounds
        max_x = max(float(bl), float(br) - self.cat_w)
        max_y = max(float(bt), float(bb) - self.cat_h)
        return (
            max(float(bl), min(max_x, float(x))),
            max(float(bt), min(max_y, float(y))),
        )

    def _floor_y(self, bounds, taskbar_rect=None):
        _, _, _, bb = bounds
        if taskbar_rect is not None:
            return float(taskbar_rect[1]) - self.cat_h
        return float(bb) - self.cat_h

    def emit_paw_trail(self, x, y, facing=1):
        """Record a new paw trail entry at (x, y) with full alpha."""
        self.paw_trails.append({
            "x": float(x),
            "y": float(y),
            "alpha": 1.0,
            "facing": 1 if facing >= 0 else -1,
        })
        self._last_paw_pos = (float(x), float(y))

    def _update_paw_trails(self, dt, prev_x, prev_y, new_x, new_y, facing):
        fade = dt / self.PAW_TRAIL_LIFETIME
        kept = []
        for trail in self.paw_trails:
            alpha = trail["alpha"] - fade
            if alpha > 1e-6:
                trail["alpha"] = max(0.0, alpha)
                kept.append(trail)
        self.paw_trails = kept

        if not self.falling and math.hypot(new_x - prev_x, new_y - prev_y) > 0.5:
            foot_x = new_x + self.cat_w * 0.5
            foot_y = new_y + self.cat_h - 6.0
            if self._last_paw_pos is None or (
                math.hypot(foot_x - self._last_paw_pos[0], foot_y - self._last_paw_pos[1])
                >= self.PAW_TRAIL_STEP_DIST
            ):
                self.emit_paw_trail(foot_x, foot_y, facing)

    def _perch_y(self, window_top):
        """Target top-left y when perched on ``window_top``.

        Preserves exact ``window_top - cat_h`` whenever the cat fits inside the monitor's
        visible top bound; when a window sits directly under the macOS menu bar, clamps y
        so the cat perches visibly on top of the window's titlebar instead of off-screen.
        """
        raw = float(window_top) - self.cat_h
        min_top = float(self.bounds[1])
        if raw >= min_top:
            return raw
        return max(min_top - self.cat_h * 0.08, raw)

    def perch_on_window(self, window_rect, cat_x=None, hwnd=None, animate=False):
        """Jump onto the top edge of the given window rect (``hwnd`` kilitlenir; ``animate``: 0.4 sn zıplama yayı)."""
        rect = _normalize_rect(window_rect)
        if rect is None:
            return False
        wl, wt, wr, _ = rect
        target_x = self.x if cat_x is None else float(cat_x)
        max_x = max(float(wl), float(wr) - self.cat_w)
        target_x = max(float(wl), min(max_x, target_x))
        self._jump = None
        if animate:
            self._jump = {"t": 0.0, "dur": self.JUMP_SECONDS, "x0": self.x, "y0": self.y, "x1": target_x}
        else:
            self.x = target_x
            self.y = self._perch_y(wt)
        self.perch_hwnd = hwnd
        self.vx = 0.0
        self.vy = 0.0
        self.perched = True
        self.falling = False
        self.surface = "window_top"
        self.perch_rect = rect
        self.perch_offset_x = self.x - wl
        self.in_box = False
        self.on_bed = False
        return True

    def walk_on_taskbar(self, taskbar_rect, cat_x=None):
        """Place the cat on the top edge of the Windows taskbar."""
        rect = _normalize_rect(taskbar_rect)
        if rect is None:
            return False
        tl, tt, tr, _ = rect
        target_x = self.x if cat_x is None else float(cat_x)
        max_x = max(float(tl), float(tr) - self.cat_w)
        self.x = max(float(tl), min(max_x, target_x))
        self.y = float(tt) - self.cat_h
        self.vy = 0.0
        self.perched = False
        self.falling = False
        self.perch_rect = None
        self.surface = "taskbar"
        return True

    def peek_at_icon(self, icon_index=0, icons=None, bounds=None):
        """Peek out from behind a desktop icon slot."""
        slots = icons if icons is not None else desktop_icon_grid(bounds or self.bounds)
        if not slots or not (0 <= icon_index < len(slots)):
            return None
        slot = slots[icon_index]
        self.icon_peek = True
        self.icon_slap = False
        self.active_icon_index = slot.index
        self.perched = False
        self.falling = False
        self.surface = "ground"
        self.x = float(slot.x) + slot.w * 0.45
        self.y = float(slot.y) + max(0.0, slot.h - self.cat_h * 0.5)
        return slot

    def sit_on_icon(self, icon_index=0, icons=None, bounds=None):
        """Sit on top of a desktop icon slot."""
        slots = icons if icons is not None else desktop_icon_grid(bounds or self.bounds)
        if not slots or not (0 <= icon_index < len(slots)):
            return None
        slot = slots[icon_index]
        self.icon_peek = False
        self.icon_slap = False
        self.active_icon_index = slot.index
        self.perched = False
        self.falling = False
        self.surface = "icon"
        self.x = float(slot.x) + (slot.w - self.cat_w) * 0.5
        self.y = float(slot.y) - self.cat_h
        return slot

    def slap_icon(self, icon_index=0, icons=None, bounds=None):
        """Playfully slap a desktop icon, making it tilt and drop."""
        slots = icons if icons is not None else desktop_icon_grid(bounds or self.bounds)
        if not slots or not (0 <= icon_index < len(slots)):
            return None
        slot = slots[icon_index]
        self.icon_slap = True
        self.icon_peek = False
        self.active_icon_index = slot.index
        self.slapped_icons[slot.index] = {
            "dx": 8.0,
            "dy": 0.0,
            "vy": 0.0,
            "angle": 18.0,
            "timer": 2.5,
        }
        return self.slapped_icons[slot.index]

    def spawn_prop(self, kind, x, y):
        """Spawn a desktop prop ('bed' or 'laser') at (x, y). Kutu artık desktop_toys'ta."""
        norm_kind = str(kind).lower().strip()
        sizes = {
            "bed": (110.0, 56.0),
            "laser": (16.0, 16.0),
        }
        if norm_kind not in sizes:
            raise ValueError(f"Unsupported prop kind: {kind!r}")
        w, h = sizes[norm_kind]
        if norm_kind == "laser":
            self.props = [p for p in self.props if p.kind != "laser"]
            self.chasing_laser = True
        prop = Prop(kind=norm_kind, x=float(x), y=float(y), width=w, height=h, active=True)
        self.props.append(prop)
        self.active_prop = prop
        return prop

    def clear_props(self, kind=None):
        """Remove all props, or only props of a specific kind."""
        if kind is None:
            self.props.clear()
            self.active_prop = None
            self.in_box = False
            self.on_bed = False
            self.chasing_laser = False
            if self.surface == "bed":
                self.surface = "ground"
            return
        norm_kind = str(kind).lower().strip()
        self.props = [p for p in self.props if p.kind != norm_kind]
        if norm_kind == "laser":
            self.chasing_laser = False
        if norm_kind == "bed":
            self.on_bed = False
            if self.surface == "bed":
                self.surface = "ground"
        if self.active_prop is not None and self.active_prop.kind == norm_kind:
            self.active_prop = self.props[-1] if self.props else None

    def _update_slapped_icons(self, dt):
        expired = []
        for idx, state in self.slapped_icons.items():
            state["timer"] -= dt
            if state["timer"] <= 0:
                expired.append(idx)
                continue
            state["vy"] += 900.0 * dt
            state["dy"] = min(140.0, state["dy"] + state["vy"] * dt)
            state["angle"] = min(90.0, state["angle"] + 120.0 * dt)
        for idx in expired:
            del self.slapped_icons[idx]
        if not self.slapped_icons:
            self.icon_slap = False

    def _drop_from_perch(self):
        self.perched = False
        self.falling = True
        self.perch_rect = None
        self.perch_hwnd = None
        self._jump = None
        self.surface = "ground"
        self.vy = 0.0

    def _update_perch(self, dt, window_rect):
        new_rect = _normalize_rect(window_rect)
        if new_rect is None or self.perch_rect is None:
            self._drop_from_perch()
            return
        pl, pt, _, _ = self.perch_rect
        nl, nt, nr, _ = new_rect
        dx = nl - pl
        dy = nt - pt
        speed = math.hypot(dx, dy) / dt if dt > 0 else 0.0
        if speed > self.SHAKE_SPEED_THRESHOLD:
            self._drop_from_perch()
            self.startled = True
            self.startle_timer = max(self.startle_timer, 0.8)
            return
        max_x = max(float(nl), float(nr) - self.cat_w)
        self.perch_rect = new_rect
        jump = self._jump
        if jump is not None:
            jump["t"] += dt
            jump["x1"] = max(float(nl), min(max_x, jump["x1"] + dx))
            u = min(1.0, jump["t"] / jump["dur"])
            ty = self._perch_y(nt)
            self.x = jump["x0"] + (jump["x1"] - jump["x0"]) * u
            arc_y = jump["y0"] + (ty - jump["y0"]) * u - math.sin(math.pi * u) * self.JUMP_HEIGHT
            if float(nt) - self.cat_h < float(self.bounds[1]):
                arc_y = max(float(self.bounds[1]) - self.cat_h * 0.15, arc_y)
            self.y = arc_y
            if u >= 1.0:
                self._jump = None
                self.y = ty
            self.surface = "window_top"
            return
        self.x = max(float(nl), min(max_x, self.x + dx))
        self.y = self._perch_y(nt)
        self.surface = "window_top"

    def _update_cursor_nap(self, dt, pointer, bounds):
        if self.startle_timer > 0:
            self.startle_timer = max(0.0, self.startle_timer - dt)
            if self.startle_timer == 0.0:
                self.startled = False

        if pointer is None:
            return
        px, py = float(pointer[0]), float(pointer[1])
        if self.last_pointer is None:
            self.last_pointer = (px, py)
            self.cursor_idle_time = 0.0
            return

        moved = math.hypot(px - self.last_pointer[0], py - self.last_pointer[1])
        if moved > self.CURSOR_MOVE_EPS:
            self.cursor_idle_time = 0.0
            self.last_pointer = (px, py)
            if self.cursor_nap:
                self.cursor_nap = False
                self.startled = True
                self.startle_timer = 0.8
            return

        self.cursor_idle_time += dt
        if (
            self.cursor_idle_time >= self.CURSOR_IDLE_THRESHOLD
            and not self.falling
            and not self.chasing_laser
        ):
            self.cursor_nap = True
            self.perched = False
            self.in_box = False
            self.on_bed = False
            self.x, self.y = self._clamp_to_bounds(
                px - self.cat_w * 0.5,
                py - self.cat_h * 0.65,
                bounds,
            )

    def _update_props(self, dt, pointer, bounds):
        laser = next((p for p in self.props if p.active and p.kind == "laser"), None)
        if laser is not None:
            self.chasing_laser = True
            self.perched = False
            self.falling = False
            self.in_box = False
            self.on_bed = False
            self.cursor_nap = False
            if pointer is not None:
                laser.x, laser.y = float(pointer[0]), float(pointer[1])
            tx = laser.x - self.cat_w * 0.5
            ty = laser.y - self.cat_h * 0.5
            dx = tx - self.x
            dy = ty - self.y
            dist = math.hypot(dx, dy)
            step_dist = self.LASER_CHASE_SPEED * dt
            if dist <= step_dist or dist == 0.0:
                self.x, self.y = self._clamp_to_bounds(tx, ty, bounds)
            else:
                self.x, self.y = self._clamp_to_bounds(
                    self.x + dx / dist * step_dist,
                    self.y + dy / dist * step_dist,
                    bounds,
                )
            return

        self.chasing_laser = False
        if self.falling or self.perched or self.cursor_nap:
            return

        cat_cx = self.x + self.cat_w * 0.5
        cat_cy = self.y + self.cat_h * 0.5
        matched_bed = None
        for prop in self.props:
            if not prop.active:
                continue
            prop_cx = prop.x + prop.width * 0.5
            prop_cy = prop.y + prop.height * 0.5
            if math.hypot(cat_cx - prop_cx, cat_cy - prop_cy) <= self.PROP_SNAP_RADIUS:
                if prop.kind == "bed" and matched_bed is None:
                    matched_bed = prop

        if matched_bed is not None:
            self.on_bed = True
            self.in_box = False
            self.surface = "bed"
            self.active_prop = matched_bed
            self.x = matched_bed.x + (matched_bed.width - self.cat_w) * 0.5
            self.y = matched_bed.y + matched_bed.height - self.cat_h
        else:
            self.in_box = False
            self.on_bed = False
            if self.surface == "bed":
                self.surface = "ground"

    def step(
        self,
        dt,
        cat_x=None,
        cat_y=None,
        *,
        facing=1,
        pointer=None,
        window_rect=_UNSET,
        taskbar_rect=_UNSET,
        has_toast=_UNSET,
        bounds=None,
    ):
        """Advance desktop physics by ``dt`` seconds and return updated (x, y)."""
        try:
            dt = float(dt)
        except (TypeError, ValueError):
            return (self.x, self.y)
        if not math.isfinite(dt) or dt <= 0:
            return (self.x, self.y)

        if bounds is not None:
            self.bounds = _normalize_rect(bounds) or self.bounds
        if cat_x is not None:
            self.x = float(cat_x)
        if cat_y is not None:
            self.y = float(cat_y)

        prev_x, prev_y = self.x, self.y

        if window_rect is _UNSET:
            window_rect = (window_utils.window_rect(self.perch_hwnd) if self.perched and self.perch_hwnd
                           else window_utils.active_window_rect())
        if taskbar_rect is _UNSET:
            taskbar_rect = window_utils.taskbar_rect()
        else:
            taskbar_rect = _normalize_rect(taskbar_rect)
        if has_toast is _UNSET:
            has_toast = window_utils.has_toast_notification()

        self._update_slapped_icons(dt)

        if self.perched:
            self._update_perch(dt, window_rect)

        if self.falling:
            self.vy += self.GRAVITY * dt
            self.y += self.vy * dt
            floor_y = self._floor_y(self.bounds, taskbar_rect)
            if self.y >= floor_y:
                self.y = floor_y
                self.vy = 0.0
                self.falling = False
                self.surface = "taskbar" if taskbar_rect is not None else "ground"

        self._update_cursor_nap(dt, pointer, self.bounds)
        self._update_props(dt, pointer, self.bounds)

        if has_toast and not self.falling and not self.chasing_laser:
            self.toast_curious = True
            self.perched = False
            self.cursor_nap = False
            target_x = float(self.bounds[2]) - self.cat_w - 16.0
            target_y = self._floor_y(self.bounds, taskbar_rect)
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.hypot(dx, dy)
            step_dist = self.TOAST_RUN_SPEED * dt
            if dist <= step_dist or dist == 0.0:
                self.x, self.y = target_x, target_y
            else:
                self.x += dx / dist * step_dist
                self.y += dy / dist * step_dist
            self.surface = "taskbar" if taskbar_rect is not None else "ground"
        else:
            self.toast_curious = False

        if not self.perched and not self.falling and not self.in_box and not self.on_bed:
            if taskbar_rect is not None and abs(self.y - (taskbar_rect[1] - self.cat_h)) <= 2.0:
                self.surface = "taskbar"

        self._update_paw_trails(dt, prev_x, prev_y, self.x, self.y, facing)
        return (self.x, self.y)
