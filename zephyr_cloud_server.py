# ==============================
# FILE: zephyr_cloud_server.py
# FINAL MERGED STABLE VERSION
# DESKTOP + MOBILE + FCM + CLEANUP
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
camera_streamers = {}
camera_viewers = {}
fcm_tokens = {}
last_ping = {}

UPLOAD_DIR = "intruders"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount(
    "/intruders",
    StaticFiles(directory=UPLOAD_DIR),
    name="intruders"
)

# ==========================
# FIREBASE
# ==========================

if not firebase_admin._apps:

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


def is_trusted_device(device):

    return (
        device ==
        TRUSTED_DEVICE_ID
    )


async def safe_send(ws,data):

    try:

        await ws.send_text(data)

        return True

    except:

        return False


# ==========================
# CLEANUP
# ==========================

async def cleanup():

    while True:

        await asyncio.sleep(30)

        now=time.time()

        dead=[]

        for d,t in list(
            last_ping.items()
        ):

            if now-t > 180:

                dead.append(d)

        for d in dead:

            clients.pop(
                f"mobile_{d}",
                None
            )

            desktop_clients.pop(
                f"desktop_{d}",
                None
            )

            camera_streamers.pop(
                d,
                None
            )

            last_ping.pop(
                d,
                None
            )

            print(
                f"❌ Removed {d}"
            )


@app.on_event("startup")
async def startup():

    asyncio.create_task(
        cleanup()
    )


# ==========================
# FCM REGISTER
# ==========================

@app.post("/register_fcm")
async def register_fcm(
    data:dict
):

    device=data["device_id"]

    token=data["fcm_token"]

    fcm_tokens[
        device
    ]=token

    return {
        "status":"ok"
    }


# ==========================
# INTRUDER
# ==========================

@app.post("/upload_intruder")
async def upload_intruder(

    file:UploadFile=File(...),

    device_id:str=Form(...)
):

    filename=(

        f"{device_id}_"

        f"{int(time.time())}.jpg"

    )

    path=os.path.join(
        UPLOAD_DIR,
        filename
    )

    with open(path,"wb") as f:

        shutil.copyfileobj(
            file.file,
            f
        )

    url=(

        "https://zephyr-altair-ai-server.onrender.com"

        f"/intruders/{filename}"

    )

    token=fcm_tokens.get(
        device_id
    )

    if token:

        try:

            msg=messaging.Message(

                token=token,

                notification=
                messaging.Notification(

                    title="🚨 Intruder",

                    body="Tap to open"
                ),

                data={
                    "image_url":url
                }
            )

            messaging.send(msg)

        except:
            pass

    return {
        "url":url
    }


# ==========================
# WEBSOCKET
# ==========================

@app.websocket("/ws")
async def ws(ws:WebSocket):

    await ws.accept()

    device_id=None

    try:

        while True:

            raw=await ws.receive_text()

            msg=json.loads(raw)

            t=msg.get("type")

            if t=="register":

                device_id=msg["device_id"]

                role=msg.get(
                    "role",
                    "desktop"
                )

                if role=="mobile":

                    clients[
                        f"mobile_{device_id}"
                    ]=ws

                    print(
                        f"📱 {device_id}"
                    )

                else:

                    desktop_clients[
                        f"desktop_{device_id}"
                    ]=ws

                    print(
                        f"💻 {device_id}"
                    )

                last_ping[
                    device_id
                ]=time.time()


            elif t=="ping":

                last_ping[
                    device_id
                ]=time.time()

                await safe_send(

                    ws,

                    json.dumps({

                        "type":"pong"
                    })
                )


            elif t=="command":

                target=msg["target"]

                valid,reason=verify_request(

                    msg["action"],

                    msg["ts"],

                    target,

                    msg["sig"],

                    msg["nonce"]
                )

                if not valid:

                    continue


                target_ws=(

                    desktop_clients.get(
                        f"desktop_{target}"
                    )

                    or

                    clients.get(
                        f"mobile_{target}"
                    )
                )

                if not target_ws:

                    print(
                        "❌ offline"
                    )

                    continue


                ok=await safe_send(

                    target_ws,

                    raw
                )

                if ok:

                    print(
                        "✅ forwarded"
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