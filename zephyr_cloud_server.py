import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import time
import hashlib

app = FastAPI()

clients = {}

# 🔐 SAME SECRET MAP (for testing manual endpoint)
DEVICE_SECRETS = {
    "160c02a2018e7132": "c63bd8f574f9634e3f50bda3fd5cce15"
}


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

        await clients[target].send_text(json.dumps({
            "type": "command",
            "action": action,
            "token": token,
            "timestamp": timestamp
        }))

        print(f"[Cloud] 🚀 {action} → {target}")
        print(f"        🕒 {timestamp}")
        print(f"        🔑 {token}")

        return {"status": f"{action} sent to {target}"}

    else:
        return {"error": "Device not connected"}