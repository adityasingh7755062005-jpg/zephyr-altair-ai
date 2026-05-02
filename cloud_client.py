# ==============================
# FILE: cloud_client.py (FINAL)
# ==============================

import asyncio
import websockets
import json
import time
import hashlib
import threading

DEVICE_ID = "160c02a2018e7132"
SECRET_KEY = "c63bd8f574f9634e3f50bda3fd5cce15"
CLOUD_URL = "wss://zephyr-altair-ai-server.onrender.com/ws"

MAX_TIME_DIFF = 300


class CloudClient:

    def __init__(self, core, connection):
        self.core = core
        self.connection = connection
        self.running = True

        threading.Thread(
            target=self._start,
            daemon=True
        ).start()

    def _start(self):
        asyncio.run(self._loop())

    def generate_token(self, action, timestamp):
        raw = f"{DEVICE_ID}{SECRET_KEY}{timestamp}{action}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _loop(self):

        while self.running:
            try:
                print("🌐 [Cloud] Connecting...")

                async with websockets.connect(
                    CLOUD_URL,
                    ping_interval=20,
                    ping_timeout=20
                ) as ws:

                    await ws.send(json.dumps({
                        "type": "register",
                        "device_id": DEVICE_ID
                    }))

                    self.connection.update_cloud(True)
                    print("✅ [Cloud] Connected")

                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)

                        await self._handle(data)

            except Exception as e:
                print("❌ [Cloud]", e)
                self.connection.update_cloud(False)

            await asyncio.sleep(3)

    async def _handle(self, data):

        if data.get("type") != "command":
            return

        action = data.get("action")
        timestamp = data.get("timestamp")
        token = data.get("token")

        if not action or not timestamp or not token:
            return

        if abs(int(time.time()) - int(timestamp)) > MAX_TIME_DIFF:
            return

        expected = self.generate_token(action, int(timestamp))

        if token != expected:
            return

        print(f"⚡ [Cloud] {action}")

        if action == "lock":
            self.core.lock()

        elif action == "unlock":
            self.core.unlock()