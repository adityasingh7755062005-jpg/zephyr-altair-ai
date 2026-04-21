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

        if now - self.last_upload_time < 5:
            return

        self.last_upload_time = now

        print("[Core 18] Intruder activity detected")

        self.capture_photo()

    def capture_photo(self):

        try:

            cam = cv2.VideoCapture(0)
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

            cam.release()

        except Exception as e:
            print("[Core 18] Intruder capture failed:", e)

    def upload_intruder_image(self, file_path):

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

        except Exception as e:
            print("[Core 18] Upload failed:", e)

    def enable(self):
        self.freeze_active = True

    def disable(self):
        self.freeze_active = False