# ==============================
# FILE 18: core_18_intruder_detector.py
# ==============================

import cv2
import os
import time
import threading
import requests
from datetime import datetime
from pynput import keyboard, mouse

CLOUD_UPLOAD_URL = "https://zephyr-altair-ai-server.onrender.com/upload_intruder"
DEVICE_ID = "160c02a2018e7132"


class IntruderDetector:

    def __init__(self):
        self.freeze_active = False
        self.last_upload = 0
        self.lock = threading.Lock()

        os.makedirs("intruders", exist_ok=True)

        keyboard.Listener(on_press=self._on_activity).start()
        mouse.Listener(
            on_move=self._on_activity,
            on_click=self._on_activity
        ).start()

    def _on_activity(self, *args):

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
            cam = cv2.VideoCapture(0)

            if not cam.isOpened():
                return

            ret, frame = cam.read()

            if ret:
                filename = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = f"intruders/{filename}.jpg"

                success = cv2.imwrite(file_path, frame)

                if success and os.path.exists(file_path):
                    threading.Thread(
                        target=self.upload,
                        args=(file_path,),
                        daemon=True
                    ).start()

        finally:
            if cam is not None:
                cam.release()
            self.lock.release()

    def upload(self, file_path):

        for _ in range(3):
            try:
                with open(file_path, "rb") as f:
                    response = requests.post(
                        CLOUD_UPLOAD_URL,
                        files={"file": f},
                        data={"device_id": DEVICE_ID},
                        timeout=10
                    )

                    if response.status_code == 200:
                        return

            except:
                pass

            time.sleep(2)

    def enable(self):
        self.freeze_active = True

    def disable(self):
        self.freeze_active = False