# ==============================
# FILE: webcam_stream.py
# FINAL STABLE CAMERA STREAM
# THREAD SAFE VERSION
# ==============================

import sys

try:
    sys.stdout.reconfigure(
        encoding="utf-8"
    )
except:
    pass

import cv2
import asyncio
import websockets
import base64
import json
import time
import traceback
import threading

HOST = "0.0.0.0"
PORT = 8765

CLOUD_URI = (
    "wss://zephyr-altair-ai-server.onrender.com/ws"
)

DEVICE_ID = "160c02a2018e7132"

JPEG_QUALITY = 50
FRAME_WIDTH = 640
FRAME_HEIGHT = 360

TARGET_FPS = 15
FRAME_DELAY = 1 / TARGET_FPS

camera = None

connected_clients = set()

cloud_ws = None
cloud_connected = False
cloud_send_lock = None

# ==============================
# SHARED FRAME BUFFER
# ==============================

latest_frame = None
frame_lock = threading.Lock()

camera_running = True


# ==============================
# CAMERA INIT
# ==============================

def initialize_camera():

    global camera

    try:

        camera = cv2.VideoCapture(
            0,
            cv2.CAP_DSHOW
        )

        if not camera.isOpened():

            camera = cv2.VideoCapture(
                0
            )

        if not camera.isOpened():

            raise Exception(
                "Cannot open webcam"
            )

        camera.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            FRAME_WIDTH
        )

        camera.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            FRAME_HEIGHT
        )

        camera.set(
            cv2.CAP_PROP_BUFFERSIZE,
            1
        )

        print(
            "[WEBCAM] Camera Ready"
        )

        return True

    except Exception as e:

        print(e)

        return False


# ==============================
# CAMERA THREAD
# ==============================

def camera_capture_loop():

    global latest_frame
    global camera_running

    print(
        "[WEBCAM] Camera thread started"
    )

    while camera_running:

        try:

            if camera is None:

                time.sleep(1)
                continue

            ok, frame = camera.read()

            if not ok:

                print(
                    "[WEBCAM] Camera read failed"
                )

                time.sleep(0.1)
                continue

            frame = cv2.resize(

                frame,

                (
                    FRAME_WIDTH,
                    FRAME_HEIGHT
                )

            )

            with frame_lock:

                latest_frame = frame.copy()

        except Exception as e:

            print(
                "[WEBCAM] Capture Error:",
                e
            )

            time.sleep(1)


# ==============================
# SAFE CLOUD SEND
# ==============================

async def safe_cloud_send(
        payload
):

    global cloud_ws
    global cloud_connected
    global cloud_send_lock

    try:

        if (

            not cloud_connected

            or

            cloud_ws is None

        ):

            return False

        async with cloud_send_lock:

            await cloud_ws.send(
                payload
            )

            return True

    except Exception as e:

        print(
            "[WEBCAM] Cloud send fail",
            e
        )

        cloud_connected = False

        return False


# ==============================
# CLOUD RECEIVER
# ==============================

async def cloud_receiver(ws):

    global cloud_connected

    try:

        async for message in ws:

            try:

                data = json.loads(
                    message
                )

                t = data.get(
                    "type"
                )

                if t == "viewer_connected":

                    print(
                        "[WEBCAM] Viewer Connected"
                    )

            except:
                pass

    except:

        cloud_connected = False


# ==============================
# CLOUD CONNECT
# ==============================

async def cloud_connection_loop():

    global cloud_ws
    global cloud_connected

    while True:

        try:

            print(
                "[WEBCAM] Connecting..."
            )

            ws = await websockets.connect(

                CLOUD_URI,

                ping_interval=20,

                ping_timeout=20,

                max_size=None

            )

            cloud_ws = ws

            auth = {

                "type":
                    "camera_auth",

                "device_id":
                    DEVICE_ID,

                "role":
                    "laptop_camera"

            }

            await ws.send(

                json.dumps(
                    auth
                )

            )

            cloud_connected = True

            print(
                "[WEBCAM] Cloud Connected"
            )

            print(
                f"[WEBCAM] Auth sent: {DEVICE_ID}"
            )

            await cloud_receiver(
                ws
            )

        except Exception as e:

            print(
                "[WEBCAM]",
                e
            )

        finally:

            cloud_connected = False

            await asyncio.sleep(
                3
            )


# ==============================
# STREAM CAMERA
# ==============================

async def stream_camera():

    while True:

        try:

            frame = None

            with frame_lock:

                if latest_frame is not None:

                    frame = latest_frame.copy()

            if frame is None:

                await asyncio.sleep(0.01)
                continue

            ok, buffer = cv2.imencode(

                ".jpg",

                frame,

                [

                    int(
                        cv2.IMWRITE_JPEG_QUALITY
                    ),

                    JPEG_QUALITY

                ]

            )

            if not ok:

                await asyncio.sleep(0.01)
                continue

            jpg = base64.b64encode(
                buffer
            ).decode()

            payload = json.dumps({

                "type":
                    "camera_frame",

                "device_id":
                    DEVICE_ID,

                "frame":
                    jpg

            })

            # ======================
            # LOCAL VIEWERS
            # ======================

            dead = []

            for ws in connected_clients:

                try:

                    await ws.send(
                        payload
                    )

                except:

                    dead.append(
                        ws
                    )

            for x in dead:

                connected_clients.discard(
                    x
                )

            # ======================
            # CLOUD VIEWERS
            # ======================

            if cloud_connected:

                await safe_cloud_send(
                    payload
                )

            await asyncio.sleep(
                FRAME_DELAY
            )

        except Exception as e:

            print(
                "[WEBCAM] Stream Error:",
                e
            )

            await asyncio.sleep(
                1
            )


# ==============================
# LOCAL SOCKET
# ==============================

async def handler(ws):

    connected_clients.add(
        ws
    )

    print(
        "[WEBCAM] Local Viewer"
    )

    try:

        await asyncio.Future()

    finally:

        connected_clients.discard(
            ws
        )


# ==============================
# MAIN
# ==============================

async def main():

    global cloud_send_lock

    cloud_send_lock = asyncio.Lock()

    if not initialize_camera():

        return

    # ==============================
    # START CAMERA THREAD
    # ==============================

    threading.Thread(

        target=camera_capture_loop,

        daemon=True

    ).start()

    await websockets.serve(

        handler,

        HOST,

        PORT,

        max_size=None

    )

    asyncio.create_task(

        cloud_connection_loop()

    )

    asyncio.create_task(

        stream_camera()

    )

    print(
        "[WEBCAM] Server Ready"
    )

    await asyncio.Future()


if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        pass

    except Exception:

        traceback.print_exc()