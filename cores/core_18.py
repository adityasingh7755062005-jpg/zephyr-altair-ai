# ==============================
# FILE: cores/core_18.py
# FULL LIVE CAMERA WIRED VERSION
# FINAL STABLE BUILD
# MANUAL CAMERA START VERSION
# FULL FIXED VERSION
# LOCAL + CLOUD CAMERA FIXED
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
import subprocess
import os
import time
import sys


class Core18:

    def __init__(self):

        print("🚀 Zephyr Altair AI - Starting System")

        # ==============================
        # SECURITY
        # ==============================

        self.security_state = SecurityState.LOCKED

        self.trusted_device_manager = (
            TrustedDeviceManager()
        )

        # ==============================
        # CAMERA ENGINE
        # ==============================

        self.camera_process = None

        self.camera_running = False

        self.camera_lock = threading.Lock()

        # ==============================
        # WATCHERS
        # ==============================

        self.login_watcher = LoginWatcher(
            self._on_desktop_ready
        )

        self.freeze_overlay = FreezeOverlay()

        self.intruder_detector = (
            IntruderDetector()
        )

        # ==============================
        # NETWORK
        # ==============================

        start_local_server(self)

        start_local_discovery()

        self.connection = ConnectionManager()

        self.cloud = CloudClient(
            self,
            self.connection
        )

        # ==============================
        # STARTUP
        # ==============================

        self.check_trusted_device()

        self._start_session_watcher()

        self._start_login_watcher()

        self.login_watcher.arm()

        # ==============================
        # STATUS
        # ==============================

        print("✅ Core 18 initialized successfully")

        print("🔐 Security system active")

        print("📷 Live camera engine ready")

        print("⏳ Waiting for device connection...")

    # ==============================
    # DESKTOP READY
    # ==============================

    def _on_desktop_ready(self):

        print("[Core 18] Desktop Ready")

        if (
            self.security_state ==
            SecurityState.LOCKED
        ):

            self.freeze_overlay.show()

            self.intruder_detector.enable()

        else:

            self.freeze_overlay.hide()

            self.intruder_detector.disable()

    # ==============================
    # WINDOWS LOCK
    # ==============================

    def _on_windows_lock(self):

        print("[Core 18] Windows Locked")

        self.freeze_overlay.show()

        self.intruder_detector.enable()

    # ==============================
    # WINDOWS UNLOCK
    # ==============================

    def _on_windows_unlock(self):

        print("[Core 18] Windows Unlocked")

    # ==============================
    # SESSION WATCHER
    # ==============================

    def _start_session_watcher(self):

        watcher = SessionWatcher(

            on_lock=self._on_windows_lock,

            on_unlock=self._on_windows_unlock
        )

        threading.Thread(

            target=watcher.start,

            daemon=True

        ).start()

    # ==============================
    # LOGIN WATCHER
    # ==============================

    def _start_login_watcher(self):

        threading.Thread(

            target=self.login_watcher.start,

            daemon=True

        ).start()

    # ==============================
    # TRUSTED DEVICE
    # ==============================

    def check_trusted_device(self):

        device = (
            self.trusted_device_manager.load()
        )

        if device:

            print(
                "[Core 18] Trusted device → unlocked"
            )

            self.security_state = (
                SecurityState.UNLOCKED
            )

    # ==============================
    # LOCK
    # ==============================

    def lock(self):

        print("[Core 18] 🔒 Lock requested")

        self.security_state = (
            SecurityState.LOCKED
        )

        self.freeze_overlay.show()

        self.intruder_detector.enable()

        try:

            ctypes.windll.user32.LockWorkStation()

        except Exception as e:

            print("[ERROR]", e)

    # ==============================
    # UNLOCK
    # ==============================

    def unlock(self):

        print("[Core 18] 🔓 Unlock requested")

        self.security_state = (
            SecurityState.UNLOCKED
        )

        self.freeze_overlay.hide()

        self.intruder_detector.disable()

    # ==============================
    # CAMERA FILE PATH
    # ==============================

    def _get_webcam_stream_path(self):

        project_root = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

        webcam_path = os.path.join(
            project_root,
            "webcam_stream.py"
        )

        return project_root, webcam_path

    # ==============================
    # START LIVE CAMERA
    # ==============================

    def start_live_camera(self):

        with self.camera_lock:

            try:

                # ==============================
                # ALREADY RUNNING
                # ==============================

                if self.is_camera_running():

                    print(
                        "[Core 18] 📷 Camera already running"
                    )

                    return True

                # ==============================
                # PATH
                # ==============================

                project_root, webcam_path = (
                    self._get_webcam_stream_path()
                )

                # ==============================
                # FILE CHECK
                # ==============================

                if not os.path.exists(webcam_path):

                    print(
                        "[Core 18] ❌ webcam_stream.py not found"
                    )

                    return False

                print(
                    "[Core 18] 🚀 Starting live camera..."
                )

                print(
                    f"[Core 18] 📂 Path: {webcam_path}"
                )

                # ==============================
                # PYTHON EXECUTABLE
                # ==============================

                python_exe = sys.executable

                print(
                    f"[Core 18] 🐍 Python: {python_exe}"
                )

                # ==============================
                # WINDOWS SETTINGS
                # ==============================

                creation_flags = 0
                startupinfo = None

                if os.name == "nt":

                    creation_flags = (
                        subprocess.CREATE_NEW_PROCESS_GROUP
                    )

                # ==============================
                # START PROCESS
                # ==============================

                self.camera_process = subprocess.Popen(

                    [
                        python_exe,
                        "-u",
                        webcam_path
                    ],

                    cwd=project_root,

                    stdout=None,

                    stderr=None,

                    stdin=subprocess.DEVNULL,

                    creationflags=creation_flags,

                    startupinfo=startupinfo
                )

                # ==============================
                # WAIT
                # ==============================

                time.sleep(5)

                # ==============================
                # VERIFY
                # ==============================

                if (
                    self.camera_process
                    and
                    self.camera_process.poll() is None
                ):

                    self.camera_running = True

                    print(
                        "[Core 18] ✅ Live camera started"
                    )

                    print(
                        f"[Core 18] 📷 PID: {self.camera_process.pid}"
                    )

                    return True

                # ==============================
                # PROCESS EXITED
                # ==============================

                exit_code = None

                try:

                    exit_code = (
                        self.camera_process.poll()
                    )

                except:
                    pass

                print(
                    f"[Core 18] ❌ Camera process crashed | Exit: {exit_code}"
                )

                self.camera_running = False

                self.camera_process = None

                return False

            except Exception as e:

                print(
                    f"[Core 18] ❌ Camera start error: {e}"
                )

                self.camera_running = False

                self.camera_process = None

                return False

    # ==============================
    # STOP LIVE CAMERA
    # ==============================

    def stop_live_camera(self):

        with self.camera_lock:

            try:

                if not self.camera_process:

                    print(
                        "[Core 18] 📷 Camera not running"
                    )

                    self.camera_running = False

                    return

                print(
                    "[Core 18] 🛑 Stopping live camera..."
                )

                if (
                    self.camera_process.poll()
                    is None
                ):

                    self.camera_process.terminate()

                    try:

                        self.camera_process.wait(
                            timeout=5
                        )

                    except Exception:

                        print(
                            "[Core 18] ⚠️ Force killing camera..."
                        )

                        self.camera_process.kill()

                self.camera_process = None

                self.camera_running = False

                print(
                    "[Core 18] ✅ Live camera stopped"
                )

            except Exception as e:

                print(
                    f"[Core 18] ❌ Camera stop error: {e}"
                )

    # ==============================
    # TOGGLE CAMERA
    # ==============================

    def toggle_live_camera(self):

        if self.is_camera_running():

            self.stop_live_camera()

        else:

            self.start_live_camera()

    # ==============================
    # CAMERA STATUS
    # ==============================

    def is_camera_running(self):

        try:

            if (
                self.camera_process
                and
                self.camera_process.poll() is None
            ):

                self.camera_running = True

                return True

            self.camera_running = False

            return False

        except Exception:

            self.camera_running = False

            return False

    # ==============================
    # CLEANUP
    # ==============================

    def cleanup(self):

        try:

            print(
                "[Core 18] 🧹 Cleaning up..."
            )

            self.stop_live_camera()

        except Exception as e:

            print(
                f"[Core 18] Cleanup error: {e}"
            )