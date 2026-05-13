# ==============================
# FILE: webcam_stream.py
# ZEPHYR LIVE CAMERA ENGINE
# FINAL PRODUCTION STABLE VERSION
# FULL CLOUD + LOCAL STABILIZED
# NETWORK SWITCH FIXED
# FRAME FREEZE FIXED
# VIEWER DELIVERY FIXED
# LOW LOG VERSION
# ==============================

import sys

# ==============================
# WINDOWS UTF-8 FIX
# ==============================

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

# ==============================
# SETTINGS
# ==============================

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

SHOW_STATS = True

# ==============================
# GLOBALS
# ==============================

camera = None

connected_clients = set()

cloud_ws = None

cloud_connected = False

cloud_send_lock = None

fps_counter = 0

fps_timer = time.time()

current_fps = 0

last_stats_log = 0

# ==============================
# CAMERA INIT
# ==============================

def initialize_camera():

    global camera

    print(
        "[WEBCAM] Initializing camera..."
    )

    try:

        camera = cv2.VideoCapture(
            0,
            cv2.CAP_DSHOW
        )

        if not camera.isOpened():

            print(
                "[WEBCAM] CAP_DSHOW failed"
            )

            try:
                camera.release()
            except:
                pass

            camera = cv2.VideoCapture(0)

        if not camera.isOpened():

            raise Exception(
                "Could not open webcam"
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
            "[WEBCAM] Camera initialized"
        )

        return True

    except Exception as e:

        print(
            f"[WEBCAM] Camera Init Failed: {e}"
        )

        traceback.print_exc()

        return False

# ==============================
# SAFE LOCAL SEND
# ==============================

async def safe_local_send(
    ws,
    payload
):

    try:

        await ws.send(payload)

        return True

    except:

        return False

# ==============================
# SAFE CLOUD SEND
# ==============================

async def safe_cloud_send(payload):

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

            try:

                await cloud_ws.send(
                    payload
                )

                return True

            except websockets.ConnectionClosed:

                cloud_connected = False

                return False

    except Exception as e:

        print(
            f"\n[WEBCAM] Cloud Send Failed: {e}"
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

                data = json.loads(message)

                msg_type = data.get("type")

                if msg_type == "auth_ok":

                    print(
                        "[WEBCAM] Cloud Auth OK"
                    )

                elif msg_type == "viewer_connected":

                    print(
                        "[WEBCAM] Cloud Viewer Connected"
                    )

                elif msg_type == "viewer_disconnected":

                    print(
                        "[WEBCAM] Cloud Viewer Disconnected"
                    )

            except:
                pass

    except websockets.ConnectionClosed:

        pass

    except Exception as e:

        print(
            f"\n[WEBCAM] Cloud Receiver Error: {e}"
        )

    finally:

        cloud_connected = False

# ==============================
# CLOUD PING LOOP
# ==============================

async def cloud_ping_loop():

    while True:

        try:

            if cloud_connected:

                payload = {

                    "type": "ping",

                    "device_id": DEVICE_ID,

                    "timestamp": int(
                        time.time()
                    )
                }

                await safe_cloud_send(
                    json.dumps(payload)
                )

            await asyncio.sleep(15)

        except:

            await asyncio.sleep(3)

# ==============================
# CLOUD CONNECTOR
# ==============================

async def cloud_connection_loop():

    global cloud_ws
    global cloud_connected

    while True:

        try:

            print(
                "[WEBCAM] Connecting To Cloud..."
            )

            ws = await websockets.connect(

                CLOUD_URI,

                ping_interval=None,

                ping_timeout=None,

                close_timeout=10,

                max_size=None,

                max_queue=None
            )

            cloud_ws = ws

            auth_packet = {

                "type": "camera_auth",

                "device_id": DEVICE_ID,

                "role": "laptop_camera"
            }

            await ws.send(
                json.dumps(auth_packet)
            )

            cloud_connected = True

            print(
                "[WEBCAM] Cloud Connected"
            )

            await cloud_receiver(ws)

        except Exception as e:

            print(
                f"[WEBCAM] Cloud Error: {e}"
            )

        finally:

            cloud_connected = False

            try:

                if cloud_ws:

                    await cloud_ws.close()

            except:
                pass

            cloud_ws = None

            print(
                "[WEBCAM] Cloud Reconnecting..."
            )

            await asyncio.sleep(3)

# ==============================
# STREAM CAMERA
# ==============================

async def stream_camera():

    global fps_counter
    global fps_timer
    global current_fps
    global last_stats_log

    while True:

        try:

            start_time = time.time()

            if camera is None:

                await asyncio.sleep(1)

                continue

            success, frame = camera.read()

            if not success:

                print(
                    "[WEBCAM] Camera Read Failed"
                )

                await asyncio.sleep(1)

                continue

            frame = cv2.resize(

                frame,

                (
                    FRAME_WIDTH,
                    FRAME_HEIGHT
                )
            )

            success, buffer = cv2.imencode(

                ".jpg",

                frame,

                [
                    int(
                        cv2.IMWRITE_JPEG_QUALITY
                    ),
                    JPEG_QUALITY
                ]
            )

            if not success:

                continue

            jpg_as_text = base64.b64encode(
                buffer
            ).decode("utf-8")

            payload = json.dumps({

                "type": "camera_frame",

                "device_id": DEVICE_ID,

                "frame": jpg_as_text,

                "fps": current_fps,

                "width": FRAME_WIDTH,

                "height": FRAME_HEIGHT,

                "timestamp": int(
                    time.time() * 1000
                )
            })

            # ==============================
            # LOCAL CLIENTS
            # ==============================

            dead_clients = set()

            for ws in connected_clients.copy():

                ok = await safe_local_send(
                    ws,
                    payload
                )

                if not ok:

                    dead_clients.add(ws)

            connected_clients.difference_update(
                dead_clients
            )

            # ==============================
            # CLOUD SEND
            # ==============================

            if cloud_connected:

                await safe_cloud_send(
                    payload
                )

            # ==============================
            # FPS
            # ==============================

            fps_counter += 1

            elapsed = (
                time.time() - fps_timer
            )

            if elapsed >= 1:

                current_fps = fps_counter

                fps_counter = 0

                fps_timer = time.time()

                # ==============================
                # REDUCED LOGS
                # ==============================

                if SHOW_STATS:

                    if (

                        time.time()
                        - last_stats_log

                        >= 15
                    ):

                        cloud_status = (

                            "ONLINE"

                            if cloud_connected

                            else "OFFLINE"
                        )

                        print(

                            f"[WEBCAM] "
                            f"FPS={current_fps} | "
                            f"Local={len(connected_clients)} | "
                            f"Cloud={cloud_status}"
                        )

                        last_stats_log = (
                            time.time()
                        )

            processing_time = (
                time.time() - start_time
            )

            sleep_time = max(

                0,

                FRAME_DELAY
                - processing_time
            )

            await asyncio.sleep(
                sleep_time
            )

        except asyncio.CancelledError:

            break

        except Exception as e:

            print(
                f"\n[WEBCAM] Stream Error: {e}"
            )

            traceback.print_exc()

            await asyncio.sleep(1)

# ==============================
# LOCAL MOBILE HANDLER
# ==============================

async def handler(websocket):

    connected_clients.add(
        websocket
    )

    print(
        "[WEBCAM] Local Viewer Connected"
    )

    try:

        async for message in websocket:

            try:

                data = json.loads(message)

                if (
                    data.get("type")
                    == "ping"
                ):

                    await websocket.send(

                        json.dumps({
                            "type": "pong"
                        })
                    )

            except:
                pass

    except:
        pass

    finally:

        connected_clients.discard(
            websocket
        )

        print(
            "[WEBCAM] Local Viewer Disconnected"
        )

# ==============================
# MAIN
# ==============================

async def main():

    global cloud_send_lock

    cloud_send_lock = asyncio.Lock()

    if not initialize_camera():

        return

    print("")
    print("===================================")
    print("[WEBCAM] ZEPHYR CAMERA ENGINE")
    print("[WEBCAM] LOCAL + CLOUD READY")
    print("===================================")

    server = await websockets.serve(

        handler,

        HOST,

        PORT,

        max_size=None,

        ping_interval=30,

        ping_timeout=30
    )

    print(
        f"[WEBCAM] Local WS: "
        f"ws://0.0.0.0:{PORT}"
    )

    print(
        f"[WEBCAM] Cloud WS: "
        f"{CLOUD_URI}"
    )

    stream_task = asyncio.create_task(
        stream_camera()
    )

    cloud_task = asyncio.create_task(
        cloud_connection_loop()
    )

    ping_task = asyncio.create_task(
        cloud_ping_loop()
    )

    try:

        await asyncio.Future()

    finally:

        stream_task.cancel()

        cloud_task.cancel()

        ping_task.cancel()

        server.close()

        await server.wait_closed()

# ==============================
# CLEANUP
# ==============================

def cleanup():

    global camera

    print(
        "\n[WEBCAM] Closing Camera Engine"
    )

    try:

        if camera:

            camera.release()

    except:
        pass

    try:

        cv2.destroyAllWindows()

    except:
        pass

# ==============================
# START
# ==============================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        cleanup()

    except Exception as e:

        print(
            f"\n[WEBCAM] Fatal Error: {e}"
        )

        traceback.print_exc()

        cleanup()