import asyncio
import websockets
import json
import requests
import time

DEVICE_ID = "laptop_001"

# ✅ CORRECT WebSocket URL (VERY IMPORTANT)
CLOUD_URL = "wss://zephyr-altair-ai-server.onrender.com/ws"

# ✅ Local AI server
LOCAL_SERVER = "http://127.0.0.1:5001"


async def connect():
    while True:
        try:
            print("🚀 Connecting to Zephyr Cloud...")

            async with websockets.connect(CLOUD_URL) as websocket:

                # REGISTER DEVICE
                await websocket.send(json.dumps({
                    "type": "register",
                    "device_id": DEVICE_ID
                }))

                print(f"✅ Connected as {DEVICE_ID}")

                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)

                        if data.get("type") == "command":
                            action = data.get("action")

                            print(f"📩 Command received: {action}")

                            try:
                                response = requests.post(f"{LOCAL_SERVER}/{action}")
                                print(f"⚡ Local response: {response.status_code}")
                            except Exception as e:
                                print("❌ Local server error:", e)

                    except websockets.ConnectionClosed:
                        print("⚠️ Connection lost. Reconnecting...")
                        break

        except Exception as e:
            print("❌ Connection error:", e)

        time.sleep(3)


asyncio.run(connect())