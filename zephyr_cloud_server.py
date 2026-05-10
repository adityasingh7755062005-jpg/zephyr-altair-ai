# ==============================
# FILE 5: zephyr_cloud_server.py
# FULL CLOUD CAMERA VERSION
# ==============================

import json
import os
import time
import shutil

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    Form
)

from fastapi.staticfiles import StaticFiles

import firebase_admin
from firebase_admin import credentials, messaging

from network.security import verify_request

app = FastAPI()

# ==============================
# 🔥 FIREBASE INIT
# ==============================
if not firebase_admin._apps:

    try:

        firebase_json = os.environ.get(
            "FIREBASE_KEY_JSON"
        )

        if firebase_json:

            cred_dict = json.loads(
                firebase_json
            )

            cred = credentials.Certificate(
                cred_dict
            )

            firebase_admin.initialize_app(
                cred
            )

            print(
                "✅ Firebase Ready From ENV"
            )

        else:

            print(
                "❌ FIREBASE_KEY_JSON missing"
            )

    except Exception as e:

        print(
            "❌ Firebase error:",
            e
        )

# ==============================
# MEMORY
# ==============================

clients = {}

fcm_tokens = {}

# ✅ CAMERA STREAMERS
camera_streamers = {}

# ✅ CAMERA VIEWERS
camera_viewers = {}

# ==============================
# STORAGE
# ==============================

UPLOAD_DIR = "intruders"

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)

app.mount(

    "/intruders",

    StaticFiles(
        directory=UPLOAD_DIR
    ),

    name="intruders"
)

# ==============================
# FCM SEND
# ==============================

def send_fcm(
    token,
    title,
    body,
    data
):

    try:

        message = messaging.Message(

            notification=
            messaging.Notification(

                title=title,
                body=body
            ),

            data=data,

            token=token
        )

        response = messaging.send(
            message
        )

        print("✅ FCM sent")
        print("📨 Response:", response)

    except Exception as e:

        print("❌ FCM error:", e)

# ==============================
# REGISTER FCM
# ==============================

@app.post("/register_fcm")
async def register_fcm(
    data: dict
):

    try:

        device_id = data.get(
            "device_id",
            ""
        ).strip()

        fcm_token = data.get(
            "fcm_token",
            ""
        ).strip()

        if not device_id:

            return {
                "status": "error",
                "message": "device_id missing"
            }

        if not fcm_token:

            return {
                "status": "error",
                "message": "fcm_token missing"
            }

        fcm_tokens[
            device_id
        ] = fcm_token

        print(
            f"📱 FCM registered: "
            f"{device_id}"
        )

        print(
            f"🔑 TOKEN: "
            f"{fcm_token[:35]}..."
        )

        return {
            "status": "ok"
        }

    except Exception as e:

        print(
            "❌ Register FCM error:",
            e
        )

        return {
            "status": "error",
            "message": str(e)
        }

# ==============================
# 🚨 INTRUDER UPLOAD
# ==============================

@app.post("/upload_intruder")
async def upload_intruder(

    file: UploadFile = File(...),

    device_id: str = Form(...)

):

    try:

        device_id = device_id.strip()

        print(
            "📥 Upload request received"
        )

        print(
            f"📱 Device ID: "
            f"{device_id}"
        )

        filename = (
            f"{device_id}_"
            f"{int(time.time())}.jpg"
        )

        path = os.path.join(
            UPLOAD_DIR,
            filename
        )

        with open(path, "wb") as f:

            shutil.copyfileobj(
                file.file,
                f
            )

        url = (

            "https://zephyr-altair-ai-server.onrender.com"

            f"/intruders/{filename}"
        )

        print("📸 Intruder uploaded")
        print(f"🌐 URL: {url}")

        token = fcm_tokens.get(
            device_id
        )

        if token:

            send_fcm(

                token,

                "🚨 Intruder Alert",

                "Tap to view image",

                {

                    "type": "intruder",

                    "image_url": url,

                    "time": time.strftime(
                        "%H:%M:%S"
                    ),

                    "date": time.strftime(
                        "%Y-%m-%d"
                    ),

                    "activity":
                    "Intruder detected"
                }
            )

        else:

            print(
                "❌ No FCM token found"
            )

        return {

            "status": "ok",

            "url": url
        }

    except Exception as e:

        print(
            "❌ Upload error:",
            e
        )

        return {

            "status": "error",

            "message": str(e)
        }

# ==============================
# WEBSOCKET
# ==============================

@app.websocket("/ws")
async def ws(ws: WebSocket):

    await ws.accept()

    device_id = None

    viewer_target = None

    role = None

    try:

        while True:

            raw = await ws.receive_text()

            msg = json.loads(raw)

            msg_type = msg.get("type")

            # ==============================
            # NORMAL DEVICE REGISTER
            # ==============================

            if msg_type == "register":

                device_id = msg.get(
                    "device_id"
                )

                clients[device_id] = ws

                role = "device"

                print(
                    f"✅ Device connected: "
                    f"{device_id}"
                )

            # ==============================
            # CAMERA AUTH
            # ==============================

            elif msg_type == "camera_auth":

                device_id = msg.get(
                    "device_id"
                )

                role = "camera"

                camera_streamers[
                    device_id
                ] = ws

                print("")
                print(
                    "📷 Camera Stream Connected"
                )

                print(
                    f"📱 Device: {device_id}"
                )

            # ==============================
            # VIEW CAMERA
            # ==============================

            elif msg_type == "view_camera":

                viewer_target = msg.get(
                    "target_device"
                )

                role = "viewer"

                if viewer_target not in camera_viewers:

                    camera_viewers[
                        viewer_target
                    ] = set()

                camera_viewers[
                    viewer_target
                ].add(ws)

                print("")
                print(
                    "👁️ Camera Viewer Connected"
                )

                print(
                    f"🎯 Target: "
                    f"{viewer_target}"
                )

            # ==============================
            # CAMERA FRAME RELAY
            # ==============================

            elif msg_type == "camera_frame":

                source_device = msg.get(
                    "device_id"
                )

                viewers = camera_viewers.get(
                    source_device,
                    set()
                )

                dead_viewers = set()

                for viewer_ws in viewers:

                    try:

                        await viewer_ws.send_text(
                            raw
                        )

                    except Exception:

                        dead_viewers.add(
                            viewer_ws
                        )

                viewers.difference_update(
                    dead_viewers
                )

            # ==============================
            # COMMAND SYSTEM
            # ==============================

            elif msg_type == "command":

                target = msg.get(
                    "target"
                )

                action = msg.get(
                    "action"
                )

                ts = msg.get(
                    "ts"
                )

                sig = msg.get(
                    "sig"
                )

                nonce = msg.get(
                    "nonce"
                )

                print(
                    f"📩 CLOUD CMD → "
                    f"{target} : {action}"
                )

                valid, reason = verify_request(

                    action,

                    ts,

                    target,

                    sig,

                    nonce
                )

                if not valid:

                    print(
                        f"❌ CLOUD REJECTED: "
                        f"{reason}"
                    )

                    continue

                if target in clients:

                    await clients[target].send_text(

                        json.dumps({

                            "type": "command",

                            "action": action,

                            "ts": ts,

                            "sig": sig,

                            "nonce": nonce
                        })
                    )

                    print(
                        "✅ Command forwarded"
                    )

                else:

                    print(
                        "❌ Target not connected"
                    )

    except WebSocketDisconnect:

        print("")
        print(
            f"⚠️ Disconnected: "
            f"{device_id}"
        )

    finally:

        # ==============================
        # REMOVE NORMAL CLIENT
        # ==============================

        if device_id in clients:

            del clients[device_id]

        # ==============================
        # REMOVE CAMERA
        # ==============================

        if device_id in camera_streamers:

            del camera_streamers[
                device_id
            ]

            print(
                "📷 Camera Stream Removed"
            )

        # ==============================
        # REMOVE VIEWER
        # ==============================

        if viewer_target in camera_viewers:

            camera_viewers[
                viewer_target
            ].discard(ws)

            print(
                "👁️ Viewer Removed"
            )