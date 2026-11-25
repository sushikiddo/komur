"""Adaptive battery & CPU power manager for Kömür (macOS + Windows, stdlib only).

Detects AC vs Battery power and OS Low Power / Battery Saver mode without blocking
the Tk UI thread, and selects an adaptive frame interval (4..45 FPS) based on
current cat activity so laptops lose virtually no battery while walking & play stay fluid.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import logging
import re
import subprocess
import sys
import threading
import time

_IS_MAC = sys.platform == "darwin"
_IS_WIN = sys.platform == "win32"

POLL_INTERVAL_SECONDS = 30.0

ACTIVE_STATES = frozenset({
    "wander", "follow", "play", "jump", "scratch", "stretch", "roll", "laser_chase",
})
EXPRESSIVE_STATES = frozenset({
    "groom", "yawn", "drink", "eat", "sneeze", "chirp", "knead", "hiss",
})


@dataclass(frozen=True)
class PowerStatus:
    on_battery: bool = False
    low_power_mode: bool = False
    percent: int | None = None


def _read_mac_power() -> PowerStatus:
    on_battery = False
    low_power = False
    percent = None
    try:
        out = subprocess.check_output(
            ["pmset", "-g", "batt"], text=True, timeout=2.0, stderr=subprocess.DEVNULL,
        )
        on_battery = "Battery Power" in out
        m = re.search(r"(\d+)%", out)
        if m:
            percent = max(0, min(100, int(m.group(1))))
    except Exception:
        pass
    try:
        out2 = subprocess.check_output(
            ["pmset", "-g"], text=True, timeout=2.0, stderr=subprocess.DEVNULL,
        )
        m2 = re.search(r"lowpowermode\s+(\d+)", out2)
        if m2:
            low_power = m2.group(1) == "1"
    except Exception:
        pass
    return PowerStatus(on_battery=on_battery, low_power_mode=low_power, percent=percent)


def _read_win_power() -> PowerStatus:
    try:
        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        st = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st)):
            on_battery = (st.ACLineStatus == 0)
            low_power = bool(st.SystemStatusFlag & 1)
            pct = int(st.BatteryLifePercent & 0xFF)
            percent = pct if 0 <= pct <= 100 else None
            return PowerStatus(on_battery=on_battery, low_power_mode=low_power, percent=percent)
    except Exception:
        pass
    return PowerStatus()


def read_system_power() -> PowerStatus:
    if _IS_MAC:
        return _read_mac_power()
    if _IS_WIN:
        return _read_win_power()
    return PowerStatus()


def frame_interval_ms(
    state: str,
    *,
    status: PowerStatus | None = None,
    enabled: bool = True,
    hidden: bool = False,
    paused: bool = False,
    dragging: bool = False,
    pointer_active: bool = False,
) -> int:
    """Return optimal Tkinter ``after()`` delay in ms for current state & power source."""
    if hidden:
        return 250
    if paused and not dragging:
        return 220
    if dragging:
        return 22

    st = status or PowerStatus()
    state_low = str(state or "sit").lower()
    if not enabled:
        # Power-saver explicitly off: still keep sleep/idle reasonable
        if state_low == "sleep":
            return 80
        return 20 if state_low in ACTIVE_STATES else 33

    saving = st.on_battery or st.low_power_mode
    ultra = st.low_power_mode or (st.on_battery and st.percent is not None and st.percent <= 20)

    if state_low == "sleep":
        return 500 if ultra else (400 if saving else 180)
    if state_low in ACTIVE_STATES:
        return 40 if ultra else (33 if saving else 22)
    if state_low in EXPRESSIVE_STATES:
        return 95 if ultra else (65 if saving else 38)
    # Calm idle states: sit, look, purr_idle, bored, perch, peek, box_sit
    if pointer_active:
        return 75 if ultra else (55 if saving else 33)
    return 260 if ultra else (200 if saving else 90)


class PowerMonitor:
    """Non-blocking background battery watcher for the main animation loop."""

    def __init__(self, reader=read_system_power, clock=time.monotonic):
        self._reader = reader
        self._clock = clock
        self._lock = threading.Lock()
        self._status = PowerStatus()
        self._next_poll = 0.0
        self._busy = False

    @property
    def status(self) -> PowerStatus:
        with self._lock:
            return self._status

    @property
    def is_saving(self) -> bool:
        st = self.status
        return st.on_battery or st.low_power_mode

    def poll(self) -> PowerStatus:
        """Kick off a background battery check every 30s; returns latest cached status instantly."""
        now = self._clock()
        with self._lock:
            if not self._busy and now >= self._next_poll:
                self._busy = True
                threading.Thread(target=self._poll_power_worker, daemon=True).start()
            return self._status

    def _poll_power_worker(self):
        try:
            st = self._reader()
        except Exception:
            logging.debug("Power status read failed", exc_info=True)
            st = PowerStatus()
        with self._lock:
            self._status = st
            self._busy = False
            self._next_poll = self._clock() + POLL_INTERVAL_SECONDS
