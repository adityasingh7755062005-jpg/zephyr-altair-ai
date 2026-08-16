# zephyr_cloud_server.py
# HARDENED — verifies real signatures, not just a device_id string match.
# The relay never learns your secret from strangers — only YOUR desktop
# (which already has it from local pairing) can establish it.

import json, os, time, shutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
import firebase_admin
from firebase_admin import credentials, messaging

from network.security import verify_request

app = FastAPI()

if not firebase_admin._apps:
    try:
        firebase_json = os.environ.get("FIREBASE_KEY_JSON")
        if firebase_json:
            cred = credentials.Certificate(json.loads(firebase_json))
            firebase_admin.initialize_app(cred)
    except Exception as e:
        print("Firebase:", e)

mobile_clients = {}
desktop_clients = {}
camera_streamers = {}
camera_viewers = {}
fcm_tokens = {}

# In-memory only — populated ONLY by a device's own desktop connection,
# never persisted, never accepted from an unverified mobile client.
device_secrets = {}

UPLOAD_DIR = "intruders"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/intruders", StaticFiles(directory=UPLOAD_DIR), name="intruders")


async def safe_send(ws, data):
    try:
        await ws.send_text(data)
        return True
    except Exception:
        return False


def verify_signed(msg: dict) -> tuple:
    """Every privileged message (register-as-mobile, command, camera
    actions) must carry cmd/ts/device_id/sig/nonce and pass real HMAC
    verification against the secret THIS device's desktop established."""
    device_id = msg.get("device_id")
    secret_hex = device_secrets.get(device_id)
    if not secret_hex:
        return False, "device not paired with this relay yet"
    secret = bytes.fromhex(secret_hex)
    return verify_request(
        msg.get("cmd", msg.get("type")), msg.get("ts"), device_id,
        msg.get("sig"), msg.get("nonce"), secret,
    )


@app.post("/register_fcm")
async def register_fcm(data: dict):
    # Also requires a valid signature now — previously anyone could
    # register ANY device_id with ANY token, letting them redirect
    # your intruder-alert push notifications to their own phone.
    device_id = data.get("device_id", "")
    secret_hex = device_secrets.get(device_id)
    if not secret_hex:
        return {"status": "error", "error": "unpaired device"}

    valid, msg = verify_request(
        "register_fcm", data.get("ts"), device_id,
        data.get("sig"), data.get("nonce"), bytes.fromhex(secret_hex),
    )
    if not valid:
        return {"status": "error", "error": msg}

    fcm_tokens[device_id] = data.get("fcm_token", "")
    print("FCM saved:", device_id)
    return {"status": "ok"}


@app.post("/upload_intruder")
async def upload_intruder(file: UploadFile = File(...), device_id: str = Form(...), sig: str = Form(...), ts: str = Form(...), nonce: str = Form(...)):
    # Now requires a valid signature too — no more anonymous uploads
    # that could spam fake "intruder" push notifications.
    secret_hex = device_secrets.get(device_id)
    if not secret_hex:
        return {"status": "error", "error": "unpaired device"}
    valid, msg = verify_request("upload_intruder", ts, device_id, sig, nonce, bytes.fromhex(secret_hex))
    if not valid:
        return {"status": "error", "error": msg}

    try:
        filename = f"{device_id}_{int(time.time())}.jpg"
        path = os.path.join(UPLOAD_DIR, filename)
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        image_url = f"https://zephyr-altair-ai-server.onrender.com/intruders/{filename}"

        token = fcm_tokens.get(device_id)
        if token:
            messaging.send(messaging.Message(
                token=token,
                data={"type": "intruder", "image_url": image_url,
                      "time": time.strftime("%H:%M"), "date": time.strftime("%d/%m/%Y"),
                      "activity": "Movement detected"},
            ))
        return {"status": "ok", "url": image_url}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.websocket("/ws")
async def ws(socket: WebSocket):
    await socket.accept()
    device_id = None

    try:
        while True:
            raw = await socket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "register":
                device_id = msg.get("device_id")
                role = msg.get("role", "mobile")

                if role == "desktop":
                    # ONLY the desktop, which got this secret via real
                    # local pairing, can establish it in the relay.
                    secret_key = msg.get("secret_key")
                    if not secret_key:
                        await socket.close()
                        return
                    device_secrets[device_id] = secret_key
                    desktop_clients[device_id] = socket
                else:
                    # Mobile must PROVE it knows the secret already
                    # established by the desktop — no free registration.
                    valid, err = verify_signed(msg)
                    if not valid:
                        print(f"❌ Mobile registration rejected: {err}")
                        await socket.close()
                        return
                    mobile_clients[device_id] = socket

                await safe_send(socket, json.dumps({"type": "auth_ok"}))

            elif msg_type == "camera_auth":
                device_id = msg.get("device_id")
                if device_id not in device_secrets:
                    await socket.close()
                    return
                old = camera_streamers.pop(device_id, None)
                if old:
                    try:
                        await old.close()
                    except Exception:
                        pass
                camera_streamers[device_id] = socket
                await safe_send(socket, json.dumps({"type": "auth_ok"}))

            elif msg_type == "view_camera":
                valid, err = verify_signed(msg)
                if not valid:
                    print(f"❌ view_camera rejected: {err}")
                    await socket.close()
                    return
                viewer = msg.get("viewer_device")
                target = msg.get("target_device")
                old_viewer = camera_viewers.pop(viewer, None)
                if old_viewer:
                    try:
                        await old_viewer.close()
                    except Exception:
                        pass
                camera_viewers[viewer] = socket
                streamer = camera_streamers.get(target)
                if streamer:
                    await safe_send(streamer, json.dumps({"type": "viewer_connected"}))

            elif msg_type == "camera_frame":
                dead = []
                for vid, vws in list(camera_viewers.items()):
                    if not await safe_send(vws, raw):
                        dead.append(vid)
                for x in dead:
                    camera_viewers.pop(x, None)

            elif msg_type == "command":
                # THE critical fix: every command must carry a valid
                # signature verified against the target device's real
                # secret. A bare device_id claim is no longer enough.
                valid, err = verify_signed(msg)
                if not valid:
                    print(f"❌ COMMAND REJECTED: {err}")
                    continue

                target = msg.get("target")
                action = msg.get("action")
                desktop = desktop_clients.get(target)
                if desktop:
                    await safe_send(desktop, json.dumps({"type": "command", "action": action}))
                    print(f"✅ Forwarded verified command: {action}")

            elif msg_type in ("start_camera", "stop_camera"):
                valid, err = verify_signed(msg)
                if not valid:
                    print(f"❌ {msg_type} rejected: {err}")
                    continue
                target = msg.get("target_device")
                streamer = camera_streamers.get(target)
                if streamer:
                    await safe_send(streamer, json.dumps({"type": msg_type}))

            elif msg_type == "ping":
                await safe_send(socket, json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(e)
    finally:
        if device_id:
            mobile_clients.pop(device_id, None)
            desktop_clients.pop(device_id, None)
            camera_viewers.pop(device_id, None)
            if camera_streamers.get(device_id) is socket:
                camera_streamers.pop(device_id, None)