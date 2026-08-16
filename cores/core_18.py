# cores/core_18.py
# HARDENED — wires in real pairing, passes credentials through properly

from cores.core_18_security_state import SecurityState
from cores.trusted_device_manager import TrustedDeviceManager
from cores.core_18_pairing_manager import PairingManager
from cores.core_18_login_watcher import LoginWatcher
from cores.core_18_session_watcher import SessionWatcher
from cores.core_18_freeze_overlay import FreezeOverlay
from cores.core_18_intruder_detector import IntruderDetector

from network.local_server import start_local_server
from network.local_discovery import start_local_discovery
from network.connection_manager import ConnectionManager

from cloud_client import CloudClient

import threading, ctypes, subprocess, os, time, sys


class Core18:
    def __init__(self):
        print("🚀 Zephyr Altair AI - Starting System (Hardened Security)")

        self.security_state = SecurityState.LOCKED
        self.trusted_device_manager = TrustedDeviceManager()
        self.pairing_manager = PairingManager(self.trusted_device_manager)

        self.camera_process = None
        self.camera_running = False
        self.camera_lock = threading.Lock()

        try:
            self.login_watcher = LoginWatcher(self._on_desktop_ready)
            self.freeze_overlay = FreezeOverlay()
            self.intruder_detector = IntruderDetector(self.trusted_device_manager)

            start_local_server(self)
            start_local_discovery()
            self.connection = ConnectionManager()
            self.cloud = CloudClient(self, self.connection, self.trusted_device_manager)

            self.check_trusted_device()
            self._start_session_watcher()
            self._start_login_watcher()
            self.login_watcher.arm()

        except Exception as e:
            # A single sub-module failing to start no longer takes down
            # the whole assistant silently — you'll see exactly what broke.
            print(f"❌ Core 18 sub-module failed to initialize: {e}")
            raise

        print("✅ Core 18 initialized (real per-device authentication active)")
        if not self.trusted_device_manager.load():
            print("⚠️ No device paired yet. Trigger pairing to connect your phone.")

    def _on_desktop_ready(self):
        # First-run setup case: if no device has EVER been paired,
        # there's nothing to protect yet, and whoever is at the
        # keyboard right now is doing initial setup — not an
        # untrusted session. Skip the freeze/intruder response
        # entirely until pairing has happened at least once.
        if not self.trusted_device_manager.load():
            print("[Core 18] Desktop Ready (first-run setup — no lock/freeze until paired)")
            return

        if self.security_state == SecurityState.LOCKED:
            self.freeze_overlay.show()
            self.intruder_detector.enable()
        else:
            self.freeze_overlay.hide()
            self.intruder_detector.disable()

    def _on_windows_lock(self):
        if not self.trusted_device_manager.load():
            print("[Core 18] Windows Locked (first-run setup — no freeze until paired)")
            return
        self.freeze_overlay.show()
        self.intruder_detector.enable()

    def _on_windows_unlock(self):
        print("[Core 18] Windows Unlocked")

    def _start_session_watcher(self):
        watcher = SessionWatcher(on_lock=self._on_windows_lock, on_unlock=self._on_windows_unlock)
        threading.Thread(target=watcher.start, daemon=True).start()

    def _start_login_watcher(self):
        threading.Thread(target=self.login_watcher.start, daemon=True).start()

    def check_trusted_device(self):
        device = self.trusted_device_manager.load()
        if device:
            print(f"[Core 18] Trusted device loaded: {device.get('device_name', 'Unknown')}")
            self.security_state = SecurityState.UNLOCKED

    def start_pairing(self):
        """Call this from a voice command or hotkey to begin pairing a
        new phone. Real-life example: like pressing 'pair new device'
        on a Bluetooth speaker — nothing connects until you actively
        start this AND enter the PIN it shows you."""
        return self.pairing_manager.start_pairing()

    def lock(self):
        self.security_state = SecurityState.LOCKED
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

    # ---- Camera methods unchanged from before — see camera core
    # rebuild for when we get to those files ----
    def _get_webcam_stream_path(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return project_root, os.path.join(project_root, "webcam_stream.py")

    def is_camera_running(self):
        try:
            if self.camera_process and self.camera_process.poll() is None:
                self.camera_running = True
                return True
            self.camera_running = False
            return False
        except Exception:
            self.camera_running = False
            return False

    def start_live_camera(self):
        # unchanged from your original — kept here for completeness
        with self.camera_lock:
            if self.is_camera_running():
                return True
            project_root, webcam_path = self._get_webcam_stream_path()
            if not os.path.exists(webcam_path):
                return False
            try:
                self.camera_process = subprocess.Popen(
                    [sys.executable, "-u", webcam_path], cwd=project_root,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, text=True, bufsize=1,
                )
                time.sleep(2)
                self.camera_running = self.camera_process.poll() is None
                return self.camera_running
            except Exception as e:
                print(f"[Core 18] Camera start error: {e}")
                return False

    def stop_live_camera(self):
        with self.camera_lock:
            if not self.camera_process:
                return
            try:
                self.camera_process.terminate()
                self.camera_process.wait(timeout=5)
            except Exception:
                try:
                    self.camera_process.kill()
                except Exception:
                    pass
            self.camera_process = None
            self.camera_running = False

    def toggle_live_camera(self):
        self.stop_live_camera() if self.is_camera_running() else self.start_live_camera()

    def cleanup(self):
        try:
            self.stop_live_camera()
            self.freeze_overlay.hide()
        except Exception as e:
            print(f"[Core 18] Cleanup error: {e}")