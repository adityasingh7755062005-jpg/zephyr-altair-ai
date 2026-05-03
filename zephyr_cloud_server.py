# ==============================
# FILE 5: zephyr_cloud_server.py (CLEAN - NO TOKEN)
# ==============================

import json
import os
import time
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

UPLOAD_DIR = "intruders"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/intruders", StaticFiles(directory=UPLOAD_DIR), name="intruders")


# ==============================
# FCM SEND
# ==============================
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


# ==============================
# REGISTER FCM
# ==============================
@app.post("/register_fcm")
async def register_fcm(data: dict):
    fcm_tokens[data["device_id"]] = data["fcm_token"]
    print(f"📱 FCM registered: {data['device_id']}")
    return {"status": "ok"}


# ==============================
# WEBSOCKET
# ==============================
@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    device_id = None

    try:
        while True:
            msg = json.loads(await ws.receive_text())

            # 📲 REGISTER DEVICE
            if msg.get("type") == "register":
                device_id = msg.get("device_id")
                clients[device_id] = ws
                print(f"✅ Device connected: {device_id}")

            # ⚡ COMMAND ROUTING
            elif msg.get("type") == "command":
                target = msg.get("target")
                action = msg.get("action")

                print(f"📩 CLOUD CMD → {target} : {action}")

                if target in clients:
                    await clients[target].send_text(json.dumps({
                        "type": "command",
                        "action": action
                    }))
                    print("✅ Command forwarded")
                else:
                    print("❌ Target not connected")

    except WebSocketDisconnect:
        print(f"⚠️ Disconnected: {device_id}")
        if device_id in clients:
            del clients[device_id]


# ==============================
# INTRUDER UPLOAD
# ==============================
@app.post("/upload_intruder")
async def upload(file: UploadFile = File(...), device_id: str = ""):

    filename = f"{device_id}_{int(time.time())}.jpg"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    url = f"https://zephyr-altair-ai-server.onrender.com/intruders/{filename}"

    print(f"📸 Intruder uploaded: {device_id}")

    token = fcm_tokens.get(device_id)

    if token:
        send_fcm(token, "🚨 Intruder", "Detected", {
            "type": "intruder",
            "image_url": url
        })

    return {"status": "ok"}