# cores/core_18_session_watcher.py
# HARDENED — reliable Windows lock detection

import time
import ctypes
from ctypes import wintypes

DESKTOP_SWITCHDESKTOP = 0x0100
user32 = ctypes.windll.user32


class SessionWatcher:
    """
    Real-life example: GetForegroundWindow()==0 (the old check) is like
    guessing someone left the room just because you can't see their
    face for a second — happens constantly during normal use (alt-tab,
    clicking the taskbar) and gives false alarms.

    OpenInputDesktop is like checking whether the door is actually
    locked — it can only succeed if the input desktop is genuinely
    accessible, which fails specifically and only when Windows is
    really locked. This is the same technique Windows' own lock
    screen detection relies on.
    """

    def __init__(self, on_lock, on_unlock, poll_interval=0.5):
        self.on_lock = on_lock
        self.on_unlock = on_unlock
        self.poll_interval = poll_interval
        self._last_locked = None

    def _is_locked(self) -> bool:
        try:
            desktop = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
            if desktop:
                user32.CloseDesktop(desktop)
                return False  # successfully opened -> NOT locked
            return True  # failed to open -> locked
        except Exception:
            return False  # fail safe: assume unlocked rather than
                           # falsely triggering the freeze overlay

    def start(self):
        print("[Core 18] SessionWatcher started (reliable lock detection)")
        while True:
            try:
                locked = self._is_locked()
                if locked != self._last_locked:
                    self._last_locked = locked
                    (self.on_lock if locked else self.on_unlock)()
                time.sleep(self.poll_interval)
            except Exception as e:
                print("[Core 18] SessionWatcher error:", e)
                time.sleep(1)