# ==============================
# FILE: webcam_stream.py
# ZEPHYR LIVE CAMERA ENGINE
# HYBRID LOCAL + CLOUD VERSION
# FULL STABLE VERSION
# ==============================

import cv2
import asyncio
import websockets
import base64
import json
import time

# ==============================
# SETTINGS
# ==============================

HOST = "0.0.0.0"
PORT = 8765

# ✅ CLOUD SERVER
CLOUD_URI = "wss://zephyr-altair-ai-server.onrender.com/ws"

# ✅ TRUSTED DEVICE
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

camera = cv2.VideoCapture(
    0,
    cv2.CAP_DSHOW
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

# ==============================
# LOCAL CLIENTS
# ==============================

connected_clients = set()

# ==============================
# CLOUD
# ==============================

cloud_ws = None
cloud_connected = False

# ==============================
# FPS
# ==============================

fps_counter = 0
fps_timer = time.time()
current_fps = 0

# ==============================
# CLOUD CONNECTOR
# ==============================

async def cloud_connection_loop():

    global cloud_ws
    global cloud_connected

    while True:

        ws = None

        try:

            print("\n☁️ Connecting To Cloud...")

            # ==============================
            # CONNECT
            # ==============================

            ws = await websockets.connect(

                CLOUD_URI,

                ping_interval=20,
                ping_timeout=20,

                max_size=None,

                close_timeout=2
            )

            cloud_ws = ws
            cloud_connected = True

            # ==============================
            # AUTH
            # ==============================

            auth_packet = {

                "type": "camera_auth",

                "device_id": DEVICE_ID,

                "role": "laptop_camera"
            }

            await ws.send(
                json.dumps(auth_packet)
            )

            print("☁️ Cloud Connected")

            # ==============================
            # KEEP ALIVE
            # ==============================

            while True:

                try:

                    await ws.send(
                        json.dumps({
                            "type": "ping"
                        })
                    )

                except Exception:
                    break

                await asyncio.sleep(15)

        except asyncio.CancelledError:
            break

        except Exception as e:

            print(
                f"\n❌ Cloud Error: {e}"
            )

        finally:

            cloud_connected = False

            try:

                if ws:

                    await ws.close()

            except:
                pass

            cloud_ws = None

            print("\n☁️ Cloud Offline")

            await asyncio.sleep(5)

# ==============================
# CAMERA STREAM
# ==============================

async def stream_camera():

    global fps_counter
    global fps_timer
    global current_fps
    global cloud_connected
    global cloud_ws

    while True:

        try:

            start_time = time.time()

            # ==============================
            # READ CAMERA
            # ==============================

            success, frame = camera.read()

            if not success:

                await asyncio.sleep(FRAME_DELAY)
                continue

            # ==============================
            # RESIZE
            # ==============================

            frame = cv2.resize(

                frame,

                (
                    FRAME_WIDTH,
                    FRAME_HEIGHT
                )
            )

            # ==============================
            # JPEG COMPRESS
            # ==============================

            encode_param = [

                int(
                    cv2.IMWRITE_JPEG_QUALITY
                ),

                JPEG_QUALITY
            ]

            success, buffer = cv2.imencode(

                ".jpg",

                frame,

                encode_param
            )

            if not success:
                continue

            # ==============================
            # BASE64
            # ==============================

            jpg_as_text = base64.b64encode(
                buffer
            ).decode("utf-8")

            # ==============================
            # PAYLOAD
            # ==============================

            payload_dict = {

                "type": "camera_frame",

                "device_id": DEVICE_ID,

                "frame": jpg_as_text,

                "fps": current_fps,

                "width": FRAME_WIDTH,

                "height": FRAME_HEIGHT,

                "timestamp": int(
                    time.time() * 1000
                )
            }

            payload = json.dumps(
                payload_dict
            )

            # ==============================
            # LOCAL STREAM
            # ==============================

            dead_clients = set()

            for ws in connected_clients:

                try:

                    await ws.send(payload)

                except Exception:

                    dead_clients.add(ws)

            connected_clients.difference_update(
                dead_clients
            )

            # ==============================
            # CLOUD STREAM
            # ==============================

            if (
                cloud_connected
                and
                cloud_ws is not None
            ):

                try:

                    await cloud_ws.send(
                        payload
                    )

                except Exception:

                    cloud_connected = False

                    print(
                        "\n❌ Cloud Send Failed"
                    )

            # ==============================
            # FPS COUNTER
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

            # ==============================
            # FPS LOCK
            # ==============================

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

                msg_type = data.get(
                    "type"
                )

                # ==============================
                # PING
                # ==============================

                if msg_type == "ping":

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

        print(

            f"\n📴 Active Local Clients: "
            f"{len(connected_clients)}"
        )

# ==============================
# MAIN
# ==============================

async def main():

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

    # ==============================
    # LOCAL SERVER
    # ==============================

    server = await websockets.serve(

        handler,

        HOST,

        PORT,

        max_size=None,

        ping_interval=20,

        ping_timeout=20
    )

    # ==============================
    # TASKS
    # ==============================

    stream_task = asyncio.create_task(
        stream_camera()
    )

    cloud_task = asyncio.create_task(
        cloud_connection_loop()
    )

    try:

        await server.wait_closed()

    finally:

        stream_task.cancel()
        cloud_task.cancel()

# ==============================
# CLEANUP
# ==============================

def cleanup():

    print("")
    print("\n🛑 Closing Camera Engine")

    try:
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

        cleanup()