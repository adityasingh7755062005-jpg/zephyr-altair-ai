import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import time
import hashlib

app = FastAPI()

clients = {}

# =========================
# WEBSOCKET ENDPOINT
# =========================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    device_id = None

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            # REGISTER DEVICE
            if data.get("type") == "register":
                device_id = data.get("device_id")
                clients[device_id] = websocket
                print(f"[Cloud] ✅ {device_id} connected")

            # FORWARD COMMAND (WITH TOKEN + TIMESTAMP)
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
                    print(f"        🕒 timestamp: {timestamp}")
                    print(f"        🔑 token: {token}")

                else:
                    print(f"[Cloud] ❌ Target {target} not found")

    except WebSocketDisconnect:
        print(f"[Cloud] ⚠️ {device_id} disconnected")

    finally:
        if device_id in clients:
            del clients[device_id]


# =========================
# HEALTH CHECK (RENDER)
# =========================
@app.get("/")
def home():
    return {"status": "Zephyr Cloud Running 🚀"}


# =========================
# MANUAL COMMAND TRIGGER (TESTING)
# =========================
@app.get("/send/{target}/{action}")
async def send_command(target: str, action: str):
    if target in clients:

        # 🔥 Generate TEMP token for testing
        timestamp = int(time.time())
        raw = f"{target}_{action}_{timestamp}"
        token = hashlib.sha256(raw.encode()).hexdigest()

        await clients[target].send_text(json.dumps({
            "type": "command",
            "action": action,
            "token": token,
            "timestamp": timestamp
        }))

        print(f"[Cloud] 🚀 {action} → {target}")
        print(f"        🕒 timestamp: {timestamp}")
        print(f"        🔑 token: {token}")

        return {"status": f"{action} sent to {target}"}
    else:
        return {"error": "Device not connected"}