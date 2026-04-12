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

        # ==========================
        # SECURITY SYSTEMS
        # ==========================
        self.freeze_overlay = FreezeOverlay()
        self.intruder_detector = IntruderDetector()

        # ==========================
        # SERVERS
        # ==========================
        self.start_control_listener()
        start_discovery_server()

        # ==========================
        # PAIRING CHECK
        # ==========================
        self.check_trusted_device()

        # ==========================
        # ❌ CLOUD DISABLED (LOCAL TEST MODE)
        # ==========================
        self.cloud_client = None
        print("[Core 18] Cloud disabled (local testing mode)")

        # ==========================
        # WATCHERS
        # ==========================
        self._start_session_watcher()
        self._start_login_watcher()

        self.login_watcher.arm()

    # ==================================================
    # WINDOWS SESSION
    # ==================================================

    def _on_windows_lock(self):
        print("[Core 18] Windows LOCK detected")

        self.login_watcher.arm()

        self.freeze_overlay.show()
        self.intruder_detector.enable()

    def _on_windows_unlock(self):
        print("[Core 18] Windows UNLOCK detected")

    def _start_session_watcher(self):
        watcher = SessionWatcher(
            on_lock=self._on_windows_lock,
            on_unlock=self._on_windows_unlock
        )

        threading.Thread(
            target=watcher.start,
            daemon=True
        ).start()

    # ==================================================
    # DESKTOP
    # ==================================================

    def _on_desktop_ready(self):
        print("[Core 18] Desktop detected")

    def _start_login_watcher(self):
        threading.Thread(
            target=self.login_watcher.start,
            daemon=True
        ).start()

    # ==================================================
    # CONTROL SERVER
    # ==================================================

    def start_control_listener(self):
        threading.Thread(
            target=start_control_server,
            args=(self, 5001),
            daemon=True
        ).start()

    def check_trusted_device(self):
        device = self.trusted_device_manager.load()

        if device:
            print("[Core 18] Trusted device found")
            self.security_state = SecurityState.UNLOCKED
        else:
            print("[Core 18] No trusted device found")
            print("[Core 18] Waiting for manual pairing...")

    # ==================================================
    # LOCAL COMMANDS (PHONE VIA LOCAL SERVER)
    # ==================================================

    def lock(self):
        print("[Core 18] Lock requested (LOCAL)")

        self.login_watcher.arm()

        self.freeze_overlay.show()
        self.intruder_detector.enable()

        try:
            ctypes.windll.user32.LockWorkStation()
        except Exception as e:
            print("[Core 18 ERROR] Lock failed:", e)

    def unlock(self):
        print("[Core 18] Unlock requested (LOCAL)")

        self.security_state = SecurityState.UNLOCKED

        self.freeze_overlay.hide()
        self.intruder_detector.disable()