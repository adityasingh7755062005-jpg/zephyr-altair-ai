import asyncio
import websockets
import json
import requests

DEVICE_ID = "laptop_001"

# 🔴 CHANGE THIS AFTER DEPLOYMENT
CLOUD_URL = "ws://your-render-url:8765"

LOCAL_SERVER = "http://127.0.0.1:5001"


async def connect():
    async with websockets.connect(CLOUD_URL) as websocket:

        # REGISTER
        await websocket.send(json.dumps({
            "type": "register",
            "device_id": DEVICE_ID
        }))

        print(f"[Laptop] Connected as {DEVICE_ID}")

        while True:
            message = await websocket.recv()
            data = json.loads(message)

            if data["type"] == "command":
                action = data["action"]

                print(f"[Laptop] Command received: {action}")

                try:
                    requests.post(f"{LOCAL_SERVER}/{action}")
                except Exception as e:
                    print("Error:", e)


asyncio.run(connect())