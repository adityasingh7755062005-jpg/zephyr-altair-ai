import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
import time
import hashlib
import shutil
import asyncio

# 🔥 Firebase
import firebase_admin
from firebase_admin import credentials, messaging

app = FastAPI()

# ✅ FIX: LOAD FIREBASE FROM ENV (RENDER SAFE)
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_KEY")

    if not firebase_json:
        raise Exception("❌ FIREBASE_KEY not set in environment")

    cred_dict = json.loads(firebase_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

    print("✅ Firebase initialized (Render safe)")

clients = {}

# 🔥 STORE FCM TOKENS
fcm_tokens = {}

DEVICE_SECRETS = {
    "160c02a2018e7132": "c63bd8f574f9634e3f50bda3fd5cce15"
}

UPLOAD_DIR = "intruders"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/intruders", StaticFiles(directory=UPLOAD_DIR), name="intruders")

intruder_logs = []

BASE_URL = "https://zephyr-altair-ai-server.onrender.com"


def generate_token(device_id, secret_key, action, timestamp):
    raw = f"{device_id}{secret_key}{timestamp}{action}"
    return hashlib.sha256(raw.encode()).hexdigest()


# 🔥 SEND FCM
def send_fcm_notification(token, title, body, data=None):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data or {},
            token=token
        )

        response = messaging.send(message)
        print("✅ FCM sent:", response)

    except Exception as e:
        print("❌ FCM error:", e)


# 🔥 SAVE TOKEN FROM APP
@app.post("/register_fcm")
async def register_fcm(data: dict):
    device_id = data.get("device_id")
    token = data.get("fcm_token")

    if not device_id or not token:
        return {"error": "Missing data"}

    fcm_tokens[device_id] = token
    print(f"✅ FCM saved for {device_id}")

    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    device_id = None

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data.get("type") == "register":
                device_id = data.get("device_id")
                clients[device_id] = websocket
                print(f"[Cloud] ✅ {device_id} connected")

            elif data.get("type") == "command":
                target = data.get("target")
                action = data.get("action")

                if target in clients:
                    await clients[target].send_text(json.dumps({
                        "type": "command",
                        "action": action
                    }))
                else:
                    print(f"[Cloud] ❌ Target not found")

    except WebSocketDisconnect:
        print(f"[Cloud] ⚠️ {device_id} disconnected")

    finally:
        if device_id in clients:
            del clients[device_id]


@app.get("/")
def home():
    return {"status": "Zephyr Cloud Running 🚀"}


@app.post("/upload_intruder")
async def upload_intruder(
    file: UploadFile = File(...),
    device_id: str = "",
    activity: str = "Intruder detected"
):
    try:
        timestamp = int(time.time())
        filename = f"{device_id}_{timestamp}.jpg"
        file_path = os.path.join(UPLOAD_DIR, filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        image_url = f"{BASE_URL}/intruders/{filename}"

        print(f"[Cloud] 📸 Saved: {filename}")

        intruder_logs.append({
            "device_id": device_id,
            "image_url": image_url,
            "activity": activity,
            "timestamp": timestamp,
            "time": time.strftime("%H:%M:%S"),
            "date": time.strftime("%Y-%m-%d")
        })

        # 🔥 SEND FCM USING STORED TOKEN
        token = fcm_tokens.get(device_id)
        if token:
            send_fcm_notification(
                token,
                "🚨 Intruder Detected!",
                activity,
                {
                    "type": "intruder",
                    "image_url": image_url,
                    "time": time.strftime("%H:%M:%S"),
                    "date": time.strftime("%Y-%m-%d"),
                    "activity": activity
                }
            )

        return {"status": "uploaded", "image_url": image_url}

    except Exception as e:
        print("❌ Upload error:", e)
        return {"error": str(e)}


@app.get("/get_intruder_logs")
def get_intruder_logs():
    return intruder_logs