# cores/core_18_intruder_detector.py

import cv2
import os
from datetime import datetime
from pynput import keyboard, mouse


class IntruderDetector:

    def __init__(self):

        self.freeze_active = False

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

    # ==========================
    # ACTIVITY DETECTION
    # ==========================

    def _on_activity(self, *args):

        if not self.freeze_active:
            return

        print("[Core 18] Intruder activity detected")

        self.capture_photo()

    # ==========================
    # CAPTURE WEBCAM
    # ==========================

    def capture_photo(self):

        try:

            cam = cv2.VideoCapture(0)

            ret, frame = cam.read()

            if ret:

                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

                filename = f"intruders/intruder_{timestamp}.jpg"

                cv2.imwrite(filename, frame)

                print(f"[Core 18] Intruder photo saved: {filename}")

            cam.release()

        except Exception as e:

            print("[Core 18] Intruder capture failed:", e)

    # ==========================
    # CONTROL
    # ==========================

    def enable(self):

        self.freeze_active = True

    def disable(self):

        self.freeze_active = False