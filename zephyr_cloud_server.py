# ==============================
# FILE: zephyr_cloud_server.py
# FINAL ULTRA STABLE CLOUD SERVER
# FIXED COMMAND ROUTING VERSION
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

TRUSTED_DEVICE_ID = "160c02a2018e7132"

clients = {}
desktop_clients = {}
fcm_tokens = {}
camera_streamers = {}
camera_viewers = {}
last_frame_log = {}
last_ping = {}

UPLOAD_DIR = "intruders"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount(
    "/intruders",
    StaticFiles(directory=UPLOAD_DIR),
    name="intruders"
)

def is_trusted_device(device_id):
    return device_id == TRUSTED_DEVICE_ID


async def safe_send(ws, data):
    try:
        await ws.send_text(data)
        return True
    except:
        return False


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
            # REGISTER
            # ==============================

            if msg_type == "register":

                device_id = msg.get(
                    "device_id",""
                ).strip()

                role = msg.get(
                    "role",
                    "desktop"
                )

                if not is_trusted_device(
                    device_id
                ):
                    await ws.close()
                    return

                if role == "mobile":

                    clients[
                        f"mobile_{device_id}"
                    ] = ws

                    print(
                        f"📱 Mobile Connected "
                        f"{device_id}"
                    )

                else:

                    desktop_clients[
                        f"desktop_{device_id}"
                    ] = ws

                    print(
                        f"💻 Desktop Connected "
                        f"{device_id}"
                    )

                last_ping[
                    device_id
                ] = time.time()

            # ==============================
            # CAMERA AUTH
            # ==============================

            elif msg_type == "camera_auth":

                device_id = msg.get(
                    "device_id",""
                ).strip()

                camera_streamers[
                    device_id
                ] = ws

                await safe_send(
                    ws,
                    json.dumps({
                        "type":"auth_ok"
                    })
                )

            # ==============================
            # VIEW CAMERA
            # ==============================

            elif msg_type == "view_camera":

                viewer_target = msg.get(
                    "target_device"
                )

                camera_viewers\
                    .setdefault(
                        viewer_target,
                        set()
                    ).add(ws)

            # ==============================
            # CAMERA FRAME
            # ==============================

            elif msg_type == "camera_frame":

                source = msg.get(
                    "device_id"
                )

                viewers = (
                    camera_viewers.get(
                        source,
                        set()
                    )
                )

                for v in list(viewers):

                    ok = await safe_send(
                        v,
                        raw
                    )

                    if not ok:
                        viewers.discard(v)

            # ==============================
            # PING
            # ==============================

            elif msg_type == "ping":

                await safe_send(
                    ws,
                    json.dumps({
                        "type":"pong"
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

                ts = msg.get("ts")
                sig = msg.get("sig")
                nonce = msg.get("nonce")

                valid, reason = verify_request(
                    action,
                    ts,
                    target,
                    sig,
                    nonce
                )

                if not valid:

                    print(
                        f"Rejected: "
                        f"{reason}"
                    )

                    continue

                # ==========================
                # SEND TO DESKTOP FIRST
                # ==========================

                target_ws = (
                    desktop_clients.get(
                        f"desktop_{target}"
                    )
                )

                if not target_ws:

                    target_ws = clients.get(
                        f"mobile_{target}"
                    )

                if not target_ws:

                    print(
                        "❌ Device offline"
                    )

                    continue

                ok = await safe_send(

                    target_ws,

                    json.dumps({

                        "type":"command",

                        "action":action,

                        "ts":ts,

                        "sig":sig,

                        "nonce":nonce
                    })
                )

                if ok:

                    print(
                        f"✅ Command "
                        f"{action}"
                    )

    except WebSocketDisconnect:
        pass

    finally:

        clients.pop(
            f"mobile_{device_id}",
            None
        )

        desktop_clients.pop(
            f"desktop_{device_id}",
            None
        )

        camera_streamers.pop(
            device_id,
            None
        )