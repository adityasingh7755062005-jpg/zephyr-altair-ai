# ==============================
# FILE 5: zephyr_cloud_server.py (FULL FIXED)
# ==============================

import json
import os
import time
import shutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
import firebase_admin
from firebase_admin import credentials, messaging

from network.security import verify_request

app = FastAPI()

# 🔥 Firebase Init (ENV FIXED)
if not firebase_admin._apps:
    try:
        firebase_json = os.environ.get("FIREBASE_KEY_JSON")

        if firebase_json:
            cred_dict = json.loads(firebase_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Ready From ENV")
        else:
            print("❌ FIREBASE_KEY_JSON missing")

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
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data,
            token=token
        )

        response = messaging.send(message)

        print("✅ FCM sent")
        print("📨 Response:", response)

    except Exception as e:
        print("❌ FCM error:", e)


# ==============================
# REGISTER FCM
# ==============================
@app.post("/register_fcm")
async def register_fcm(data: dict):

    try:
        device_id = data.get("device_id", "")
        fcm_token = data.get("fcm_token", "")

        if not device_id or not fcm_token:
            return {
                "status": "error",
                "message": "missing fields"
            }

        fcm_tokens[device_id] = fcm_token

        print(f"📱 FCM registered: {device_id}")
        print(f"🔑 TOKEN: {fcm_token[:30]}...")

        return {"status": "ok"}

    except Exception as e:
        print("❌ Register FCM error:", e)

        return {
            "status": "error",
            "message": str(e)
        }


# ==============================
# 🚨 INTRUDER UPLOAD (FULL FIXED)
# ==============================
@app.post("/upload_intruder")
async def upload_intruder(
    file: UploadFile = File(...),
    device_id: str = ""
):

    try:
        # ✅ UNIQUE FILE NAME
        filename = f"{device_id}_{int(time.time())}.jpg"

        path = os.path.join(UPLOAD_DIR, filename)

        # ✅ SAVE FILE
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # ✅ PUBLIC URL
        url = f"https://zephyr-altair-ai-server.onrender.com/intruders/{filename}"

        print("📸 Intruder uploaded:")
        print(f"🌐 URL: {url}")

        # ✅ GET TOKEN
        token = fcm_tokens.get(device_id)

        if token:

            # ✅ SEND FCM
            send_fcm(
                token,
                "🚨 Intruder Alert",
                "Tap to view image",
                {
                    "type": "intruder",
                    "image_url": url,
                    "time": time.strftime("%H:%M:%S"),
                    "date": time.strftime("%Y-%m-%d"),
                    "activity": "Intruder detected"
                }
            )

        else:
            print("❌ No FCM token found")
            print(f"📱 Device ID: {device_id}")

        return {
            "status": "ok",
            "url": url
        }

    except Exception as e:
        print("❌ Upload error:", e)

        return {
            "status": "error",
            "message": str(e)
        }


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

            if msg.get("type") == "register":

                device_id = msg.get("device_id")

                clients[device_id] = ws

                print(f"✅ Device connected: {device_id}")

            elif msg.get("type") == "command":

                target = msg.get("target")
                action = msg.get("action")
                ts = msg.get("ts")
                sig = msg.get("sig")
                nonce = msg.get("nonce")

                print(f"📩 CLOUD CMD → {target} : {action}")

                valid, reason = verify_request(
                    action,
                    ts,
                    target,
                    sig,
                    nonce
                )

                if not valid:
                    print(f"❌ CLOUD REJECTED: {reason}")
                    continue

                if target in clients:

                    await clients[target].send_text(json.dumps({
                        "type": "command",
                        "action": action,
                        "ts": ts,
                        "sig": sig,
                        "nonce": nonce
                    }))

                    print("✅ Command forwarded")

                else:
                    print("❌ Target not connected")

    except WebSocketDisconnect:

        print(f"⚠️ Disconnected: {device_id}")

        if device_id in clients:
            del clients[device_id]