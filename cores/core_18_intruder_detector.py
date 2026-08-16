# cores/core_18_intruder_detector.py
# HARDENED — adds local storage retention, signs uploads with the real secret

import cv2, os, time, threading
from datetime import datetime, timedelta
from pynput import keyboard, mouse
from network.security import generate_signature
import secrets as _secrets

CLOUD_UPLOAD_URL = "https://zephyr-altair-ai-server.onrender.com/upload_intruder"
RETENTION_DAYS = 14


class IntruderDetector:
    def __init__(self, trusted_device_manager):
        self.trusted_device_manager = trusted_device_manager
        self.freeze_active = False
        self.last_upload = 0
        self.lock = threading.Lock()

        os.makedirs("intruders", exist_ok=True)
        self._cleanup_old_captures()

        print("🚨 Intruder detector ready (activity-only, never logs keystroke content)")

        keyboard.Listener(on_press=self._on_activity).start()
        mouse.Listener(on_move=self._on_activity, on_click=self._on_activity).start()

    def _cleanup_old_captures(self):
        cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
        for fname in os.listdir("intruders"):
            path = os.path.join("intruders", fname)
            try:
                if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                    os.remove(path)
            except OSError:
                pass

    def _on_activity(self, *args):
        # NOTE: only ever checks THAT activity happened, never what key
        # or where the mouse moved — no content is ever recorded.
        if not self.freeze_active:
            return
        if time.time() - self.last_upload < 5:
            return
        self.last_upload = time.time()
        threading.Thread(target=self.capture, daemon=True).start()

    def capture(self):
        if not self.lock.acquire(blocking=False):
            return
        cam = None
        try:
            cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cam.isOpened():
                return
            ret, frame = cam.read()
            if not ret:
                return

            filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
            file_path = os.path.join("intruders", filename)
            if cv2.imwrite(file_path, frame):
                threading.Thread(target=self.upload, args=(file_path,), daemon=True).start()
        except Exception as e:
            print("❌ Capture error:", e)
        finally:
            if cam:
                cam.release()
            self.lock.release()

    def upload(self, file_path):
        trusted = self.trusted_device_manager.load()
        if not trusted:
            print("❌ Upload skipped — no paired device to sign with")
            return

        device_id = trusted["device_id"]
        secret = bytes.fromhex(trusted["secret_key"])
        ts = str(int(time.time()))
        nonce = _secrets.token_hex(8)
        sig = generate_signature("upload_intruder", ts, device_id, nonce, secret)

        import requests
        for attempt in range(3):
            try:
                with open(file_path, "rb") as f:
                    response = requests.post(
                        CLOUD_UPLOAD_URL,
                        files={"file": f},
                        data={"device_id": device_id, "ts": ts, "nonce": nonce, "sig": sig},
                        timeout=20,
                    )
                if response.status_code == 200:
                    print("✅ Intruder uploaded (signed)")
                    return
            except Exception as e:
                print("❌ Upload error:", e)
            time.sleep(2)
        print("❌ Upload failed after retries")

    def enable(self):
        self.freeze_active = True

    def disable(self):
        self.freeze_active = False