# ==============================
# FILE: webcam_stream.py
# FINAL STABLE CAMERA STREAM
# ULTRA STABLE VERSION
# FIXED FREEZE + RECONNECT ISSUE
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
import os 

HOST = "0.0.0.0"
PORT = 8765

CLOUD_URI = (
    "wss://zephyr-altair-ai-server.onrender.com/ws"
)

DEVICE_ID = "160c02a2018e7132"

# ==============================
# STREAM SETTINGS
# ==============================

JPEG_QUALITY = 25

FRAME_WIDTH = 320
FRAME_HEIGHT = 240

TARGET_FPS = 8

FRAME_DELAY = 0.12

camera = None

# FIXED:
connected_clients = []

cloud_ws = None
cloud_connected = False
cloud_send_lock = None

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

        print(
            "[WEBCAM]",
            e
        )

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

            cam = camera

            if cam is None:

                time.sleep(0.1)

                continue

            ok, frame = cam.read()

            if not ok:

                print("[WEBCAM] Frame Read Failed"
                )

                time.sleep(0.02)

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

            # FIXED:
            await asyncio.wait_for(

                cloud_ws.send(
                    payload
                ),

                timeout=0.5

            )

            return True

    except Exception:

        cloud_connected = False

        return False


# ==============================
# CLOUD RECEIVER
# ==============================

async def cloud_receiver(ws):

    global cloud_connected
    global camera_running
    global camera
    global latest_frame

    try:

        async for message in ws:
            
            try:
                
                data = json.loads(message)
                t = data.get("type")
                

                # ======================
                # VIEWER CONNECTED
                # ======================

                if t == "viewer_connected":

                    print(
                        "[WEBCAM] Viewer Connected"
                    )

                # ======================
                # START CAMERA
                # ======================

                elif t == "start_camera":

                    print(
                        "[WEBCAM] START CAMERA RECEIVED"
                    )

                    latest_frame = None

                    temp = camera
                    camera = None

                    if temp is not None:  
                        
                        try:
                          temp.release()
                        except:
                              pass

                    await asyncio.sleep(1)

                    if initialize_camera():

                        print(
                            "[WEBCAM] Camera Restarted"
                        )

                # ======================
                # STOP CAMERA
                # ======================

                elif t == "stop_camera":

                    print(
                        "[WEBCAM] STOP CAMERA RECEIVED"
                    )

                    try:

                        temp = camera
                        camera = None

                        if temp is not None:

                            temp.release()

                            latest_frame = None

                            print(
                                "[WEBCAM] Camera Released"
                            )

                    except Exception as e:

                        print(
                            "[WEBCAM] Stop Error:",
                            e
                        )

            except Exception as e:

                    print(
                        "[WEBCAM] Receiver Error:",
                       
                        e
                 )

    except Exception as e:

                           cloud_connected = False

                           print(
                               "[WEBCAM] Cloud Receiver Error:", e
                               )

# ==============================
# CLOUD LOOP
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

            await cloud_receiver(
                ws
            )

        except Exception as e:

            print(
                "[WEBCAM] Cloud:",
                e
            )

        finally:

            cloud_connected = False

            await asyncio.sleep(3)


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
            # LOCAL CLIENTS
            # ======================

            dead = []

            # FIXED:
            for ws in connected_clients[:]:

                try:

                    await asyncio.wait_for(

                        ws.send(
                            payload
                        ),

                        timeout=0.5

                    )

                except:

                    dead.append(
                        ws
                    )

            for ws in dead:

                try:

                    if ws in connected_clients:

                        connected_clients.remove(
                            ws
                        )

                except:
                    pass

            # ======================
            # CLOUD
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
                "[WEBCAM] Stream:",
                e
            )

            await asyncio.sleep(1)


# ==============================
# LOCAL VIEWER
# ==============================

async def handler(ws):

    try:

        # FIXED:
        if ws not in connected_clients:

            connected_clients.append(
                ws
            )

        print(
            "[WEBCAM] Local Viewer"
        )

        # FIXED:
        while True:

            await asyncio.sleep(1)

    except:
        pass

    finally:

        try:

            if ws in connected_clients:

                connected_clients.remove(
                    ws
                )

        except:
            pass


# ==============================
# MAIN
# ==============================

async def main():

    global cloud_send_lock

    cloud_send_lock = asyncio.Lock()

    if not initialize_camera():

        return

    # ==============================
    # CAMERA THREAD
    # ==============================

    threading.Thread(

        target=camera_capture_loop,

        daemon=True

    ).start()

    # ==============================
    # START LOCAL SERVER
    # ==============================

    server = await websockets.serve(

        handler,

        HOST,

        PORT,

        ping_interval=20,

        ping_timeout=20,

        max_size=None

    )

    print(
        "[WEBCAM] Server Ready"
    )

    # ==============================
    # START TASKS
    # ==============================

    asyncio.create_task(
        cloud_connection_loop()
    )

    asyncio.create_task(
        stream_camera()
    )

    await server.wait_closed()


if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        pass

    except Exception:

        traceback.print_exc()