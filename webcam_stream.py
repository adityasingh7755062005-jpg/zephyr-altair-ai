# ==============================
# FILE: webcam_stream.py
# ZEPHYR LIVE CAMERA ENGINE
# FULL FIXED CLOUD VERSION
# FINAL STABLE BUILD
# LOCAL + CLOUD STABLE VERSION
# ==============================

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

CLOUD_URI = "wss://zephyr-altair-ai-server.onrender.com/ws"

DEVICE_ID = "160c02a2018e7132"

JPEG_QUALITY = 55

FRAME_WIDTH = 640
FRAME_HEIGHT = 360

TARGET_FPS = 20
FRAME_DELAY = 1 / TARGET_FPS

SHOW_STATS = True

# ==============================
# CAMERA INIT
# ==============================

camera = None

def initialize_camera():

    global camera

    print("📷 Initializing camera...")

    try:

        camera = cv2.VideoCapture(
            0,
            cv2.CAP_DSHOW
        )

        if not camera.isOpened():

            print(
                "⚠️ CAP_DSHOW failed, trying default backend..."
            )

            camera.release()

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

        print("✅ Camera initialized")

        return True

    except Exception as e:

        print(
            f"❌ Camera Init Failed: {e}"
        )

        return False

# ==============================
# LOCAL CLIENTS
# ==============================

connected_clients = set()

# ==============================
# CLOUD
# ==============================

cloud_ws = None
cloud_connected = False
cloud_lock = None

# ==============================
# FPS
# ==============================

fps_counter = 0
fps_timer = time.time()
current_fps = 0

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

                if msg_type == "viewer_connected":

                    print(
                        "\n👁️ Camera Viewer Connected"
                    )

                elif msg_type == "viewer_disconnected":

                    print(
                        "\n📴 Camera Viewer Disconnected"
                    )

            except:
                pass

    except Exception as e:

        print(
            f"\n❌ Cloud Receiver Error: {e}"
        )

    finally:

        cloud_connected = False

# ==============================
# CLOUD PING
# ==============================

async def cloud_ping_loop(ws):

    global cloud_connected

    while cloud_connected:

        try:

            await ws.send(json.dumps({

                "type": "ping",

                "device_id": DEVICE_ID,

                "timestamp": int(time.time())

            }))

        except Exception as e:

            print(
                f"\n❌ Ping Failed: {e}"
            )

            cloud_connected = False

            break

        await asyncio.sleep(10)

# ==============================
# CLOUD CONNECTOR
# ==============================

async def cloud_connection_loop():

    global cloud_ws
    global cloud_connected
    global cloud_lock

    while True:

        try:

            print("\n☁️ Connecting To Cloud...")

            ws = await websockets.connect(

                CLOUD_URI,

                ping_interval=20,

                ping_timeout=20,

                close_timeout=5,

                max_size=None

            )

            async with cloud_lock:

                cloud_ws = ws
                cloud_connected = True

            auth_packet = {

                "type": "camera_auth",

                "device_id": DEVICE_ID,

                "role": "laptop_camera"
            }

            await ws.send(
                json.dumps(auth_packet)
            )

            print("☁️ Cloud Connected")

            receiver_task = asyncio.create_task(
                cloud_receiver(ws)
            )

            ping_task = asyncio.create_task(
                cloud_ping_loop(ws)
            )

            done, pending = await asyncio.wait(

                [
                    receiver_task,
                    ping_task
                ],

                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:

                task.cancel()

        except Exception as e:

            print(
                f"\n❌ Cloud Error: {e}"
            )

        finally:

            cloud_connected = False

            try:

                if cloud_ws:

                    await cloud_ws.close()

            except:
                pass

            cloud_ws = None

            print("\n☁️ Cloud Offline")

            await asyncio.sleep(3)

# ==============================
# CAMERA STREAM
# ==============================

async def stream_camera():

    global fps_counter
    global fps_timer
    global current_fps
    global cloud_connected

    while True:

        try:

            start_time = time.time()

            success, frame = camera.read()

            if not success:

                print(
                    "\n❌ Failed To Read Camera Frame"
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

            encode_param = [

                int(cv2.IMWRITE_JPEG_QUALITY),

                JPEG_QUALITY
            ]

            success, buffer = cv2.imencode(

                ".jpg",

                frame,

                encode_param
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
            # LOCAL STREAM
            # ==============================

            dead_clients = set()

            for ws in connected_clients.copy():

                try:

                    await ws.send(payload)

                except:

                    dead_clients.add(ws)

            connected_clients.difference_update(
                dead_clients
            )

            # ==============================
            # CLOUD STREAM
            # ==============================

            if cloud_connected and cloud_ws:

                try:

                    await cloud_ws.send(payload)

                except Exception as e:

                    print(
                        f"\n❌ Cloud Send Failed: {e}"
                    )

                    cloud_connected = False

            # ==============================
            # FPS
            # ==============================

            fps_counter += 1

            elapsed = (
                time.time() - fps_timer
            )

            if elapsed >= 1:

                current_fps = fps_counter

                if SHOW_STATS:

                    frame_kb = round(
                        len(buffer) / 1024,
                        1
                    )

                    cloud_status = (

                        "ONLINE"

                        if cloud_connected

                        else "OFFLINE"
                    )

                    print(

                        f"\r📷 FPS: {current_fps} | "
                        f"Clients: {len(connected_clients)} | "
                        f"Cloud: {cloud_status} | "
                        f"Frame: {frame_kb} KB",

                        end=""
                    )

                fps_counter = 0
                fps_timer = time.time()

            processing_time = (
                time.time() - start_time
            )

            sleep_time = max(

                0,

                FRAME_DELAY - processing_time
            )

            await asyncio.sleep(
                sleep_time
            )

        except asyncio.CancelledError:

            break

        except Exception as e:

            print(
                f"\n❌ Stream Error: {e}"
            )

            traceback.print_exc()

            await asyncio.sleep(1)

# ==============================
# LOCAL MOBILE HANDLER
# ==============================

async def handler(websocket):

    print("\n✅ Local Mobile Connected")

    connected_clients.add(
        websocket
    )

    try:

        async for message in websocket:

            try:

                data = json.loads(message)

                if data.get("type") == "ping":

                    await websocket.send(

                        json.dumps({
                            "type": "pong"
                        })
                    )

            except:
                pass

    except:

        print(
            "\n❌ Local Mobile Disconnected"
        )

    finally:

        connected_clients.discard(
            websocket
        )

# ==============================
# MAIN
# ==============================

async def main():

    global cloud_lock

    cloud_lock = asyncio.Lock()

    if not initialize_camera():

        return

    print("")
    print("===================================")
    print("✅ ZEPHYR LIVE CAMERA ENGINE")
    print("✅ HYBRID LOCAL + CLOUD")
    print("===================================")

    print(
        f"✅ Local ws://0.0.0.0:{PORT}"
    )

    print(
        f"✅ Cloud: {CLOUD_URI}"
    )

    print(
        f"✅ Resolution: "
        f"{FRAME_WIDTH}x{FRAME_HEIGHT}"
    )

    print(
        f"✅ Target FPS: "
        f"{TARGET_FPS}"
    )

    print("===================================")
    print("")

    server = await websockets.serve(

        handler,

        HOST,

        PORT,

        max_size=None,

        ping_interval=20,

        ping_timeout=20
    )

    stream_task = asyncio.create_task(
        stream_camera()
    )

    cloud_task = asyncio.create_task(
        cloud_connection_loop()
    )

    await asyncio.gather(
        stream_task,
        cloud_task
    )

# ==============================
# CLEANUP
# ==============================

def cleanup():

    print("")
    print("\n🛑 Closing Camera Engine")

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
            f"\n❌ Fatal Error: {e}"
        )

        traceback.print_exc()

        cleanup()