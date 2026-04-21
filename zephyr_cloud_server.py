import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
import time
import hashlib
import os
import shutil
import asyncio

app = FastAPI()

clients = {}

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
                token = data.get("token")
                timestamp = data.get("timestamp")

                if target in clients:
                    for i in range(3):
                        try:
                            await clients[target].send_text(json.dumps({
                                "type": "command",
                                "action": action,
                                "token": token,
                                "timestamp": timestamp
                            }))
                            print(f"[Cloud] 📤 {action} → {target} (try {i+1})")
                            break
                        except Exception as e:
                            print(f"[Cloud] retry {i+1} failed:", e)
                            await asyncio.sleep(1)
                else:
                    print(f"[Cloud] ❌ Target {target} not found")

    except WebSocketDisconnect:
        print(f"[Cloud] ⚠️ {device_id} disconnected")

    finally:
        if device_id in clients:
            del clients[device_id]


@app.get("/")
def home():
    return {"status": "Zephyr Cloud Running 🚀"}


@app.get("/send/{target}/{action}")
async def send_command(target: str, action: str):
    if target in clients:

        secret = DEVICE_SECRETS.get(target)

        if not secret:
            return {"error": "Unknown device"}

        timestamp = int(time.time())
        token = generate_token(target, secret, action, timestamp)

        for i in range(3):
            try:
                await clients[target].send_text(json.dumps({
                    "type": "command",
                    "action": action,
                    "token": token,
                    "timestamp": timestamp
                }))
                print(f"[Cloud] 🚀 {action} → {target} (try {i+1})")
                break
            except Exception as e:
                print(f"[Cloud] retry {i+1} failed:", e)
                await asyncio.sleep(1)

        return {"status": f"{action} sent to {target}"}

    else:
        return {"error": "Device not connected"}


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

        for _, ws in clients.items():
            try:
                await ws.send_text(json.dumps({
                    "type": "intruder",
                    "image_url": image_url,
                    "time": time.strftime("%H:%M:%S"),
                    "date": time.strftime("%Y-%m-%d"),
                    "activity": activity
                }))
            except:
                pass

        return {"status": "uploaded", "image_url": image_url}

    except Exception as e:
        print("❌ Upload error:", e)
        return {"error": str(e)}


@app.get("/get_intruder_logs")
def get_intruder_logs():
    return intruder_logs