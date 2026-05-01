# ==============================
# FILE 6: cloud_client.py
# ==============================

import asyncio
import websockets
import json
import requests
import time
import hashlib

# 🔐 Device identity (must match server)
DEVICE_ID = "160c02a2018e7132"
SECRET_KEY = "c63bd8f574f9634e3f50bda3fd5cce15"

# 🌐 Cloud WebSocket endpoint
CLOUD_URL = "wss://zephyr-altair-ai-server.onrender.com/ws"

# 🏠 Local control server
LOCAL_SERVER = "http://127.0.0.1:5001"

# ⏱️ Token expiry tolerance
MAX_TIME_DIFF = 300


# ==============================
# TOKEN GENERATION (SYNC WITH SERVER)
# ==============================
def generate_token(device_id, secret_key, action, timestamp):
    raw = f"{device_id}{secret_key}{timestamp}{action}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ==============================
# MAIN CONNECTION LOOP (AUTO RECONNECT)
# ==============================
async def connect():

    while True:
        try:
            print("🌐 Connecting to Cloud...")

            async with websockets.connect(
                CLOUD_URL,
                ping_interval=30,
                ping_timeout=30
            ) as ws:

                # 📡 Register device
                await ws.send(json.dumps({
                    "type": "register",
                    "device_id": DEVICE_ID
                }))

                print("✅ Connected to cloud")

                while True:
                    message = await ws.recv()
                    data = json.loads(message)

                    if data.get("type") == "command":

                        action = data.get("action")
                        timestamp = data.get("timestamp")
                        token = data.get("token")

                        # 🔐 Basic validation
                        if not action or not timestamp or not token:
                            print("❌ Invalid command payload")
                            continue

                        try:
                            timestamp = int(timestamp)
                        except:
                            continue

                        # ⏱️ Expiry check
                        if abs(int(time.time()) - timestamp) > MAX_TIME_DIFF:
                            print("❌ Expired command")
                            continue

                        # 🔐 Token verification
                        expected = generate_token(
                            DEVICE_ID,
                            SECRET_KEY,
                            action,
                            timestamp
                        )

                        if token != expected:
                            print("❌ Invalid token")
                            continue

                        print(f"⚡ Executing: {action}")

                        payload = {
                            "device_id": DEVICE_ID,
                            "timestamp": timestamp,
                            "token": token
                        }

                        try:
                            res = requests.post(
                                f"{LOCAL_SERVER}/{action}",
                                json=payload,
                                timeout=5
                            )
                            print("✅ Local response:", res.status_code)

                        except Exception as e:
                            print("❌ Local error:", e)

        except Exception as e:
            print("❌ Cloud connection error:", e)

        # 🔁 Retry after delay
        await asyncio.sleep(3)


# ==============================
# ENTRY
# ==============================
if __name__ == "__main__":
    asyncio.run(connect())