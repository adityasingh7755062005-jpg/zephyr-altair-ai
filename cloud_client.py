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

MAX_TIME_DIFF = 300  # 5 minutes


# 🔥 MATCH SERVER TOKEN LOGIC EXACTLY
def generate_token(device_id, secret_key, action, timestamp):
    raw = f"{device_id}{secret_key}{timestamp}{action}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def connect():
    while True:
        try:
            print("🚀 Connecting to Zephyr Cloud...")

            async with websockets.connect(
                CLOUD_URL,
                ping_interval=30,   # 🔥 increased (fix timeout)
                ping_timeout=30
            ) as websocket:

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

                            # 🔥 HARD CHECK
                            if not action or not timestamp or not token:
                                print("❌ Missing security data")
                                continue

                            try:
                                timestamp = int(timestamp)
                            except:
                                print("❌ Invalid timestamp format")
                                continue

                            # 🔥 TIME VALIDATION
                            if abs(int(time.time()) - timestamp) > MAX_TIME_DIFF:
                                print("❌ Expired request")
                                continue

                            # 🔥 TOKEN VALIDATION (FIXED)
                            expected_token = generate_token(
                                DEVICE_ID,
                                SECRET_KEY,
                                action,
                                timestamp
                            )

                            if token != expected_token:
                                print("❌ Invalid token (possible hacker)")
                                continue

                            print("✅ Command verified")

                            payload = {
                                "device_id": DEVICE_ID,
                                "timestamp": timestamp,
                                "token": token
                            }

                            try:
                                response = requests.post(
                                    f"{LOCAL_SERVER}/{action}",
                                    json=payload,
                                    timeout=5
                                )
                                print(f"⚡ Local response: {response.status_code}")
                            except Exception as e:
                                print("❌ Local request failed:", e)

                    except websockets.ConnectionClosed:
                        print("⚠️ Connection lost. Reconnecting...")
                        break

        except Exception as e:
            print("❌ Connection error:", e)

        await asyncio.sleep(3)


asyncio.run(connect())