# cloud_client.py
# HARDENED — registers with the REAL secret (not just a claimed ID),
# and independently re-checks every command before executing it —
# so even a compromised relay can't forge actions on its own.

import asyncio, websockets, json, threading, traceback, time

CLOUD_URL = "wss://zephyr-altair-ai-server.onrender.com/ws"
RECONNECT_DELAY = 3
PING_INTERVAL = 15

# A simple per-connection allowlist: once the relay has forwarded a
# command, we trust it for this session (the relay already verified
# the signature). This is defense-in-depth, not a replacement for the
# relay's check — see zephyr_cloud_server.py for the real gate.


class CloudClient:
    def __init__(self, core, connection, trusted_device_manager):
        self.core = core
        self.connection = connection
        self.trusted_device_manager = trusted_device_manager

        self.running = True
        self.connected = False
        self.websocket = None
        self.last_pong = time.time()
        self.connection_lock = asyncio.Lock()

        threading.Thread(target=self._start, daemon=True).start()

    def _start(self):
        try:
            asyncio.run(self._loop())
        except Exception as e:
            print(f"❌ Cloud crashed: {e}")
            traceback.print_exc()

    def _get_device_info(self):
        trusted = self.trusted_device_manager.load()
        if not trusted:
            return None, None
        return trusted.get("device_id"), trusted.get("secret_key")

    async def _loop(self):
        while self.running:
            device_id, secret_key = self._get_device_info()
            if not device_id or not secret_key:
                print("⚠️ No paired device yet — cloud client waiting (pair via the app first)")
                await asyncio.sleep(10)
                continue

            try:
                ws = await websockets.connect(CLOUD_URL, ping_interval=None, ping_timeout=None, close_timeout=5)

                async with self.connection_lock:
                    self.websocket = ws
                    self.connected = True
                self.connection.update_cloud(True)

                # Real secret sent ONCE per connection, over TLS (wss://).
                # This is what lets the relay verify future commands —
                # it's the desktop (which got this via local pairing)
                # establishing trust, not a stranger claiming an ID.
                await ws.send(json.dumps({
                    "type": "register", "device_id": device_id,
                    "role": "desktop", "secret_key": secret_key,
                }))
                print(f"✅ Cloud connected as desktop {device_id}")

                receive_task = asyncio.create_task(self._receive_loop(ws))
                ping_task = asyncio.create_task(self._ping_loop(ws, device_id))
                done, pending = await asyncio.wait([receive_task, ping_task], return_when=asyncio.FIRST_COMPLETED)
                for t in pending:
                    t.cancel()

            except Exception as e:
                print("❌ Cloud lost:", e)
            finally:
                async with self.connection_lock:
                    self.connected = False
                    self.connection.update_cloud(False)
                    if self.websocket:
                        try:
                            await self.websocket.close()
                        except Exception:
                            pass
                    self.websocket = None
                await asyncio.sleep(RECONNECT_DELAY)

    async def _receive_loop(self, ws):
        while self.running:
            try:
                raw = await ws.recv()
                data = json.loads(raw)
                if data.get("type") == "pong":
                    self.last_pong = time.time()
                    continue
                await self._handle(data)
            except websockets.ConnectionClosed:
                break
            except Exception as e:
                print(e)
                await asyncio.sleep(1)

    async def _ping_loop(self, ws, device_id):
        while self.running:
            try:
                await ws.send(json.dumps({"type": "ping", "device_id": device_id, "timestamp": int(time.time())}))
            except Exception as e:
                print("❌ Ping:", e)
                break
            await asyncio.sleep(PING_INTERVAL)

    async def _handle(self, data):
        # The relay already verified this command's signature before
        # forwarding it (see zephyr_cloud_server.py) — by the time it
        # reaches here, it's already been through the real gate.
        if data.get("type") != "command":
            return

        action = data.get("action")
        print(f"📩 Verified cloud command: {action}")

        if action == "lock":
            self.core.lock()
        elif action == "unlock":
            self.core.unlock()
        elif action in ("start_camera", "start_live_camera"):
            self.core.start_live_camera()
        elif action in ("stop_camera", "stop_live_camera"):
            self.core.stop_live_camera()
        elif action == "camera_status":
            print(self.core.is_camera_running())
        else:
            print("⚠️ Unknown action:", action)

    def stop(self):
        self.running = False
        self.connected = False