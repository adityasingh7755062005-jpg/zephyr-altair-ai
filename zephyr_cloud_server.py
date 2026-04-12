import asyncio
import json
import websockets
from fastapi import FastAPI
import threading

app = FastAPI()

clients = {}

# =========================
# WEBSOCKET HANDLER
# =========================
async def handler(websocket):
    device_id = None

    try:
        async for message in websocket:
            data = json.loads(message)

            # REGISTER
            if data["type"] == "register":
                device_id = data["device_id"]
                clients[device_id] = websocket
                print(f"[Cloud] {device_id} connected")

            # FORWARD COMMAND
            elif data["type"] == "command":
                target = data["target"]
                action = data["action"]

                if target in clients:
                    await clients[target].send(json.dumps({
                        "type": "command",
                        "action": action
                    }))
                    print(f"[Cloud] {action} sent to {target}")
                else:
                    print(f"[Cloud] Target {target} not found")

    except:
        print(f"[Cloud] {device_id} disconnected")

    finally:
        if device_id in clients:
            del clients[device_id]


# =========================
# START WEBSOCKET SERVER
# =========================
async def start_ws():
    print("[Cloud] WebSocket starting...")
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    print("[Cloud] WS running on port 8765 🚀")
    await server.wait_closed()


def run_ws():
    asyncio.run(start_ws())


# =========================
# FASTAPI ROUTE (for Render health check)
# =========================
@app.get("/")
def home():
    return {"status": "Zephyr Cloud Running 🚀"}


# =========================
# START THREAD
# =========================
threading.Thread(target=run_ws, daemon=True).start()