# ==============================
# FILE 4: core_18.py
# ==============================

from cores.core_18_security_state import SecurityState
from cores.trusted_device_manager import TrustedDeviceManager
from cores.core_18_control_server import start_control_server
from cores.core_18_login_watcher import LoginWatcher
from cores.core_18_session_watcher import SessionWatcher
from cores.core_18_discovery_server import start_discovery_server
from cores.core_18_freeze_overlay import FreezeOverlay
from cores.core_18_intruder_detector import IntruderDetector

import threading
import ctypes


class Core18:

    def __init__(self):
        print("[Core 18] Booting...")

        self.security_state = SecurityState.LOCKED
        self.trusted_device_manager = TrustedDeviceManager()

        self.login_watcher = LoginWatcher(self._on_desktop_ready)

        self.freeze_overlay = FreezeOverlay()
        self.intruder_detector = IntruderDetector()

        self.start_control_listener()
        start_discovery_server()

        self.check_trusted_device()

        self._start_session_watcher()
        self._start_login_watcher()

        self.login_watcher.arm()

    def _on_windows_lock(self):
        self.freeze_overlay.show()
        self.intruder_detector.enable()

    def _on_windows_unlock(self):
        pass

    def _start_session_watcher(self):
        watcher = SessionWatcher(
            on_lock=self._on_windows_lock,
            on_unlock=self._on_windows_unlock
        )
        threading.Thread(target=watcher.start, daemon=True).start()

    def _start_login_watcher(self):
        threading.Thread(
            target=self.login_watcher.start,
            daemon=True
        ).start()

    def start_control_listener(self):
        threading.Thread(
            target=start_control_server,
            args=(self, 5001),
            daemon=True
        ).start()

    def check_trusted_device(self):
        device = self.trusted_device_manager.load()
        if device:
            self.security_state = SecurityState.UNLOCKED

    def lock(self):
        self.freeze_overlay.show()
        self.intruder_detector.enable()

        try:
            ctypes.windll.user32.LockWorkStation()
        except Exception as e:
            print("[ERROR]", e)

    def unlock(self):
        self.security_state = SecurityState.UNLOCKED
        self.freeze_overlay.hide()
        self.intruder_detector.disable()