# ==============================
# FILE: cloud_client.py
# FINAL ULTRA STABLE CLOUD CLIENT
# FIXED DEAD SOCKETS
# FIXED RANDOM MISSED COMMANDS
# FIXED RECONNECT LOOP
# FIXED RENDER SLEEP WAKE
# FIXED STALE WEBSOCKET ISSUE
# ==============================

import asyncio
import websockets
import json
import threading
import traceback
import time

from network.security import verify_request


DEVICE_ID = "160c02a2018e7132"

CLOUD_URL = (
    "wss://zephyr-altair-ai-server.onrender.com/ws"
)

RECONNECT_DELAY = 3
PING_INTERVAL = 20
PING_TIMEOUT = 90


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
        self.last_ping = 0

        self.send_lock = None

        self.receive_task = None
        self.ping_task = None

        print(
            "☁️ Cloud client initializing..."
        )

        threading.Thread(

            target=self._start,

            daemon=True

        ).start()

    # ==========================
    # THREAD
    # ==========================

    def _start(self):

        try:

            asyncio.run(
                self._main_loop()
            )

        except Exception:

            traceback.print_exc()

    # ==========================
    # MAIN LOOP
    # ==========================

    async def _main_loop(self):

        self.send_lock = asyncio.Lock()

        while self.running:

            try:

                print(
                    "🌐 Connecting..."
                )

                ws = await websockets.connect(

                    CLOUD_URL,

                    ping_interval=None,

                    ping_timeout=None,

                    close_timeout=10,

                    max_size=None,

                    max_queue=None
                )

                self.websocket = ws
                self.connected = True

                self.last_pong = time.time()

                self.connection.update_cloud(
                    True
                )

                ok = await self._safe_send_raw({

                    "type":
                        "register",

                    "device_id":
                        DEVICE_ID,

                    "role":
                        "desktop"

                })

                if not ok:

                    raise Exception(
                        "register failed"
                    )

                print(
                    "✅ Cloud connected"
                )

                self.receive_task = (

                    asyncio.create_task(

                        self._receive_loop(
                            ws
                        )
                    )
                )

                self.ping_task = (

                    asyncio.create_task(

                        self._ping_loop(
                            ws
                        )
                    )
                )

                done, pending = (

                    await asyncio.wait(

                        [

                            self.receive_task,

                            self.ping_task

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
                    f"❌ Lost: {e}"
                )

            finally:

                self.connected = False

                self.connection.update_cloud(
                    False
                )

                for t in [

                    self.receive_task,

                    self.ping_task

                ]:

                    if t:

                        t.cancel()

                try:

                    if self.websocket:

                        await self.websocket.close()

                except:
                    pass

                self.websocket = None

                print(
                    f"🔄 Retry "
                    f"{RECONNECT_DELAY}s"
                )

                await asyncio.sleep(

                    RECONNECT_DELAY
                )

    # ==========================
    # RECEIVE
    # ==========================

    async def _receive_loop(

        self,

        ws

    ):

        while self.running:

            try:

                if (

                    ws != self.websocket

                    or

                    not self.connected

                ):

                    break

                raw = (

                    await asyncio.wait_for(

                        ws.recv(),

                        timeout=
                        PING_TIMEOUT
                    )
                )

                if not raw:

                    continue

                data = json.loads(raw)

                msg = data.get(
                    "type"
                )

                if msg == "pong":

                    self.last_pong = (

                        time.time()
                    )

                    continue

                elif msg == "command":

                    await self._handle(
                        data
                    )

            except asyncio.TimeoutError:

                print(
                    "❌ Timeout"
                )

                self.connected = False

                break

            except websockets.ConnectionClosed:

                self.connected = False

                break

            except:

                traceback.print_exc()

                await asyncio.sleep(1)

    # ==========================
    # PING
    # ==========================

    async def _ping_loop(

        self,

        ws

    ):

        while self.running:

            try:

                if (

                    not self.connected

                    or

                    ws != self.websocket

                ):

                    break

                now = time.time()

                if (

                    now -

                    self.last_pong

                    >

                    PING_TIMEOUT

                ):

                    print(
                        "❌ Pong timeout"
                    )

                    self.connected = False

                    break

                ok = (

                    await self
                    ._safe_send_raw({

                        "type":
                            "ping",

                        "device_id":
                            DEVICE_ID,

                        "timestamp":
                            int(now)

                    })
                )

                if not ok:

                    break

                self.last_ping = now

            except:

                self.connected = False

                break

            await asyncio.sleep(

                PING_INTERVAL
            )

    # ==========================
    # SEND
    # ==========================

    async def _safe_send_raw(

        self,

        payload

    ):

        try:

            if (

                not self.websocket

                or

                not self.connected

            ):

                return False

            async with self.send_lock:

                await self.websocket.send(

                    json.dumps(
                        payload
                    )
                )

            return True

        except:

            self.connected = False

            return False

    # ==========================
    # COMMANDS
    # ==========================

    async def _handle(

        self,

        data

    ):

        try:

            action = data.get(
                "action"
            )

            ts = data.get("ts")
            sig = data.get("sig")
            nonce = data.get("nonce")

            valid,msg = verify_request(

                action,

                ts,

                DEVICE_ID,

                sig,

                nonce
            )

            if not valid:

                print(
                    f"❌ Reject "
                    f"{msg}"
                )

                return

            print(
                f"📩 {action}"
            )

            if action == "lock":

                self.core.lock()

            elif action == "unlock":

                self.core.unlock()

            elif (

                action ==

                "start_live_camera"
            ):

                self.core.start_live_camera()

            elif (

                action ==

                "stop_live_camera"
            ):

                self.core.stop_live_camera()

        except:

            traceback.print_exc()

    async def send(

        self,

        payload

    ):

        return await (

            self._safe_send_raw(
                payload
            )
        )

    def stop(self):

        self.running = False

        self.connected = False

        print(
            "☁️ Cloud stopped"
        )