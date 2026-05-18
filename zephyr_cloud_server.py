# ==============================
# FILE: zephyr_cloud_server.py
# FINAL ULTRA STABLE CLOUD SERVER
# FIXED CLOUD COMMAND ROUTING
# MOBILE + LAPTOP + CAMERA RELAY
# ==============================

import json
import os
import socket
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

TRUSTED_DEVICE_ID = "160c02a2018e7132"

# ==============================
# FIREBASE
# ==============================

if not firebase_admin._apps:

    try:

        firebase_json = os.environ.get(
            "FIREBASE_KEY_JSON"
        )

        if firebase_json:

            cred = credentials.Certificate(
                json.loads(firebase_json)
            )

            firebase_admin.initialize_app(
                cred
            )

            print("✅ Firebase Ready")

    except Exception as e:

        print("❌ Firebase:", e)

# ==============================
# MEMORY
# ==============================

mobile_clients = {}
desktop_clients = {}

camera_streamers = {}
camera_viewers = {}

fcm_tokens = {}

last_frame_log = {}

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
# HELPERS
# ==============================

def is_trusted_device(device):

    return (
        device ==
        TRUSTED_DEVICE_ID
    )


async def safe_send(
    ws,
    data
):

    try:

        await ws.send_text(data)

        return True

    except:

        return False


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

        msg = messaging.Message(

            notification=
            messaging.Notification(

                title=title,
                body=body

            ),

            data=data,

            token=token

        )

        response = messaging.send(
            msg
        )

        print(

            "✅ Firebase sent:",

            response

        )

    except Exception as e:

        print(

            "❌ Firebase failed:",

            e

        )


# ==============================
# REGISTER FCM TOKEN
# FIXED MISSING ENDPOINT
# ==============================

@app.post("/register_fcm")
async def register_fcm(
        data: dict
):

    device = data.get(
        "device_id",
        ""
    )

    token = data.get(
        "fcm_token",
        ""
    )

    fcm_tokens[
        device
    ] = token

    print(
        "✅ FCM TOKEN SAVED:",
        device
    )

    return {
        "status": "ok"
    }


# ==============================
# INTRUDER
# ==============================

@app.post("/upload_intruder")
async def upload_intruder(

        file: UploadFile = File(...),

        device_id: str = Form(...)

):

    try:

        print(
            f"🚨 Upload from {device_id}"
        )

        filename = (

            f"{device_id}_"

            f"{int(time.time())}.jpg"

        )

        path = os.path.join(

            UPLOAD_DIR,

            filename

        )

        with open(
                path,
                "wb"
        ) as f:

            shutil.copyfileobj(
                file.file,
                f
            )

        image_url = (

            "https://zephyr-altair-ai-server.onrender.com"

            +

            f"/intruders/{filename}"

        )

        print(
            "📸 Saved:",
            image_url
        )

        token = fcm_tokens.get(
            device_id
        )

        print(
            "📱 Token:",
            token
        )

        if token:

            send_fcm(

                token,

                "🚨 Intruder Alert",

                "Tap to open image",

                {

                    "type":
                        "intruder",

                    "image_url":
                        image_url,

                    "time":
                        time.strftime("%H:%M"),

                    "date":
                        time.strftime("%d/%m/%Y"),

                    "activity":
                        "Movement detected"

                }

            )

            print(
                "✅ FCM sent"
            )

        else:

            print(
                "❌ No FCM token"
            )

        return {

            "status":
                "ok",

            "url":
                image_url
        }

    except Exception as e:

        print(
            "❌ Upload error:",
            e
        )

        return {

            "status":
                "error"
        }

# ==============================
# WEBSOCKET
# ==============================

@app.websocket("/ws")
async def ws(
        socket: WebSocket
):

    await socket.accept()

    device_id = None
    role = None

    try:

        while True:

            raw = await asyncio.wait_for(
                socket.receive_text(),
                timeout=90
            )

            msg = json.loads(raw)

            msg_type = msg.get(
                "type"
            )

            # ==========================
            # REGISTER
            # ==========================

            if msg_type == "register":

                device_id = msg.get(
                    "device_id",
                    ""
                )

                role = msg.get(
                    "role",
                    "mobile"
                )

                if not is_trusted_device(
                        device_id
                ):

                    await socket.close()
                    return

                if role == "mobile":

                    mobile_clients[
                        device_id
                    ] = socket

                else:

                    desktop_clients[
                        device_id
                    ] = socket

                print(
                    f"✅ Cloud connected as {role}: {device_id}"
                )

            # ==========================
            # COMMAND
            # ==========================

            elif msg_type == "command":

                target = msg.get(
                    "target"
                )

                action = msg.get(
                    "action"
                )

                print(
                    f"📨 CLOUD CMD -> {action}"
                )

                print(
                    f"🎯 target={target}"
                )

                print(
                    f"💻 desktops={list(desktop_clients.keys())}"
                )

                target_ws = desktop_clients.get(
                    target
                )

                if target_ws:

                    ok = await safe_send(

                        target_ws,

                        json.dumps({

                            "type":
                                "command",

                            "action":
                                action

                        })

                    )

                    if ok:

                        print(
                            f"✅ Routed: {action}"
                        )

                    else:

                        print(
                            "❌ Send failed"
                        )

                else:

                    print(
                        f"❌ Desktop offline: {target}"
                    )

            # ==========================
            # CAMERA AUTH
            # ==========================

            elif msg_type == "camera_auth":

                device_id = msg.get(
                    "device_id"
                )

                camera_streamers[
                    device_id
                ] = socket

                print(
                    f"📷 Camera registered: {device_id}"
                )


            # ==========================
            # VIEW CAMERA
            # ==========================

            elif msg_type == "view_camera":

                target = msg.get(
                    "target_device"
                )

                viewer = msg.get(
                    "viewer_device"
                )

                camera_viewers[
                    viewer
                ] = socket

                streamer = camera_streamers.get(
                    target
                )

                if streamer:

                    await safe_send(

                        streamer,

                        json.dumps({

                            "type":
                                "viewer_connected",

                            "viewer":
                                viewer

                        })

                    )

                    print(
                        f"👁 Viewer connected -> {target}"
                    )


            # ==========================
            # CAMERA FRAME RELAY
            # ==========================

            elif msg_type == "camera_frame":

                frame = raw

                for viewer_id, viewer_ws in list(
                    camera_viewers.items()
                ):

                    await safe_send(
                        viewer_ws,
                        frame
                    )


            # ==========================
            # PING
            # ==========================

            elif msg_type == "ping":

                await safe_send(

                    socket,

                    json.dumps({

                        "type":
                            "pong"

                    })

                )

    except asyncio.TimeoutError:

        print(
            "⏰ Timeout"
        )

    except WebSocketDisconnect:

        print(
            "⚠ Disconnect"
        )

    except Exception as e:

        print(
            "❌",
            e
        )

    finally:

        if device_id:

            mobile_clients.pop(
                device_id,
                None
            )

            desktop_clients.pop(
                device_id,
                None
            )

        print(
            "🔌 Closed:",
            device_id
        )