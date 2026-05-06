import asyncio
import websockets
import json
import threading

from network.security import verify_request

DEVICE_ID = "160c02a2018e7132"
CLOUD_URL = "wss://zephyr-altair-ai-server.onrender.com/ws"


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

    async def _loop(self):

        while self.running:
            try:
                print("🌐 Connecting to cloud...")

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

                    print(f"✅ Connected as {DEVICE_ID}")

                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        await self._handle(data)

            except Exception:
                print("❌ Cloud connection lost")
                self.connection.update_cloud(False)

            await asyncio.sleep(3)

    async def _handle(self, data):

        if data.get("type") != "command":
            return

        action = data.get("action")
        ts = data.get("ts")
        sig = data.get("sig")
        nonce = data.get("nonce")  # ✅ NEW

        print(f"📩 Command received (CLOUD): {action}")

        valid, msg = verify_request(action, ts, DEVICE_ID, sig, nonce)

        if not valid:
            print(f"❌ CLOUD REJECTED: {msg}")
            return

        if action == "lock":
            print("[Control] 🔒 Lock (CLOUD)")
            self.core.lock()

        elif action == "unlock":
            print("[Control] 🔓 Unlock (CLOUD)")
            self.core.unlock()