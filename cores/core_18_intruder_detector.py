import cv2
import os
from datetime import datetime
from pynput import keyboard, mouse
import requests
import threading
import time

CLOUD_UPLOAD_URL = "https://zephyr-altair-ai-server.onrender.com/upload_intruder"
DEVICE_ID = "160c02a2018e7132"


class IntruderDetector:

    def __init__(self):

        self.freeze_active = False
        self.last_upload_time = 0

        # 🔥 NEW: prevent parallel camera usage
        self.capture_lock = threading.Lock()

        os.makedirs("intruders", exist_ok=True)

        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_activity
        )

        self.mouse_listener = mouse.Listener(
            on_move=self._on_activity,
            on_click=self._on_activity,
            on_scroll=self._on_activity
        )

        self.keyboard_listener.start()
        self.mouse_listener.start()

    def _on_activity(self, *args):

        if not self.freeze_active:
            return

        now = time.time()

        # 🔥 COOLDOWN (prevents spam + camera crash)
        if now - self.last_upload_time < 5:
            return

        self.last_upload_time = now

        print("[Core 18] Intruder activity detected")

        # 🔥 THREAD SAFE CALL
        threading.Thread(
            target=self.capture_photo,
            daemon=True
        ).start()

    def capture_photo(self):

        # 🔥 PREVENT MULTIPLE CAMERA ACCESS
        if not self.capture_lock.acquire(blocking=False):
            return

        cam = None

        try:
            cam = cv2.VideoCapture(0)

            if not cam.isOpened():
                print("[Core 18] Camera not available")
                return

            ret, frame = cam.read()

            if ret:

                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"intruders/intruder_{timestamp}.jpg"

                cv2.imwrite(filename, frame)

                print(f"[Core 18] Intruder photo saved: {filename}")

                threading.Thread(
                    target=self.upload_intruder_image,
                    args=(filename,),
                    daemon=True
                ).start()

            else:
                print("[Core 18] Camera read failed")

        except Exception as e:
            print("[Core 18] Intruder capture failed:", e)

        finally:
            if cam:
                cam.release()

            self.capture_lock.release()

    def upload_intruder_image(self, file_path):

        # 🔥 RETRY SYSTEM (guaranteed delivery)
        for attempt in range(3):
            try:

                with open(file_path, "rb") as img:

                    files = {
                        "file": img
                    }

                    data = {
                        "device_id": DEVICE_ID,
                        "activity": "Unauthorized activity detected"
                    }

                    response = requests.post(
                        CLOUD_UPLOAD_URL,
                        files=files,
                        data=data,
                        timeout=10
                    )

                    print(f"[Core 18] Upload response: {response.status_code}")

                    if response.status_code == 200:
                        return  # ✅ SUCCESS

            except Exception as e:
                print(f"[Core 18] Upload failed (attempt {attempt+1}):", e)

            time.sleep(2)  # 🔁 wait before retry

        print("[Core 18] ❌ Upload permanently failed")

    def enable(self):
        self.freeze_active = True

    def disable(self):
        self.freeze_active = False