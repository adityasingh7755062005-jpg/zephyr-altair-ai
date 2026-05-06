# ==============================
# FILE 5: zephyr_cloud_server.py (SECURED)
# ==============================

import json
import os
import time
import shutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
import firebase_admin
from firebase_admin import credentials, messaging

# ✅ IMPORT SECURITY
from network.security import verify_request

app = FastAPI()

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
        print("✅ Firebase Ready")
    except Exception as e:
        print("❌ Firebase error:", e)

clients = {}
fcm_tokens = {}

UPLOAD_DIR = "intruders"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/intruders", StaticFiles(directory=UPLOAD_DIR), name="intruders")


def send_fcm(token, title, body, data):
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data,
            token=token
        )
        messaging.send(message)
        print("✅ FCM sent")
    except Exception as e:
        print("❌ FCM error:", e)


@app.post("/register_fcm")
async def register_fcm(data: dict):
    fcm_tokens[data["device_id"]] = data["fcm_token"]
    print(f"📱 FCM registered: {data['device_id']}")
    return {"status": "ok"}


@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    device_id = None

    try:
        while True:
            msg = json.loads(await ws.receive_text())

            if msg.get("type") == "register":
                device_id = msg.get("device_id")
                clients[device_id] = ws
                print(f"✅ Device connected: {device_id}")

            elif msg.get("type") == "command":
                target = msg.get("target")
                action = msg.get("action")
                ts = msg.get("ts")
                sig = msg.get("sig")

                print(f"📩 CLOUD CMD → {target} : {action}")

                valid, reason = verify_request(action, ts, target, sig)

                if not valid:
                    print(f"❌ CLOUD REJECTED: {reason}")
                    continue

                if target in clients:
                    await clients[target].send_text(json.dumps({
                        "type": "command",
                        "action": action,
                        "ts": ts,
                        "sig": sig
                    }))
                    print("✅ Command forwarded")
                else:
                    print("❌ Target not connected")

    except WebSocketDisconnect:
        print(f"⚠️ Disconnected: {device_id}")
        if device_id in clients:
            del clients[device_id]