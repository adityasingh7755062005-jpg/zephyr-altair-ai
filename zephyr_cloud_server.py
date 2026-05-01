# ==============================
# FILE 5: zephyr_cloud_server.py
# ==============================

import json
import os
import time
import hashlib
import shutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
import firebase_admin
from firebase_admin import credentials, messaging

app = FastAPI()

# 🔥 Firebase Init
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
        print("✅ Firebase Ready")
    except Exception as e:
        print("❌ Firebase error:", e)

clients = {}
fcm_tokens = {}

DEVICE_SECRETS = {
    "160c02a2018e7132": "c63bd8f574f9634e3f50bda3fd5cce15"
}

UPLOAD_DIR = "intruders"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/intruders", StaticFiles(directory=UPLOAD_DIR), name="intruders")


def generate_token(device_id, secret_key, action, timestamp):
    raw = f"{device_id}{secret_key}{timestamp}{action}"
    return hashlib.sha256(raw.encode()).hexdigest()


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
    return {"status": "ok"}


@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    device_id = None

    try:
        while True:
            msg = json.loads(await ws.receive_text())

            if msg["type"] == "register":
                device_id = msg["device_id"]
                clients[device_id] = ws

    except WebSocketDisconnect:
        if device_id in clients:
            del clients[device_id]


@app.post("/upload_intruder")
async def upload(file: UploadFile = File(...), device_id: str = ""):

    filename = f"{device_id}_{int(time.time())}.jpg"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    url = f"https://zephyr-altair-ai-server.onrender.com/intruders/{filename}"

    token = fcm_tokens.get(device_id)

    if token:
        send_fcm(token, "🚨 Intruder", "Detected", {
            "type": "intruder",
            "image_url": url
        })

    return {"status": "ok"}