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
                    await clients[target].send_text(json.dumps({
                        "type": "command",
                        "action": action,
                        "token": token,
                        "timestamp": timestamp
                    }))
                    print(f"[Cloud] 📤 {action} → {target}")

    except WebSocketDisconnect:
        print(f"[Cloud] ⚠️ {device_id} disconnected")

    finally:
        if device_id in clients:
            del clients[device_id]


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

        image_url = f"https://zephyr-altair-ai-server.onrender.com/intruders/{filename}"

        print(f"[Cloud] 📸 Intruder image saved: {filename}")

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


async def cleanup_old_files():
    while True:
        try:
            now = time.time()

            for file in os.listdir(UPLOAD_DIR):
                path = os.path.join(UPLOAD_DIR, file)

                if os.path.isfile(path):
                    if now - os.path.getmtime(path) > 3600:
                        os.remove(path)
                        print(f"[Cloud] 🧹 Deleted: {file}")

        except Exception as e:
            print("Cleanup error:", e)

        await asyncio.sleep(300)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_old_files())


@app.get("/")
def home():
    return {"status": "Zephyr Cloud Running 🚀"}