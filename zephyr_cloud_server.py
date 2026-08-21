# zephyr_cloud_server.py
# Merged: real per-device signature verification (from the security
# rebuild — the command handler had ZERO verification in the version
# you sent) + your new intruder log storage, FCM notifications, and
# a delete endpoint.

import json, os, time, shutil, threading
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
            print("✅ Firebase Ready")
    except Exception as e:
        print("Firebase:", e)

mobile_clients = {}
desktop_clients = {}
camera_streamers = {}
camera_viewers = {}
fcm_tokens = {}

# In-memory only — populated ONLY by a device's own desktop
# connection (which already has the real secret from local pairing),
# never accepted from an unverified mobile client.
device_secrets = {}

UPLOAD_DIR = "intruders"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/intruders", StaticFiles(directory=UPLOAD_DIR), name="intruders")

# ==========================
# INTRUDER METADATA STORE
# NOTE: Render's free tier disk is EPHEMERAL — wiped on restart. This
# is fine as a short-lived relay: the phone downloads + keeps its own
# permanent copy. Don't rely on this as long-term storage.
# ==========================
INTRUDER_LOG_FILE = "intruder_logs.json"
intruder_logs_lock = threading.Lock()


def _load_intruder_logs():
    try:
        if os.path.exists(INTRUDER_LOG_FILE):
            with open(INTRUDER_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print("Intruder log read error:", e)
    return {}


def _save_intruder_logs(store):
    try:
        with open(INTRUDER_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)
    except Exception as e:
        print("Intruder log write error:", e)


def add_intruder_log(device_id, entry):
    with intruder_logs_lock:
        store = _load_intruder_logs()
        device_entries = store.get(device_id, [])
        device_entries.insert(0, entry)
        store[device_id] = device_entries[:200]
        _save_intruder_logs(store)


def get_intruder_logs(device_id):
    with intruder_logs_lock:
        return _load_intruder_logs().get(device_id, [])


def remove_intruder_log(device_id, filename):
    with intruder_logs_lock:
        store = _load_intruder_logs()
        entries = store.get(device_id, [])
        store[device_id] = [e for e in entries if e.get("filename") != filename]
        _save_intruder_logs(store)


async def safe_send(ws, data):
    try:
        await ws.send_text(data)
        return True
    except Exception:
        return False


def verify_signed(msg: dict):
    """Real check — every privileged message must carry a valid
    signature verified against the secret THIS device's desktop
    established, not a bare device_id claim."""
    device_id = msg.get("device_id") or msg.get("target")
    secret_hex = device_secrets.get(device_id)
    if not secret_hex:
        return False, "device not paired with this relay yet"
    secret = bytes.fromhex(secret_hex)
    return verify_request(
        msg.get("cmd", msg.get("type")), msg.get("ts"), device_id,
        msg.get("sig"), msg.get("nonce"), secret,
    )


# ==========================
# REGISTER FCM (now signed)
# ==========================
# ==========================
# HEALTH CHECK (keep-alive target)
# Deliberately unauthenticated and gives away nothing sensitive —
# this is purely a "the server is awake" heartbeat, hit periodically
# by the laptop to stop Render's free tier from spinning down.
# ==========================
@app.get("/health")
async def health():
    return {"status": "alive", "time": int(time.time())}


@app.post("/register_fcm")
async def register_fcm(data: dict):
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


# ==========================
# UPLOAD INTRUDER (now signed — was wide open before)
# ==========================
@app.post("/upload_intruder")
async def upload_intruder(
    file: UploadFile = File(...),
    device_id: str = Form(...),
    activity: str = Form("Activity detected"),
    ts: str = Form(...),
    nonce: str = Form(...),
    sig: str = Form(...),
):
    secret_hex = device_secrets.get(device_id)
    if not secret_hex:
        return {"status": "error", "error": "unpaired device"}

    valid, msg = verify_request("upload_intruder", ts, device_id, sig, nonce, bytes.fromhex(secret_hex))
    if not valid:
        print(f"❌ Upload rejected: {msg}")
        return {"status": "error", "error": msg}

    try:
        now = time.time()
        filename = f"{device_id}_{int(now)}.jpg"
        path = os.path.join(UPLOAD_DIR, filename)
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        image_url = f"https://zephyr-altair-ai-server.onrender.com/intruders/{filename}"
        print("📷 Saved:", image_url)

        entry = {
            "filename": filename, "image_url": image_url, "activity": activity,
            "timestamp": int(now),
            "date": time.strftime("%d/%m/%Y", time.localtime(now)),
            "time": time.strftime("%H:%M", time.localtime(now)),
        }
        add_intruder_log(device_id, entry)

        token = fcm_tokens.get(device_id)
        if token:
            msg = messaging.Message(
                token=token,
                notification=messaging.Notification(title="Zephyr Security", body=f"{activity} — tap to view"),
                data={"type": "intruder", "image_url": image_url, "filename": filename,
                      "time": entry["time"], "date": entry["date"], "activity": activity},
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(channel_id="intruder_alerts", image=image_url),
                ),
            )
            try:
                response = messaging.send(msg)
                print("✅ FCM sent:", response)
            except Exception as e:
                print("❌ FCM send failed:", e)
        else:
            print("❌ No FCM token")

        return {"status": "ok", "url": image_url}
    except Exception as e:
        print("UPLOAD ERROR:", e)
        return {"status": "error"}


# ==========================
# LIST INTRUDER LOGS (now signed — was a bare device_id check before)
# ==========================
@app.get("/intruder_logs")
async def intruder_logs(device_id: str, ts: str, nonce: str, sig: str):
    secret_hex = device_secrets.get(device_id)
    if not secret_hex:
        return {"status": "error", "message": "unpaired device"}

    valid, msg = verify_request("intruder_logs", ts, device_id, sig, nonce, bytes.fromhex(secret_hex))
    if not valid:
        return {"status": "error", "message": msg}

    return {"status": "ok", "entries": get_intruder_logs(device_id)}


# ==========================
# DELETE INTRUDER (real delete, signed)
# ==========================
@app.get("/delete_intruder")
async def delete_intruder(device_id: str, filename: str, ts: str, nonce: str, sig: str):
    secret_hex = device_secrets.get(device_id)
    if not secret_hex:
        return {"status": "error", "message": "unpaired device"}

    valid, msg = verify_request("delete_intruder", ts, device_id, sig, nonce, bytes.fromhex(secret_hex))
    if not valid:
        return {"status": "error", "message": msg}

    safe_name = os.path.basename(filename)
    path = os.path.join(UPLOAD_DIR, safe_name)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError as e:
            print("Delete error:", e)

    remove_intruder_log(device_id, safe_name)
    return {"status": "ok"}


# ==========================
# WEBSOCKET
# ==========================
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
                    valid, err = verify_signed(msg)
                    if not valid:
                        print(f"❌ Mobile registration rejected: {err}")
                        await socket.close()
                        return
                    mobile_clients[device_id] = socket

                print(f"Connected {role}: {device_id}")
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
                # THE critical fix — this handler had ZERO verification
                # in the version you sent. Every command must now carry
                # a valid signature.
                valid, err = verify_signed(msg)
                if not valid:
                    print(f"❌ COMMAND REJECTED: {err}")
                    continue

                action = msg.get("action")
                ALLOWED_ACTIONS = {"lock", "unlock", "start_camera", "stop_camera", "freeze_overlay"}
                if action not in ALLOWED_ACTIONS:
                    print(f"❌ COMMAND REJECTED: unknown action '{action}'")
                    continue

                target = msg.get("target")
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

            elif msg_type == "stop_view_camera":
                target = msg.get("viewer_device")
                viewer_ws = camera_viewers.pop(target, None)
                if viewer_ws:
                    try:
                        await viewer_ws.close()
                    except Exception:
                        pass

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
        print(f"Closed {device_id}")