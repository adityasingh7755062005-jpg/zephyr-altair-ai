# ==============================
# FILE: cores/core_18.py (CLEAN)
# ==============================

from cores.core_18_security_state import SecurityState
from cores.trusted_device_manager import TrustedDeviceManager
from cores.core_18_login_watcher import LoginWatcher
from cores.core_18_session_watcher import SessionWatcher
from cores.core_18_freeze_overlay import FreezeOverlay
from cores.core_18_intruder_detector import IntruderDetector

from network.local_server import start_local_server
from network.local_discovery import start_local_discovery
from network.connection_manager import ConnectionManager
from cloud_client import CloudClient

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

        start_local_server(self)
        start_local_discovery()

        self.check_trusted_device()
        self._start_session_watcher()
        self._start_login_watcher()

        self.login_watcher.arm()

        self.connection = ConnectionManager()

        self.cloud = CloudClient(self, self.connection)

        print("[Core 18] initialized successfully")
        print("Security system active")

    def _on_desktop_ready(self):
        print("[Core 18] Desktop Ready")

        if self.security_state == SecurityState.LOCKED:
            self.freeze_overlay.show()
            self.intruder_detector.enable()
        else:
            self.freeze_overlay.hide()
            self.intruder_detector.disable()

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

    def check_trusted_device(self):
        device = self.trusted_device_manager.load()
        if device:
            print("[Core 18] Trusted device → unlocked")
            self.security_state = SecurityState.UNLOCKED

    def lock(self):
        print("🔒 Lock")

        self.security_state = SecurityState.LOCKED
        self.freeze_overlay.show()
        self.intruder_detector.enable()

        try:
            ctypes.windll.user32.LockWorkStation()
        except Exception as e:
            print("[ERROR]", e)

    def unlock(self):
        print("🔓 Unlock")

        self.security_state = SecurityState.UNLOCKED
        self.freeze_overlay.hide()
        self.intruder_detector.disable() 