# ==============================
# FILE: cloud_client.py
# FULL CLOUD CAMERA CONTROL VERSION
# ==============================

import asyncio
import websockets
import json
import threading
import traceback

from network.security import verify_request

# ==============================
# SETTINGS
# ==============================

DEVICE_ID = "160c02a2018e7132"

CLOUD_URL = (
    "wss://zephyr-altair-ai-server.onrender.com/ws"
)

RECONNECT_DELAY = 3

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

        print(
            "☁️ Cloud client initializing..."
        )

        threading.Thread(

            target=self._start,

            daemon=True

        ).start()

    # ==============================
    # START LOOP
    # ==============================

    def _start(self):

        asyncio.run(
            self._loop()
        )

    # ==============================
    # MAIN LOOP
    # ==============================

    async def _loop(self):

        while self.running:

            try:

                print(
                    "🌐 Connecting to cloud..."
                )

                async with websockets.connect(

                    CLOUD_URL,

                    ping_interval=20,

                    ping_timeout=20,

                    close_timeout=5,

                    max_size=None

                ) as ws:

                    self.websocket = ws

                    self.connected = True

                    # ==============================
                    # REGISTER DEVICE
                    # ==============================

                    register_payload = {

                        "type": "register",

                        "device_id": DEVICE_ID
                    }

                    await ws.send(
                        json.dumps(
                            register_payload
                        )
                    )

                    self.connection.update_cloud(
                        True
                    )

                    print(
                        f"✅ Connected as "
                        f"{DEVICE_ID}"
                    )

                    # ==============================
                    # RECEIVE LOOP
                    # ==============================

                    while self.running:

                        try:

                            msg = await ws.recv()

                            data = json.loads(msg)

                            await self._handle(
                                data
                            )

                        except websockets.ConnectionClosed:

                            print(
                                "❌ Cloud websocket closed"
                            )

                            break

                        except Exception as e:

                            print(
                                f"❌ Cloud receive error: "
                                f"{e}"
                            )

            except Exception as e:

                print(
                    f"❌ Cloud connection lost: "
                    f"{e}"
                )

            # ==============================
            # DISCONNECTED
            # ==============================

            self.connected = False

            self.websocket = None

            self.connection.update_cloud(
                False
            )

            print(
                f"🔄 Reconnecting in "
                f"{RECONNECT_DELAY}s..."
            )

            await asyncio.sleep(
                RECONNECT_DELAY
            )

    # ==============================
    # HANDLE COMMANDS
    # ==============================

    async def _handle(
        self,
        data
    ):

        # ==============================
        # ONLY COMMANDS
        # ==============================

        if data.get("type") != "command":
            return

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
        # VERIFY
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
                f"❌ CLOUD REJECTED: "
                f"{msg}"
            )

            return

        print(
            "✅ Cloud command verified"
        )

        # ==============================
        # LOCK
        # ==============================

        if action == "lock":

            print(
                "[Control] 🔒 Lock (CLOUD)"
            )

            self.core.lock()

        # ==============================
        # UNLOCK
        # ==============================

        elif action == "unlock":

            print(
                "[Control] 🔓 Unlock (CLOUD)"
            )

            self.core.unlock()

        # ==============================
        # START LIVE CAMERA
        # ==============================

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
                f"📷 Camera Running: "
                f"{result}"
            )

        # ==============================
        # STOP LIVE CAMERA
        # ==============================

        elif action == "stop_live_camera":

            print(
                "[Control] 🛑 Stop Camera "
                "(CLOUD)"
            )

            self.core.stop_live_camera()

        # ==============================
        # CAMERA STATUS
        # ==============================

        elif action == "camera_status":

            running = (
                self.core
                .is_camera_running()
            )

            print(
                f"[Control] 📷 Camera Status: "
                f"{running}"
            )

        # ==============================
        # UNKNOWN COMMAND
        # ==============================

        else:

            print(
                f"⚠️ Unknown command: "
                f"{action}"
            )

    # ==============================
    # SEND RAW MESSAGE
    # ==============================

    async def send(
        self,
        payload
    ):

        try:

            if (
                self.websocket
                and
                self.connected
            ):

                await self.websocket.send(
                    json.dumps(payload)
                )

                return True

        except Exception as e:

            print(
                f"❌ Cloud send failed: "
                f"{e}"
            )

        return False

    # ==============================
    # STOP CLIENT
    # ==============================

    def stop(self):

        self.running = False

        print(
            "☁️ Cloud client stopped"
        )