import asyncio
import websockets
import json
import requests
import time
import hashlib

DEVICE_ID = "160c02a2018e7132"
SECRET_KEY = "c63bd8f574f9634e3f50bda3fd5cce15"

CLOUD_URL = "wss://zephyr-altair-ai-server.onrender.com/ws"
LOCAL_SERVER = "http://127.0.0.1:5001"

# 🔥 FIX: Increased tolerance (was 10)
MAX_TIME_DIFF = 300   # 5 minutes


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
                            print(f"   🕒 timestamp: {timestamp}")
                            print(f"   🔑 token: {token}")

                            if not timestamp or not token:
                                print("❌ Missing security data")
                                continue

                            try:
                                timestamp = int(timestamp)
                            except:
                                print("❌ Invalid timestamp format")
                                continue

                            if abs(int(time.time()) - timestamp) > MAX_TIME_DIFF:
                                print("❌ Expired request")
                                continue

                            expected_token = generate_token(action, timestamp)

                            if token != expected_token:
                                print("❌ Invalid token (possible hacker)")
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
                        print("⚠️ Connection lost. Reconnecting...")
                        break

        except Exception as e:
            print("❌ Connection error:", e)

        time.sleep(3)


asyncio.run(connect())