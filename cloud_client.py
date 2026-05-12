# ==============================
# FILE: cloud_client.py
# FINAL ULTRA STABLE CLOUD CLIENT
# FIXED WEBSOCKET DISCONNECTS
# FIXED CLOUD COMMANDS
# ==============================

import asyncio
import websockets
import json
import threading
import traceback
import time

from network.security import verify_request

# ==============================
# SETTINGS
# ==============================

DEVICE_ID = "160c02a2018e7132"

CLOUD_URL = (
    "wss://zephyr-altair-ai-server.onrender.com/ws"
)

RECONNECT_DELAY = 3

PING_INTERVAL = 30

PING_TIMEOUT = 60

# ==============================
# CLOUD CLIENT
# ==============================

class CloudClient:

    def __init__(
        self,
        core,
        connection
    ):

        self.core = core

        self.connection = connection

        self.running = True

        self.connected = False

        self.websocket = None

        self.last_pong = time.time()

        print(
            "☁️ Cloud client initializing..."
        )

        threading.Thread(

            target=self._start,

            daemon=True

        ).start()

    # ==============================
    # START THREAD
    # ==============================

    def _start(self):

        try:

            asyncio.run(
                self._main_loop()
            )

        except Exception as e:

            print(
                f"❌ Cloud thread crashed: {e}"
            )

            traceback.print_exc()

    # ==============================
    # MAIN LOOP
    # ==============================

    async def _main_loop(self):

        while self.running:

            try:

                print(
                    "🌐 Connecting to cloud..."
                )

                self.websocket = await websockets.connect(

                    CLOUD_URL,

                    ping_interval=PING_INTERVAL,

                    ping_timeout=PING_TIMEOUT,

                    close_timeout=10,

                    max_size=None,

                    max_queue=None
                )

                self.connected = True

                self.connection.update_cloud(
                    True
                )

                # ==============================
                # REGISTER DEVICE
                # ==============================

                register_payload = {

                    "type": "register",

                    "device_id": DEVICE_ID
                }

                await self.websocket.send(

                    json.dumps(
                        register_payload
                    )
                )

                print(
                    f"✅ Connected as {DEVICE_ID}"
                )

                # ==============================
                # RECEIVE LOOP
                # ==============================

                await self._receive_loop()

            except Exception as e:

                print(
                    f"❌ Cloud connection lost: {e}"
                )

            finally:

                self.connected = False

                self.connection.update_cloud(
                    False
                )

                try:

                    if self.websocket:

                        await self.websocket.close()

                except:
                    pass

                self.websocket = None

                print(
                    f"🔄 Reconnecting in "
                    f"{RECONNECT_DELAY}s..."
                )

                await asyncio.sleep(
                    RECONNECT_DELAY
                )

    # ==============================
    # RECEIVE LOOP
    # ==============================

    async def _receive_loop(self):

        while self.running:

            try:

                raw = await self.websocket.recv()

                data = json.loads(raw)

                msg_type = data.get("type")

                # ==============================
                # PONG
                # ==============================

                if msg_type == "pong":

                    self.last_pong = time.time()

                    continue

                # ==============================
                # COMMAND
                # ==============================

                if msg_type == "command":

                    await self._handle(data)

            except websockets.ConnectionClosedOK:

                print(
                    "⚠️ Cloud websocket closed normally"
                )

                break

            except websockets.ConnectionClosedError as e:

                print(
                    f"❌ Cloud websocket error: {e}"
                )

                break

            except Exception as e:

                print(
                    f"❌ Cloud receive error: {e}"
                )

                traceback.print_exc()

                await asyncio.sleep(1)

    # ==============================
    # HANDLE COMMANDS
    # ==============================

    async def _handle(
        self,
        data
    ):

        action = data.get("action")

        ts = data.get("ts")

        sig = data.get("sig")

        nonce = data.get("nonce")

        print("")
        print(
            f"📩 Command received "
            f"(CLOUD): {action}"
        )

        # ==============================
        # VERIFY REQUEST
        # ==============================

        valid, msg = verify_request(

            action,

            ts,

            DEVICE_ID,

            sig,

            nonce
        )

        if not valid:

            print(
                f"❌ CLOUD REJECTED: {msg}"
            )

            return

        print(
            "✅ Cloud command verified"
        )

        # ==============================
        # COMMANDS
        # ==============================

        if action == "lock":

            print(
                "[Control] 🔒 Lock (CLOUD)"
            )

            self.core.lock()

        elif action == "unlock":

            print(
                "[Control] 🔓 Unlock (CLOUD)"
            )

            self.core.unlock()

        elif action == "start_live_camera":

            print(
                "[Control] 📷 Start Camera "
                "(CLOUD)"
            )

            result = (
                self.core
                .start_live_camera()
            )

            print(
                f"📷 Camera Running: {result}"
            )

        elif action == "stop_live_camera":

            print(
                "[Control] 🛑 Stop Camera "
                "(CLOUD)"
            )

            self.core.stop_live_camera()

        elif action == "camera_status":

            running = (
                self.core
                .is_camera_running()
            )

            print(
                f"[Control] 📷 Camera Status: "
                f"{running}"
            )

        else:

            print(
                f"⚠️ Unknown command: {action}"
            )

    # ==============================
    # SEND MESSAGE
    # ==============================

    async def send(
        self,
        payload
    ):

        try:

            if (
                self.connected
                and
                self.websocket
            ):

                await self.websocket.send(

                    json.dumps(payload)
                )

                return True

        except Exception as e:

            print(
                f"❌ Cloud send failed: {e}"
            )

        return False

    # ==============================
    # STOP
    # ==============================

    def stop(self):

        self.running = False

        print(
            "☁️ Cloud client stopped"
        )