# ==============================
# FILE: zephyr_cloud_server.py
# FINAL ULTRA STABLE CLOUD SERVER
# LOCAL + CLOUD CAMERA RELAY
# FIXED NETWORK SWITCHING VERSION
# FIXED DEAD SOCKET VERSION
# FIXED CLOUD COMMAND RELAY VERSION
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

viewer_locks = {}

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

    except:

        try:
            await ws.close()
        except:
            pass

        return False

# ==============================
# CLEAN DEAD VIEWERS
# ==============================

async def cleanup_dead_viewers():

    while True:

        try:

            await asyncio.sleep(15)

            dead_groups = []

            for device_id, viewers in list(camera_viewers.items()):

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

                    dead_groups.append(device_id)

            for group in dead_groups:

                if group in camera_viewers:
                    del camera_viewers[group]

        except Exception as e:

            print(
                f"❌ Viewer cleanup error: {e}"
            )

# ==============================
# CLEAN DEAD CAMERAS
# ==============================

async def cleanup_dead_cameras():

    while True:

        try:

            await asyncio.sleep(20)

            now = time.time()

            dead = []

            for device_id, ts in list(last_ping.items()):

                if now - ts > 90:

                    dead.append(device_id)

            for device_id in dead:

                if device_id in camera_streamers:

                    try:
                        await camera_streamers[
                            device_id
                        ].close()
                    except:
                        pass

                    del camera_streamers[
                        device_id
                    ]

                    print(
                        f"❌ Dead Camera Removed: "
                        f"{device_id}"
                    )

                if device_id in last_ping:
                    del last_ping[device_id]

        except Exception as e:

            print(
                f"❌ Camera cleanup error: {e}"
            )

# ==============================
# START BACKGROUND TASKS
# ==============================

@app.on_event("startup")
async def startup_tasks():

    asyncio.create_task(
        cleanup_dead_viewers()
    )

    asyncio.create_task(
        cleanup_dead_cameras()
    )

    print(
        "✅ Cleanup Tasks Started"
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

        messaging.send(
            message
        )

        print("✅ FCM sent")

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

        print("📸 Intruder Uploaded")

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

            raw = await asyncio.wait_for(

                ws.receive_text(),

                timeout=120
            )

            msg = json.loads(raw)

            msg_type = msg.get("type")

            # ==============================
            # MOBILE REGISTER
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

                old_ws = clients.get(
                    f"mobile_{device_id}"
                )

                if old_ws:

                    try:
                        await old_ws.close()
                    except:
                        pass

                clients[
                    f"mobile_{device_id}"
                ] = ws

                last_ping[
                    f"mobile_{device_id}"
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

                old_camera = camera_streamers.get(
                    device_id
                )

                if old_camera:

                    try:
                        await old_camera.close()
                    except:
                        pass

                camera_streamers[
                    device_id
                ] = ws

                last_frame_log[
                    device_id
                ] = time.time()

                last_ping[
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

                if not is_trusted_device(
                    viewer_target
                ):

                    await ws.close()
                    return

                role = "viewer"

                if viewer_target not in camera_viewers:

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

                cam_ws = camera_streamers.get(
                    viewer_target
                )

                if cam_ws:

                    await safe_send(

                        cam_ws,

                        json.dumps({
                            "type": "viewer_connected"
                        })
                    )

            # ==============================
            # CAMERA FRAME
            # ==============================

            elif msg_type == "camera_frame":

                source_device = msg.get(
                    "device_id",
                    ""
                ).strip()

                if not is_trusted_device(
                    source_device
                ):

                    continue

                last_ping[
                    source_device
                ] = time.time()

                viewers = camera_viewers.get(
                    source_device,
                    set()
                )

                if not viewers:
                    continue

                now = time.time()

                if (

                    now -

                    last_frame_log.get(
                        source_device,
                        0
                    )

                    > 15
                ):

                    print(

                        f"\n☁️ Streaming Active | "
                        f"Viewers: {len(viewers)}"
                    )

                    last_frame_log[
                        source_device
                    ] = now

                dead = set()

                for viewer_ws in list(viewers):

                    ok = await safe_send(
                        viewer_ws,
                        raw
                    )

                    if not ok:
                        dead.add(viewer_ws)

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

                if not is_trusted_device(
                    target
                ):

                    continue

                valid, reason = verify_request(

                    action,
                    ts,
                    target,
                    sig,
                    nonce
                )

                if not valid:

                    print(
                        f"❌ Rejected: {reason}"
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

                else:

                    print(
                        "❌ Command Send Failed"
                    )

        # END LOOP

    except asyncio.TimeoutError:

        print(
            "\n⏰ Connection Timeout"
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

        # ==============================
        # MOBILE CLEANUP
        # ==============================

        if device_id:

            mobile_key = (
                f"mobile_{device_id}"
            )

            current_mobile = clients.get(
                mobile_key
            )

            if current_mobile == ws:

                clients.pop(
                    mobile_key,
                    None
                )

        # ==============================
        # CAMERA CLEANUP
        # ==============================

        if device_id:

            current_camera = camera_streamers.get(
                device_id
            )

            if current_camera == ws:

                camera_streamers.pop(
                    device_id,
                    None
                )

                print(
                    f"\n📷 Camera Removed: "
                    f"{device_id}"
                )

        # ==============================
        # VIEWER CLEANUP
        # ==============================

        if (
            viewer_target
            and
            viewer_target in camera_viewers
        ):

            camera_viewers[
                viewer_target
            ].discard(ws)

            if not camera_viewers[
                viewer_target
            ]:

                del camera_viewers[
                    viewer_target
                ]

            print(
                "\n👁️ Viewer Removed"
            )

        try:
            await ws.close()
        except:
            pass

        print(
            f"\n📊 Mobiles: {len(clients)} | "
            f"Cameras: {len(camera_streamers)} | "
            f"Viewer Groups: {len(camera_viewers)}"
        )