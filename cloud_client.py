# ==============================
# FILE: cloud_client.py
# FULL CLOUD CAMERA CONTROL VERSION
# FINAL STABLE CLOUD VERSION
# FIXED RECONNECT + PING VERSION
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

PING_INTERVAL = 15

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

        self.loop = None

        self.last_pong = time.time()

        self.connection_lock = asyncio.Lock()

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

        try:

            asyncio.run(
                self._loop()
            )

        except Exception as e:

            print(
                f"❌ Cloud thread crashed: {e}"
            )

            traceback.print_exc()

    # ==============================
    # MAIN LOOP
    # ==============================

    async def _loop(self):

        while self.running:

            try:

                print(
                    "🌐 Connecting to cloud..."
                )

                ws = await websockets.connect(

                    CLOUD_URL,

                    ping_interval=None,

                    ping_timeout=None,

                    close_timeout=5,

                    max_size=None,

                    max_queue=None
                )

                async with self.connection_lock:

                    self.websocket = ws

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

                await ws.send(
                    json.dumps(
                        register_payload
                    )
                )

                print(
                    f"✅ Connected as "
                    f"{DEVICE_ID}"
                )

                # ==============================
                # START TASKS
                # ==============================

                receive_task = asyncio.create_task(
                    self._receive_loop(ws)
                )

                ping_task = asyncio.create_task(
                    self._ping_loop(ws)
                )

                done, pending = await asyncio.wait(

                    [
                        receive_task,
                        ping_task
                    ],

                    return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:

                    task.cancel()

            except Exception as e:

                print(
                    f"❌ Cloud connection lost: "
                    f"{e}"
                )

            finally:

                try:

                    async with self.connection_lock:

                        self.connected = False

                        self.connection.update_cloud(
                            False
                        )

                        if self.websocket:

                            try:

                                await self.websocket.close()

                            except:
                                pass

                        self.websocket = None

                except:
                    pass

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

    async def _receive_loop(
        self,
        ws
    ):

        while self.running:

            try:

                raw = await ws.recv()

                data = json.loads(raw)

                msg_type = data.get("type")

                # ==============================
                # PONG
                # ==============================

                if msg_type == "pong":

                    self.last_pong = time.time()

                    continue

                # ==============================
                # HANDLE COMMAND
                # ==============================

                await self._handle(data)

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

                traceback.print_exc()

                await asyncio.sleep(1)

    # ==============================
    # PING LOOP
    # ==============================

    async def _ping_loop(
        self,
        ws
    ):

        while self.running:

            try:

                ping_payload = {

                    "type": "ping",

                    "device_id": DEVICE_ID,

                    "timestamp": int(
                        time.time()
                    )
                }

                await ws.send(
                    json.dumps(
                        ping_payload
                    )
                )

            except Exception as e:

                print(
                    f"❌ Cloud ping failed: "
                    f"{e}"
                )

                break

            await asyncio.sleep(
                PING_INTERVAL
            )

    # ==============================
    # HANDLE COMMANDS
    # ==============================

    async def _handle(
        self,
        data
    ):

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