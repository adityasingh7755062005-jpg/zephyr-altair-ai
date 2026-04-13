import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

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

            # FORWARD COMMAND (device → device)
            elif data.get("type") == "command":
                target = data.get("target")
                action = data.get("action")

                if target in clients:
                    await clients[target].send_text(json.dumps({
                        "type": "command",
                        "action": action
                    }))
                    print(f"[Cloud] 📤 {action} sent to {target}")
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
# MANUAL COMMAND TRIGGER (VERY IMPORTANT)
# =========================
@app.get("/send/{target}/{action}")
async def send_command(target: str, action: str):
    if target in clients:
        await clients[target].send_text(json.dumps({
            "type": "command",
            "action": action
        }))
        print(f"[Cloud] 🚀 {action} sent to {target}")
        return {"status": f"{action} sent to {target}"}
    else:
        return {"error": "Device not connected"}