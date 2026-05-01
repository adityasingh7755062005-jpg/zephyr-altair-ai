# ==============================
# FILE: network/connection_manager.py
# ==============================

import time
import threading
import requests
import asyncio
import websockets
import json


class ConnectionManager:
    """
    🔥 Smart connection layer
    - Handles LOCAL + CLOUD
    - Auto reconnect
    - Latency-based routing
    """

    def __init__(self, core):
        self.core = core  # 🔗 reference to Core18

        self.ws = None
        self.ws_connected = False
        self.latency = 999
        self.running = True

        self.LOCAL_URL = "http://127.0.0.1:5001"
        self.CLOUD_WS = "wss://zephyr-altair-ai-server.onrender.com/ws"
        self.DEVICE_ID = "160c02a2018e7132"

        # 🔥 Start background systems
        threading.Thread(target=self._start_ws, daemon=True).start()
        threading.Thread(target=self._health_monitor, daemon=True).start()

    # ==========================
    # 🌐 CLOUD WEBSOCKET
    # ==========================
    async def _ws_loop(self):
        while self.running:
            try:
                print("🌐 Connecting to cloud...")

                async with websockets.connect(
                    self.CLOUD_WS,
                    ping_interval=20,
                    ping_timeout=20
                ) as ws:

                    self.ws = ws
                    self.ws_connected = True

                    # 🔥 register device
                    await ws.send(json.dumps({
                        "type": "register",
                        "device_id": self.DEVICE_ID
                    }))

                    print("✅ Cloud connected")

                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)

                        # 🔥 receive command from cloud
                        if data.get("type") == "command":
                            action = data.get("action")

                            print(f"📩 Cloud command: {action}")

                            if action == "lock":
                                self.core.lock()

                            elif action == "unlock":
                                self.core.unlock()

            except Exception as e:
                print("❌ WS error:", e)
                self.ws_connected = False
                await asyncio.sleep(2)

    def _start_ws(self):
        asyncio.run(self._ws_loop())

    # ==========================
    # 📡 LOCAL LATENCY CHECK
    # ==========================
    def _ping_local(self):
        try:
            start = time.time()
            requests.get(f"{self.LOCAL_URL}/", timeout=1)
            self.latency = int((time.time() - start) * 1000)
            return True
        except:
            self.latency = 999
            return False

    # ==========================
    # 🧠 HEALTH MONITOR
    # ==========================
    def _health_monitor(self):
        while self.running:
            self._ping_local()

            print(f"📡 Local: {self.latency} ms | Cloud: {self.ws_connected}")

            time.sleep(3)

    # ==========================
    # 🚀 SMART SEND (optional)
    # ==========================
    def send(self, action):

        # 🔥 LOCAL FIRST
        if self.latency < 200:
            try:
                requests.post(f"{self.LOCAL_URL}/{action}", json={}, timeout=2)
                print("⚡ Sent via LOCAL")
                return
            except:
                pass

        # 🔥 CLOUD FALLBACK
        if self.ws_connected:
            try:
                asyncio.run(self.ws.send(json.dumps({
                    "type": "command",
                    "target": self.DEVICE_ID,
                    "action": action
                })))
                print("🌐 Sent via CLOUD")
                return
            except:
                pass

        print("❌ No connection available")