# ==============================
# FILE: network/cloud_client.py
# ==============================

import asyncio
import websockets
import json
import time
import hashlib


class CloudClient:
    """
    🔥 Pure Cloud Listener
    - Only listens from cloud
    - No local HTTP calls
    - Directly triggers Core18
    """

    def __init__(self, core):
        self.core = core

        self.DEVICE_ID = "160c02a2018e7132"
        self.SECRET_KEY = "c63bd8f574f9634e3f50bda3fd5cce15"

        self.CLOUD_URL = "wss://zephyr-altair-ai-server.onrender.com/ws"
        self.MAX_TIME_DIFF = 300

    # ==============================
    # 🔐 TOKEN GENERATION
    # ==============================
    def generate_token(self, device_id, secret_key, action, timestamp):
        raw = f"{device_id}{secret_key}{timestamp}{action}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ==============================
    # 🌐 CLOUD LOOP
    # ==============================
    async def connect(self):

        while True:
            try:
                print("🌐 [CloudClient] Connecting...")

                async with websockets.connect(
                    self.CLOUD_URL,
                    ping_interval=30,
                    ping_timeout=30
                ) as ws:

                    # 🔥 Register device
                    await ws.send(json.dumps({
                        "type": "register",
                        "device_id": self.DEVICE_ID
                    }))

                    print("✅ [CloudClient] Connected")

                    while True:
                        message = await ws.recv()
                        data = json.loads(message)

                        if data.get("type") == "command":

                            action = data.get("action")
                            timestamp = data.get("timestamp")
                            token = data.get("token")

                            # ==============================
                            # 🔐 VALIDATION
                            # ==============================
                            if not action or not timestamp or not token:
                                print("❌ Invalid payload")
                                continue

                            try:
                                timestamp = int(timestamp)
                            except:
                                print("❌ Invalid timestamp")
                                continue

                            if abs(int(time.time()) - timestamp) > self.MAX_TIME_DIFF:
                                print("❌ Expired command")
                                continue

                            expected = self.generate_token(
                                self.DEVICE_ID,
                                self.SECRET_KEY,
                                action,
                                timestamp
                            )

                            if token != expected:
                                print("❌ Invalid token")
                                continue

                            print(f"⚡ [CloudClient] Executing: {action}")

                            # ==============================
                            # 🔥 DIRECT CORE EXECUTION
                            # ==============================
                            if action == "lock":
                                self.core.lock()

                            elif action == "unlock":
                                self.core.unlock()

            except Exception as e:
                print("❌ [CloudClient] Error:", e)

            await asyncio.sleep(3)