# cores/core_18_intruder_detector.py
# Merged: real per-device signed uploads (from the security rebuild)
# + activity-labeled local logging (your new work)

import cv2
import os
import json
import time
import secrets
import threading
import requests

from datetime import datetime, timedelta
from pynput import keyboard, mouse

from network.security import generate_signature

CLOUD_UPLOAD_URL = "https://zephyr-altair-ai-server.onrender.com/upload_intruder"

# NOTE: we deliberately only ever record *which kind* of input triggered
# the capture (keyboard vs mouse) as a label — never the actual key
# pressed or exact cursor path/content. This is an intruder alert,
# not a keylogger.
ACTIVITY_LABELS = {
    "keyboard": "Keyboard activity detected",
    "mouse_move": "Mouse movement detected",
    "mouse_click": "Mouse click detected",
}

LOG_DIR = os.path.join("data", "security")
LOG_FILE = os.path.join(LOG_DIR, "intruder_log.json")
MAX_LOG_ENTRIES = 200


WARNING_THRESHOLD = 3
WARNING_MESSAGE = (
    "You are not an authorized person. This device is being monitored "
    "and this attempt has been recorded."
)


class IntruderDetector:
    def __init__(self, trusted_device_manager, voice_output=None):
        self.trusted_device_manager = trusted_device_manager
        self.voice_output = voice_output  # optional Core 7 instance
        self.freeze_active = False
        self.last_upload = 0
        self.lock = threading.Lock()
        self.log_lock = threading.Lock()

        # Tracks attempts within the CURRENT freeze session — reset
        # every time freeze starts or ends, so each session counts fresh.
        self.activity_count = 0
        self._warned_this_session = False

        os.makedirs("intruders", exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)

        print("🚨 Intruder detector ready (signed uploads, activity-labeled)")

        keyboard.Listener(on_press=lambda key: self._on_activity("keyboard")).start()
        mouse.Listener(
            on_move=lambda x, y: self._on_activity("mouse_move"),
            on_click=lambda x, y, button, pressed: (
                self._on_activity("mouse_click") if pressed else None
            ),
        ).start()

    # ==========================
    # ACTIVITY
    # ==========================
    def _on_activity(self, kind):
        if not self.freeze_active:
            return
        if time.time() - self.last_upload < 5:
            return
        self.last_upload = time.time()
        print(f"⚠️ Activity during freeze ({kind})")

        self.activity_count += 1
        print(f"⚠️ Attempt count this session: {self.activity_count}")

        if self.activity_count >= WARNING_THRESHOLD and not self._warned_this_session:
            self._warned_this_session = True
            self._speak_warning()

        threading.Thread(target=self.capture, args=(kind,), daemon=True).start()

    def _speak_warning(self):
        print("🔊 Speaking unauthorized-attempt warning")
        if self.voice_output:
            try:
                self.voice_output.speak(WARNING_MESSAGE, language="en")
            except Exception as e:
                print(f"❌ Voice warning failed: {e}")
        else:
            print("⚠️ No voice output configured — warning not spoken")

    # ==========================
    # CAPTURE
    # ==========================
    def capture(self, kind="unknown"):
        if not self.lock.acquire(blocking=False):
            return
        cam = None
        try:
            cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cam.isOpened():
                print("❌ Camera failed")
                return

            ret, frame = cam.read()
            if not ret:
                print("❌ Frame failed")
                return

            now = datetime.now()
            filename = now.strftime("%Y%m%d_%H%M%S") + ".jpg"
            file_path = os.path.join("intruders", filename)

            if not cv2.imwrite(file_path, frame):
                print("❌ Save failed")
                return

            print(f"✅ Saved {file_path}")
            activity_label = ACTIVITY_LABELS.get(kind, "Activity detected")

            self._append_local_log(filename=filename, activity=activity_label, timestamp=now)
            threading.Thread(target=self.upload, args=(file_path, filename, activity_label), daemon=True).start()

        except Exception as e:
            print("❌ Capture error:", e)
        finally:
            if cam:
                cam.release()
            self.lock.release()

    # ==========================
    # LOCAL LOG
    # ==========================
    def _append_local_log(self, filename, activity, timestamp):
        entry = {
            "filename": filename,
            "activity": activity,
            "timestamp": int(timestamp.timestamp()),
            "date": timestamp.strftime("%d/%m/%Y"),
            "time": timestamp.strftime("%H:%M"),
        }
        with self.log_lock:
            entries = self._read_log_file()
            entries.insert(0, entry)
            entries = entries[:MAX_LOG_ENTRIES]
            self._write_log_file(entries)

    def _read_log_file(self):
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print("❌ Local log read error:", e)
        return []

    def _write_log_file(self, entries):
        try:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        except Exception as e:
            print("❌ Local log write error:", e)

    def get_local_log(self):
        with self.log_lock:
            return self._read_log_file()

    def delete_capture(self, filename: str) -> bool:
        """Real delete — removes the image file and its log entry.
        Kept until this is explicitly called (no auto-expiry)."""
        safe_name = os.path.basename(filename)  # prevent path traversal
        file_path = os.path.join("intruders", safe_name)

        removed_file = False
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                removed_file = True
            except OSError as e:
                print(f"❌ Delete file error: {e}")

        with self.log_lock:
            entries = self._read_log_file()
            new_entries = [e for e in entries if e.get("filename") != safe_name]
            removed_entry = len(new_entries) != len(entries)
            if removed_entry:
                self._write_log_file(new_entries)

        return removed_file or removed_entry

    # ==========================
    # SIGNED UPLOAD (real fix — was unsigned before)
    # ==========================
    def upload(self, file_path, filename, activity="Activity detected"):
        trusted = self.trusted_device_manager.load()
        if not trusted:
            print("❌ Upload skipped — no paired device to sign with")
            return

        device_id = trusted["device_id"]
        secret = bytes.fromhex(trusted["secret_key"])

        print(f"☁️ Uploading {file_path}")

        for attempt in range(3):
            try:
                ts = str(int(time.time()))
                nonce = secrets.token_hex(8)
                sig = generate_signature("upload_intruder", ts, device_id, nonce, secret)

                with open(file_path, "rb") as f:
                    response = requests.post(
                        CLOUD_UPLOAD_URL,
                        files={"file": f},
                        data={
                            "device_id": device_id,
                            "activity": activity,
                            "ts": ts,
                            "nonce": nonce,
                            "sig": sig,
                        },
                        timeout=20,
                    )

                print("☁️ Upload response:", response.status_code, response.text)
                if response.status_code == 200:
                    print("✅ Intruder uploaded (signed)")
                    return

            except Exception as e:
                print("❌ Upload error:", e)

            time.sleep(2)

        print("❌ Upload failed after retries")

    # ==========================
    # ENABLE / DISABLE
    # ==========================
    def enable(self):
        self.freeze_active = True
        self.activity_count = 0
        self._warned_this_session = False
        print("🔒 Freeze enabled")

    def disable(self):
        self.freeze_active = False
        self.activity_count = 0
        self._warned_this_session = False
        print("🔓 Freeze disabled")