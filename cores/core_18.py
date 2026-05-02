# ==============================
# FILE: cores/core_18.py (FINAL CLEAN + WIRED)
# ==============================

from cores.core_18_security_state import SecurityState
from cores.trusted_device_manager import TrustedDeviceManager
from cores.core_18_login_watcher import LoginWatcher
from cores.core_18_session_watcher import SessionWatcher
from cores.core_18_freeze_overlay import FreezeOverlay
from cores.core_18_intruder_detector import IntruderDetector

# 🔥 NEW NETWORK LAYER
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

        # ==============================
        # 🔥 LOCAL SYSTEMS (NEW)
        # ==============================
        start_local_server(self)
        start_local_discovery()

        # ==============================
        # SYSTEM INIT
        # ==============================
        self.check_trusted_device()
        self._start_session_watcher()
        self._start_login_watcher()

        self.login_watcher.arm()

        # ==============================
        # 🔥 CONNECTION MANAGER (BRAIN)
        # ==============================
        self.connection = ConnectionManager()
        print("[Core 18] Connection Manager started")

        # ==============================
        # 🔥 CLOUD CLIENT (CLOUD ONLY)
        # ==============================
        self.cloud = CloudClient(self, self.connection)
        print("[Core 18] Cloud Client started")

    # ==============================
    # WINDOWS EVENTS
    # ==============================
    def _on_windows_lock(self):
        self.freeze_overlay.show()
        self.intruder_detector.enable()

    def _on_windows_unlock(self):
        pass

    # ==============================
    # WATCHERS
    # ==============================
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

    # ==============================
    # TRUSTED DEVICE
    # ==============================
    def check_trusted_device(self):
        device = self.trusted_device_manager.load()
        if device:
            self.security_state = SecurityState.UNLOCKED

    # ==============================
    # CORE ACTIONS
    # ==============================
    def lock(self):
        print("[Core 18] 🔒 Lock triggered")

        self.freeze_overlay.show()
        self.intruder_detector.enable()

        try:
            ctypes.windll.user32.LockWorkStation()
        except Exception as e:
            print("[ERROR]", e)

    def unlock(self):
        print("[Core 18] 🔓 Unlock triggered")

        self.security_state = SecurityState.UNLOCKED
        self.freeze_overlay.hide()
        self.intruder_detector.disable()