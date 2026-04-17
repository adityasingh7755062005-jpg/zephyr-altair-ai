import asyncio
import websockets
import json
import requests
import time
import hashlib

DEVICE_ID = "160c02a2018e7132"
SECRET_KEY = "c63bd8f574f9634e3f50bda3fd5cce15"

CLOUD_URL = "wss://zephyr-altair-ai-server.onrender.com/ws"
LOCAL_SERVER = "http://127.0.0.1:5002"

MAX_TIME_DIFF = 10


def generate_token(action, timestamp):
    raw = f"{DEVICE_ID}{SECRET_KEY}{timestamp}{action}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def connect():
    while True:
        try:
            print("🚀 Connecting to Zephyr Cloud...")

            async with websockets.connect(CLOUD_URL) as websocket:

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
                            timestamp = data.get("timestamp")
                            token = data.get("token")

                            print(f"📩 Command received: {action}")

                            if not timestamp or not token:
                                continue

                            if abs(int(time.time()) - int(timestamp)) > MAX_TIME_DIFF:
                                print("❌ Expired")
                                continue

                            if token != generate_token(action, timestamp):
                                print("❌ Invalid token")
                                continue

                            print("✅ Command verified")

                            payload = {
                                "device_id": DEVICE_ID,
                                "timestamp": timestamp,
                                "token": token
                            }

                            response = requests.post(
                                f"{LOCAL_SERVER}/{action}",
                                json=payload
                            )

                            print(f"⚡ Local response: {response.status_code}")

                    except websockets.ConnectionClosed:
                        print("⚠️ Reconnecting...")
                        break

        except Exception as e:
            print("❌ Error:", e)

        time.sleep(3)


asyncio.run(connect())