# ==============================
# FILE: zephyr_cloud_server.py
# FULL FIXED VERSION
# STABLE CLOUD + CAMERA STREAM
# ==============================

import json
import os
import time
import shutil

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form

from fastapi.staticfiles import StaticFiles

import firebase_admin
from firebase_admin import credentials, messaging

app = FastAPI()

TRUSTED_DEVICE_ID = "160c02a2018e7132"

# ==========================
# FIREBASE
# ==========================

if not firebase_admin._apps:

    try:

        firebase_json = os.environ.get("FIREBASE_KEY_JSON")

        if firebase_json:

            cred = credentials.Certificate(json.loads(firebase_json))

            firebase_admin.initialize_app(cred)

            print("✅ Firebase Ready")

    except Exception as e:

        print("Firebase:", e)


# ==========================
# MEMORY
# ==========================

mobile_clients = {}
desktop_clients = {}

camera_streamers = {}
camera_viewers = {}

fcm_tokens = {}

UPLOAD_DIR = "intruders"

os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/intruders", StaticFiles(directory=UPLOAD_DIR), name="intruders")


# ==========================
# HELPERS
# ==========================


def trusted(device):

    return device == TRUSTED_DEVICE_ID


async def safe_send(ws, data):

    try:

        await ws.send_text(data)

        return True

    except:

        return False


# ==========================
# REGISTER FCM
# ==========================


@app.post("/register_fcm")
async def register_fcm(data: dict):

    device = data.get("device_id", "")

    token = data.get("fcm_token", "")

    fcm_tokens[device] = token

    print("FCM saved:", device)

    return {"status": "ok"}


# ==========================
# UPLOAD INTRUDER
# SEND FCM AFTER UPLOAD
# ==========================


@app.post("/upload_intruder")
async def upload_intruder(file: UploadFile = File(...), device_id: str = Form(...)):

    try:

        filename = f"{device_id}_" f"{int(time.time())}.jpg"

        path = os.path.join(UPLOAD_DIR, filename)

        with open(path, "wb") as f:

            shutil.copyfileobj(file.file, f)

        image_url = (
            "https://zephyr-altair-ai-server.onrender.com" + f"/intruders/{filename}"
        )

        print("📷 Saved:", image_url)

        token = fcm_tokens.get(device_id)

        print("TOKEN:", token)

        # ======================
        # SEND FIREBASE
        # ======================

        if token:

            msg = messaging.Message(
                token=token,
                data={
                    "type": "intruder",
                    "image_url": image_url,
                    "time": time.strftime("%H:%M"),
                    "date": time.strftime("%d/%m/%Y"),
                    "activity": "Movement detected",
                },
            )

            response = messaging.send(msg)

            print("✅ FCM sent:", response)

        else:

            print("❌ No FCM token")

        return {"status": "ok", "url": image_url}

    except Exception as e:

        print("UPLOAD ERROR:", e)

        return {"status": "error"}


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

            # ======================
            # REGISTER
            # ======================

            if msg_type == "register":

                device_id = msg.get("device_id")

                role = msg.get("role", "mobile")

                if not trusted(device_id):

                    await socket.close()

                    return

                if role == "mobile":

                    mobile_clients[device_id] = socket

                else:

                    desktop_clients[device_id] = socket

                print(f"Connected {role}")

                await safe_send(socket, json.dumps({"type": "auth_ok"}))

            # ======================
            # CAMERA AUTH
            # ======================

            elif msg_type == "camera_auth":

                device_id = msg.get("device_id")

                old_socket = camera_streamers.pop(device_id, None)
                if old_socket:

                    try:

                        await old_socket.close()
                    except:
                        pass

                camera_streamers[device_id] = socket

                print(f"Camera registered")

                await safe_send(socket, json.dumps({"type": "auth_ok"}))

            # ======================
            # VIEW CAMERA
            # ======================

            elif msg_type == "view_camera":

                target = msg.get("target_device")

                viewer = msg.get("viewer_device")

                old_viewer_socket = camera_viewers.pop(viewer, None)

                if old_viewer_socket:

                    try:

                        await old_viewer_socket.close()

                    except:

                        pass

                camera_viewers[viewer] = socket

                streamer = camera_streamers.get(target)

                if streamer:

                    await safe_send(streamer, json.dumps({"type": "viewer_connected"}))

                    print("Viewer connected")

            # ======================
            # CAMERA FRAME RELAY
            # ======================

            elif msg_type == "camera_frame":

                dead = []

                for viewer_id, viewer_ws in list(camera_viewers.items()):

                    ok = await safe_send(viewer_ws, raw)

                    if not ok:

                        dead.append(viewer_id)

                for x in dead:

                    camera_viewers.pop(x, None)
                # ======================
                # COMMAND
                # ======================

            elif msg_type == "command":

                target = msg.get("target")
                action = msg.get("action")

                desktop = desktop_clients.get(target)

                if desktop:

                    await safe_send(
                        desktop, json.dumps({"type": "command", "action": action})
                    )

                # ======================
                # START CAMERA
                # ======================

            elif msg_type == "start_camera":

                target = msg.get("target_device")

                streamer = camera_streamers.get(target)

                if streamer:

                    await safe_send(streamer, json.dumps({"type": "start_camera"}))

                    print("START CAMERA FORWARDED")

                # ======================
                # STOP CAMERA
                # ======================

            elif msg_type == "stop_camera":

                target = msg.get("target_device")

                streamer = camera_streamers.get(target)

                if streamer:

                    await safe_send(streamer, json.dumps({"type": "stop_camera"}))

                    print("STOP CAMERA FORWARDED")

            # ======================
            # PING
            # ======================

            elif msg_type == "ping":

                await safe_send(socket, json.dumps({"type": "pong"}))

    except WebSocketDisconnect:

        print("Disconnected")

    except Exception as e:

        print(e)

    finally:

        if device_id:

            mobile_clients.pop(device_id, None)

            desktop_clients.pop(device_id, None)

            if camera_streamers.get(device_id) is socket:

                camera_streamers.pop(device_id, None)

            camera_viewers.pop(device_id, None)

        print(f"Closed {device_id}")
