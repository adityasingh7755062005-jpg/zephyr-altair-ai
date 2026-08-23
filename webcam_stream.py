# ==============================
# FILE: webcam_stream.py
# HARDENED — real per-device auth, no more hardcoded ID,
# local viewer connections now require a signed message.
# ==============================

import sys
from camera.camera_manager import CameraManager
from camera import camera_state
from cores.trusted_device_manager import TrustedDeviceManager
from network.security import generate_signature, verify_request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import cv2, asyncio, websockets, base64, json, time, traceback, threading, secrets

HOST = "0.0.0.0"
PORT = 8765
CLOUD_URI = "wss://zephyr-altair-ai-server.onrender.com/ws"

JPEG_QUALITY = 25
FRAME_WIDTH = 320
FRAME_HEIGHT = 240
FRAME_DELAY = 0.12

connected_clients = []
cloud_ws = None
cloud_connected = False
cloud_send_lock = None
latest_frame = None
frame_lock = threading.Lock()
camera_running = True
camera_manager = CameraManager()

# ---- Real device identity, loaded from actual pairing ----
_trusted_manager = TrustedDeviceManager()
_trusted = _trusted_manager.load()
if not _trusted:
    print("[WEBCAM] ❌ No paired device found — cannot start camera stream securely")
    sys.exit(1)

DEVICE_ID = _trusted["device_id"]
SECRET = bytes.fromhex(_trusted["secret_key"])


def camera_capture_loop():
    global latest_frame, camera_running
    print("[WEBCAM] Camera thread started")
    while camera_running:
        try:
            cam = camera_state.camera
            if cam is None:
                latest_frame = None
                time.sleep(0.1)
                continue
            ok, frame = cam.read()
            if not ok:
                latest_frame = None
                print("[WEBCAM] Frame Read Failed")
                time.sleep(0.05)
                continue
            frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
            with frame_lock:
                latest_frame = frame.copy()
            camera_state.latest_frame = latest_frame
        except Exception as e:
            print("[WEBCAM] Capture Error:", e)
            time.sleep(1)


async def safe_cloud_send(payload):
    global cloud_ws, cloud_connected, cloud_send_lock
    try:
        if not cloud_connected or cloud_ws is None:
            return False
        async with cloud_send_lock:
            await asyncio.wait_for(cloud_ws.send(payload), timeout=0.5)
            return True
    except Exception:
        cloud_connected = False
        return False


async def cloud_receiver(ws):
    global cloud_connected, camera_running, latest_frame, connected_clients
    try:
        async for message in ws:
            try:
                data = json.loads(message)
                t = data.get("type")

                if t == "viewer_connected":
                    print("[WEBCAM] Viewer Connected - Stream Active")

                elif t == "start_camera":
                    print("[WEBCAM] START CAMERA RECEIVED")
                    latest_frame = None
                    camera_state.latest_frame = None
                    if camera_manager.restart_camera():
                        print("[WEBCAM] Camera Restarted")
                    else:
                        print("[WEBCAM] Camera Restart Failed")

                elif t == "stop_camera":
                    print("[WEBCAM] STOP CAMERA RECEIVED")
                    connected_clients.clear()
                    latest_frame = None
                    camera_state.latest_frame = None
                    camera_manager.stop_camera()
                    print("[WEBCAM] Camera Fully Stopped")

            except Exception as e:
                print("[WEBCAM] Receiver Error:", e)
    except Exception as e:
        cloud_connected = False
        print("[WEBCAM] Cloud Receiver Error:", e)


async def cloud_connection_loop():
    global cloud_ws, cloud_connected
    while True:
        try:
            print("[WEBCAM] Connecting...")
            ws = await websockets.connect(CLOUD_URI, ping_interval=20, ping_timeout=20, max_size=None)
            cloud_ws = ws

            # Signed registration — matches every other privileged
            # message in this project now, instead of a bare claim.
            ts = str(int(time.time()))
            nonce = secrets.token_hex(8)
            sig = generate_signature("camera_auth", ts, DEVICE_ID, nonce, SECRET)

            auth = {
                "type": "camera_auth", "device_id": DEVICE_ID,
                "cmd": "camera_auth", "ts": ts, "nonce": nonce, "sig": sig,
            }
            await ws.send(json.dumps(auth))

            cloud_connected = True
            print("[WEBCAM] Cloud Connected (signed)")
            await cloud_receiver(ws)

        except Exception as e:
            print("[WEBCAM] Cloud:", e)
        finally:
            cloud_connected = False
            cloud_ws = None
            await asyncio.sleep(3)


async def stream_camera():
    _last_diag = 0
    while True:
        try:
            frame = None
            with frame_lock:
                if latest_frame is not None:
                    frame = latest_frame.copy()

            # DIAGNOSTIC: every 5 seconds, print the actual state of
            # everything relevant — this tells us definitively whether
            # the camera has real frames, and whether any viewers are
            # actually registered, instead of guessing.
            now = time.time()
            if now - _last_diag > 5:
                _last_diag = now
                print(f"[WEBCAM][DIAG] has_frame={frame is not None} "
                      f"local_viewers={len(connected_clients)} "
                      f"cloud_connected={cloud_connected}")

            if frame is None:
                await asyncio.sleep(0.01)
                continue

            ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
            if not ok:
                await asyncio.sleep(0.01)
                continue

            jpg = base64.b64encode(buffer).decode()
            payload = json.dumps({"type": "camera_frame", "device_id": DEVICE_ID, "frame": jpg})

            dead = []
            for ws in connected_clients[:]:
                try:
                    await asyncio.wait_for(ws.send(payload), timeout=0.5)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                try:
                    if ws in connected_clients:
                        connected_clients.remove(ws)
                except Exception:
                    pass

            if cloud_connected:
                await safe_cloud_send(payload)

            await asyncio.sleep(FRAME_DELAY)

        except Exception as e:
            print("[WEBCAM] Stream:", e)
            await asyncio.sleep(1)


async def handler(ws):
    """Local viewer connection — requires a signed auth message as
    the very first thing sent, before being allowed to receive any
    frames."""
    authenticated = False
    try:
        print("[WEBCAM] New local connection attempt received")
        first_message = await asyncio.wait_for(ws.recv(), timeout=5)
        print(f"[WEBCAM] First message received: {first_message[:150]}")
        data = json.loads(first_message)

        if data.get("type") != "view_camera_local":
            print(f"[WEBCAM] Local viewer rejected — wrong first message type: {data.get('type')}")
            await ws.close()
            return

        valid, msg = verify_request(
            "view_camera_local", data.get("ts"), DEVICE_ID,
            data.get("sig"), data.get("nonce"), SECRET,
        )
        print(f"[WEBCAM] Signature check: valid={valid} msg={msg}")
        if not valid:
            print(f"[WEBCAM] Local viewer rejected — {msg}")
            await ws.close()
            return

        authenticated = True
        connected_clients.append(ws)
        print(f"[WEBCAM] Local Viewer connected (authenticated) — total viewers now: {len(connected_clients)}")
        await ws.wait_closed()

    except Exception as e:
        print("[WEBCAM] Local viewer error:", e)
    finally:
        if authenticated:
            try:
                if ws in connected_clients:
                    connected_clients.remove(ws)
            except Exception:
                pass
        print("[WEBCAM] Local Viewer disconnected")


async def main():
    global cloud_send_lock
    cloud_send_lock = asyncio.Lock()

    if not camera_manager.start_camera():
        return

    threading.Thread(target=camera_capture_loop, daemon=True).start()

    server = await websockets.serve(handler, HOST, PORT, ping_interval=20, ping_timeout=20, max_size=None)
    print("[WEBCAM] Server Ready (authenticated)")

    asyncio.create_task(cloud_connection_loop())
    asyncio.create_task(stream_camera())

    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()