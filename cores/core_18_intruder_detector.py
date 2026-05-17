# ==============================
# FILE 18: core_18_intruder_detector.py
# FULL FIXED DEBUG VERSION
# ==============================

import cv2
import os
import time
import threading
import requests

from datetime import datetime
from pynput import keyboard, mouse


CLOUD_UPLOAD_URL = (
    "https://zephyr-altair-ai-server.onrender.com/upload_intruder"
)

DEVICE_ID = "160c02a2018e7132"


class IntruderDetector:

    def __init__(self):

        self.freeze_active = False

        self.last_upload = 0

        self.lock = threading.Lock()

        os.makedirs(
            "intruders",
            exist_ok=True
        )

        print(
            "🚨 Intruder detector ready"
        )

        keyboard.Listener(

            on_press=self._on_activity

        ).start()

        mouse.Listener(

            on_move=self._on_activity,

            on_click=self._on_activity

        ).start()


    # ==========================
    # ACTIVITY
    # ==========================

    def _on_activity(self,*args):

        if not self.freeze_active:
            return

        if (

            time.time()

            -

            self.last_upload

            <

            5

        ):
            return

        self.last_upload = time.time()

        print(
            "⚠️ Activity during freeze"
        )

        threading.Thread(

            target=self.capture,

            daemon=True

        ).start()


    # ==========================
    # CAPTURE
    # ==========================

    def capture(self):

        if not self.lock.acquire(
            blocking=False
        ):
            return

        cam = None

        try:

            print(
                "📷 Opening webcam..."
            )

            cam = cv2.VideoCapture(

                0,

                cv2.CAP_DSHOW
            )

            if not cam.isOpened():

                print(
                    "❌ Camera failed"
                )

                return


            ret, frame = cam.read()

            if not ret:

                print(
                    "❌ Frame failed"
                )

                return


            filename = (

                datetime.now()

                .strftime(

                    "%Y%m%d_%H%M%S"
                )

                +

                ".jpg"
            )

            file_path = (

                "intruders/"

                +

                filename
            )

            ok = cv2.imwrite(

                file_path,

                frame
            )

            if not ok:

                print(
                    "❌ Save failed"
                )

                return


            print(
                f"✅ Saved {file_path}"
            )


            threading.Thread(

                target=self.upload,

                args=(file_path,),

                daemon=True

            ).start()


        except Exception as e:

            print(
                "❌ Capture error:",
                e
            )

        finally:

            if cam:
                cam.release()

            self.lock.release()


    # ==========================
    # UPLOAD
    # ==========================

    def upload(
        self,
        file_path
    ):

        print(
            f"☁️ Uploading {file_path}"
        )

        for attempt in range(3):

            try:

                with open(
                    file_path,
                    "rb"
                ) as f:

                    response = requests.post(

                        CLOUD_UPLOAD_URL,

                        files={

                            "file": f
                        },

                        data={

                            "device_id":
                            DEVICE_ID
                        },

                        timeout=20
                    )

                print(

                    "☁️ Upload response:",

                    response.status_code,

                    response.text
                )


                if (

                    response.status_code

                    ==

                    200
                ):

                    print(
                        "✅ Intruder uploaded"
                    )

                    return


            except Exception as e:

                print(
                    "❌ Upload error:",
                    e
                )


            time.sleep(2)


        print(
            "❌ Upload failed after retries"
        )


    # ==========================
    # ENABLE
    # ==========================

    def enable(self):

        self.freeze_active = True

        print(
            "🔒 Freeze enabled"
        )


    # ==========================
    # DISABLE
    # ==========================

    def disable(self):

        self.freeze_active = False

        print(
            "🔓 Freeze disabled"
        )