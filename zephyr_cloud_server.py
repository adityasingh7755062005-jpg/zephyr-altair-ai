# ==============================
# FILE: zephyr_cloud_server.py
# FINAL ULTRA STABLE CLOUD SERVER
# FULLY FIXED RENDER VERSION
# FIXED RECONNECT RACE CONDITION
# FIXED MOBILE DISCONNECT LOOP
# FIXED DEAD SOCKET CLEANUP
# ==============================

import json
import os
import time
import shutil
import asyncio

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
# TRUSTED DEVICE
# ==============================

TRUSTED_DEVICE_ID = "160c02a2018e7132"

# ==============================
# FIREBASE INIT
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

camera_streamers = {}

camera_viewers = {}

last_frame_log = {}

last_ping = {}

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
# TRUST CHECK
# ==============================

def is_trusted_device(device_id):

    return (
        device_id ==
        TRUSTED_DEVICE_ID
    )

# ==============================
# SAFE SEND
# ==============================

async def safe_send(ws, data):

    try:

        await ws.send_text(data)
        return True

    except Exception:

        return False

# ==============================
# CLEAN DEAD VIEWERS
# ==============================

async def cleanup_dead_viewers():

    while True:

        try:

            await asyncio.sleep(20)

            dead_groups = []

            for device_id, viewers in list(
                camera_viewers.items()
            ):

                dead = set()

                for viewer_ws in list(viewers):

                    try:

                        await viewer_ws.send_text(

                            json.dumps({
                                "type": "ping"
                            })
                        )

                    except:

                        dead.add(viewer_ws)

                viewers.difference_update(dead)

                if not viewers:

                    dead_groups.append(
                        device_id
                    )

            for group in dead_groups:

                camera_viewers.pop(
                    group,
                    None
                )

        except Exception as e:

            print(
                f"❌ Viewer cleanup error: {e}"
            )

# ==============================
# CLEAN DEAD DEVICES
# ==============================

async def cleanup_dead_devices():

    while True:

        try:

            await asyncio.sleep(30)

            now = time.time()

            dead = []

            for device_id, ts in list(
                last_ping.items()
            ):

                if now - ts > 180:

                    dead.append(device_id)

            for device_id in dead:

                current_mobile = clients.get(
                    f"mobile_{device_id}"
                )

                if current_mobile:

                    try:
                        await current_mobile.close()
                    except:
                        pass

                    clients.pop(
                        f"mobile_{device_id}",
                        None
                    )

                current_camera = (
                    camera_streamers.get(
                        device_id
                    )
                )

                if current_camera:

                    try:
                        await current_camera.close()
                    except:
                        pass

                    camera_streamers.pop(
                        device_id,
                        None
                    )

                last_ping.pop(
                    device_id,
                    None
                )

                print(
                    f"❌ Dead Device Removed: "
                    f"{device_id}"
                )

        except Exception as e:

            print(
                f"❌ Cleanup error: {e}"
            )

# ==============================
# STARTUP
# ==============================

@app.on_event("startup")
async def startup_tasks():

    asyncio.create_task(
        cleanup_dead_viewers()
    )

    asyncio.create_task(
        cleanup_dead_devices()
    )

    print(
        "✅ Cleanup Tasks Started"
    )

# ==============================
# FCM
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

        messaging.send(message)

        print("✅ FCM sent")

    except Exception as e:

        print(
            "❌ FCM error:",
            e
        )

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

        if not is_trusted_device(
            device_id
        ):

            return {
                "status": "error"
            }

        fcm_tokens[
            device_id
        ] = fcm_token

        print(
            f"📱 FCM Registered: "
            f"{device_id}"
        )

        return {
            "status": "ok"
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }

# ==============================
# INTRUDER UPLOAD
# ==============================

@app.post("/upload_intruder")
async def upload_intruder(

    file: UploadFile = File(...),

    device_id: str = Form(...)

):

    try:

        device_id = device_id.strip()

        if not is_trusted_device(
            device_id
        ):

            return {
                "status": "error"
            }

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

        print(
            "📸 Intruder Uploaded"
        )

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
                    "image_url": url
                }
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
            "status": "error"
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
            # REGISTER MOBILE
            # ==============================

            if msg_type == "register":

                device_id = msg.get(
                    "device_id",
                    ""
                ).strip()

                if not is_trusted_device(
                    device_id
                ):

                    await ws.close()
                    return

                role = "mobile"

                clients[
                    f"mobile_{device_id}"
                ] = ws

                last_ping[
                    device_id
                ] = time.time()

                print(
                    f"\n📱 Mobile Connected: "
                    f"{device_id}"
                )

            # ==============================
            # CAMERA AUTH
            # ==============================

            elif msg_type == "camera_auth":

                device_id = msg.get(
                    "device_id",
                    ""
                ).strip()

                if not is_trusted_device(
                    device_id
                ):

                    await ws.close()
                    return

                role = "camera"

                camera_streamers[
                    device_id
                ] = ws

                last_ping[
                    device_id
                ] = time.time()

                last_frame_log[
                    device_id
                ] = time.time()

                print(
                    f"\n📷 Camera Connected: "
                    f"{device_id}"
                )

                await safe_send(

                    ws,

                    json.dumps({
                        "type": "auth_ok"
                    })
                )

            # ==============================
            # VIEW CAMERA
            # ==============================

            elif msg_type == "view_camera":

                viewer_target = msg.get(
                    "target_device",
                    ""
                ).strip()

                role = "viewer"

                if viewer_target not in (
                    camera_viewers
                ):

                    camera_viewers[
                        viewer_target
                    ] = set()

                camera_viewers[
                    viewer_target
                ].add(ws)

                print(
                    f"\n👁️ Viewer Connected → "
                    f"{viewer_target}"
                )

            # ==============================
            # CAMERA FRAME
            # ==============================

            elif msg_type == "camera_frame":

                source_device = msg.get(
                    "device_id",
                    ""
                ).strip()

                last_ping[
                    source_device
                ] = time.time()

                viewers = camera_viewers.get(
                    source_device,
                    set()
                )

                dead = set()

                for viewer_ws in list(viewers):

                    ok = await safe_send(
                        viewer_ws,
                        raw
                    )

                    if not ok:

                        dead.add(
                            viewer_ws
                        )

                viewers.difference_update(
                    dead
                )

            # ==============================
            # PING
            # ==============================

            elif msg_type == "ping":

                if device_id:

                    last_ping[
                        device_id
                    ] = time.time()

                await safe_send(

                    ws,

                    json.dumps({
                        "type": "pong"
                    })
                )

            # ==============================
            # COMMAND
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

                valid, reason = (
                    verify_request(

                        action,
                        ts,
                        target,
                        sig,
                        nonce
                    )
                )

                if not valid:

                    print(
                        f"❌ Rejected: "
                        f"{reason}"
                    )

                    continue

                mobile_ws = clients.get(
                    f"mobile_{target}"
                )

                if not mobile_ws:

                    print(
                        "❌ Mobile Offline"
                    )

                    continue

                ok = await safe_send(

                    mobile_ws,

                    json.dumps({

                        "type": "command",

                        "action": action,

                        "ts": ts,

                        "sig": sig,

                        "nonce": nonce
                    })
                )

                if ok:

                    print(
                        f"✅ Command Forwarded: "
                        f"{action}"
                    )

    except WebSocketDisconnect:

        print(
            f"\n⚠️ Disconnected: "
            f"{device_id}"
        )

    except Exception as e:

        print(
            f"\n❌ WebSocket Error: {e}"
        )

    finally:

        try:

            mobile_key = (
                f"mobile_{device_id}"
            )

            if (
                clients.get(
                    mobile_key
                ) == ws
            ):

                clients.pop(
                    mobile_key,
                    None
                )

            if (
                camera_streamers.get(
                    device_id
                ) == ws
            ):

                camera_streamers.pop(
                    device_id,
                    None
                )

            if (
                viewer_target
                and
                viewer_target
                in camera_viewers
            ):

                camera_viewers[
                    viewer_target
                ].discard(ws)

                if not camera_viewers[
                    viewer_target
                ]:

                    camera_viewers.pop(
                        viewer_target,
                        None
                    )

        except:
            pass

        print(
            f"\n📊 Mobiles: {len(clients)} | "
            f"Cameras: {len(camera_streamers)} | "
            f"Viewer Groups: {len(camera_viewers)}"
        )