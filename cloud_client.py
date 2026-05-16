# ==============================
# FILE: cloud_client.py
# FULL CLOUD CAMERA CONTROL VERSION
# FINAL STABLE CLOUD VERSION
# FIXED DESKTOP REGISTRATION
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
    # START THREAD
    # ==============================

    def _start(self):

        try:

            asyncio.run(
                self._loop()
            )

        except Exception as e:

            print(
                f"❌ Cloud crashed: {e}"
            )

            traceback.print_exc()


    # ==============================
    # MAIN LOOP
    # ==============================

    async def _loop(self):

        while self.running:

            try:

                print(
                    "🌐 Connecting cloud..."
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

                # ==========================
                # FIXED REGISTER
                # ==========================

                register_payload = {

                    "type":
                        "register",

                    "device_id":
                        DEVICE_ID,

                    "role":
                        "desktop"
                }

                await ws.send(

                    json.dumps(

                        register_payload

                    )

                )

                print(

                    f"✅ Cloud connected "

                    f"as DESKTOP "

                    f"{DEVICE_ID}"

                )

                receive_task = (

                    asyncio.create_task(

                        self._receive_loop(
                            ws
                        )

                    )

                )

                ping_task = (

                    asyncio.create_task(

                        self._ping_loop(
                            ws
                        )

                    )

                )

                done, pending = (

                    await asyncio.wait(

                        [

                            receive_task,

                            ping_task

                        ],

                        return_when=

                        asyncio
                        .FIRST_COMPLETED

                    )

                )

                for t in pending:

                    t.cancel()

            except Exception as e:

                print(

                    "❌ Cloud lost:",

                    e

                )

            finally:

                try:

                    async with (

                            self.connection_lock

                    ):

                        self.connected = False

                        self.connection.update_cloud(
                            False
                        )

                        if self.websocket:

                            try:

                                await (
                                    self.websocket
                                    .close()
                                )

                            except:
                                pass

                        self.websocket = None

                except:
                    pass

                print(

                    f"🔄 Retry "

                    f"{RECONNECT_DELAY}s"

                )

                await asyncio.sleep(
                    RECONNECT_DELAY
                )

    # ==============================
    # RECEIVE
    # ==============================

    async def _receive_loop(

            self,

            ws

    ):

        while self.running:

            try:

                raw = await ws.recv()

                data = json.loads(
                    raw
                )

                msg_type = data.get(
                    "type"
                )

                if msg_type == "pong":

                    self.last_pong = (

                        time.time()

                    )

                    continue

                await self._handle(
                    data
                )

            except (

                    websockets
                    .ConnectionClosed

            ):

                print(
                    "❌ Closed"
                )

                break

            except Exception as e:

                print(
                    e
                )

                traceback.print_exc()

                await asyncio.sleep(
                    1
                )

    # ==============================
    # PING
    # ==============================

    async def _ping_loop(

            self,

            ws

    ):

        while self.running:

            try:

                payload = {

                    "type":
                        "ping",

                    "device_id":
                        DEVICE_ID,

                    "timestamp":

                        int(
                            time.time()
                        )

                }

                await ws.send(

                    json.dumps(
                        payload
                    )

                )

            except Exception as e:

                print(

                    "❌ Ping:",

                    e

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

        if data.get(
                "type"
        ) != "command":

            return

        action = data.get(
            "action"
        )

        ts = data.get(
            "ts"
        )

        sig = data.get(
            "sig"
        )

        nonce = data.get(
            "nonce"
        )

        print(

            f"\n📩 CLOUD CMD: "

            f"{action}"

        )

        valid, msg = (

            verify_request(

                action,

                ts,

                DEVICE_ID,

                sig,

                nonce

            )

        )

        if not valid:

            print(

                "❌ Reject:",

                msg

            )

            return

        print(
            "✅ Verified"
        )

        # LOCK

        if action == "lock":

            self.core.lock()

        # UNLOCK

        elif action == "unlock":

            self.core.unlock()

        # CAMERA START

        elif (

                action

                ==

                "start_live_camera"

        ):

            result = (

                self.core
                .start_live_camera()

            )

            print(
                result
            )

        # CAMERA STOP

        elif (

                action

                ==

                "stop_live_camera"

        ):

            self.core.stop_live_camera()

        elif (

                action

                ==

                "camera_status"

        ):

            print(

                self.core
                .is_camera_running()

            )

        else:

            print(

                "⚠️ Unknown:",

                action

            )

    # ==============================
    # SEND RAW
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

                await (

                    self.websocket.send(

                        json.dumps(
                            payload
                        )

                    )

                )

                return True

        except Exception as e:

            print(
                e
            )

        return False


    # ==============================
    # STOP
    # ==============================

    def stop(self):

        self.running = False

        self.connected = False

        print(
            "☁️ Cloud stopped"
        )