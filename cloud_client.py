import asyncio
import websockets
import json
import requests
import time
import hashlib

DEVICE_ID = "laptop_001"

# 🔐 SAME secret used during pairing (IMPORTANT)
SECRET_KEY = "c63bd8f574f9634e3f50bda3fd5cce15"

# ✅ Cloud server
CLOUD_URL = "wss://zephyr-altair-ai-server.onrender.com/ws"

# ✅ Local AI server
LOCAL_SERVER = "http://127.0.0.1:5001"

# ⏱️ Allowable delay (seconds)
MAX_TIME_DIFF = 10


# 🔐 TOKEN GENERATION (same logic as Android)
def generate_token(action, timestamp):
    raw = f"{DEVICE_ID}{SECRET_KEY}{timestamp}{action}"
    return hashlib.sha256(raw.encode()).hexdigest()


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
                            timestamp = data.get("timestamp")
                            token = data.get("token")

                            print(f"📩 Command received: {action}")
                            print(f"   🕒 timestamp: {timestamp}")
                            print(f"   🔑 token: {token}")

                            # =========================
                            # 🔐 SECURITY CHECK
                            # =========================

                            # 1. Check timestamp exists
                            if not timestamp or not token:
                                print("❌ Missing security data")
                                continue

                            # 2. Check time difference
                            current_time = int(time.time())
                            if abs(current_time - int(timestamp)) > MAX_TIME_DIFF:
                                print("❌ Expired or replay attack")
                                continue

                            # 3. Validate token
                            expected_token = generate_token(action, timestamp)

                            if token != expected_token:
                                print("❌ Invalid token (possible hacker)")
                                continue

                            print("✅ Command verified")

                            # =========================
                            # EXECUTE COMMAND
                            # =========================
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