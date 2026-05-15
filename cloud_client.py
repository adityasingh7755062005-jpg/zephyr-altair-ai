# ==============================
# FILE: cloud_client.py
# FINAL ULTRA STABLE CLOUD CLIENT
# FIXED NETWORK SWITCHING VERSION
# FIXED DEAD SOCKET VERSION
# FIXED COMMAND DELIVERY VERSION
# FIXED AUTO RECONNECT VERSION
# FINAL HEARTBEAT STABLE VERSION
# FINAL COMMAND STABLE VERSION
# FIXED WEBSOCKETS VERSION COMPATIBILITY
# FIXED MOBILE/DESKTOP ROLE CONFLICT
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

        print("☁️ Cloud client initializing...")

        threading.Thread(
            target=self._start,
            daemon=True
        ).start()

    # ==========================
    # THREAD START
    # ==========================

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

    # ==========================
    # MAIN LOOP
    # ==========================

    async def _main_loop(self):

        self.send_lock = asyncio.Lock()

        while self.running:

            try:

                print(
                    "🌐 Connecting to cloud..."
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

                # ==========================
                # REGISTER AS DESKTOP
                # ==========================

                register_payload = {

                    "type": "register",

                    "device_id": DEVICE_ID,

                    "role": "desktop"
                }

                ok = await self._safe_send_raw(
                    register_payload
                )

                if not ok:

                    raise Exception(
                        "Register failed"
                    )

                print(
                    f"✅ Connected as desktop "
                    f"{DEVICE_ID}"
                )

                self.receive_task = (
                    asyncio.create_task(
                        self._receive_loop(ws)
                    )
                )

                self.ping_task = (
                    asyncio.create_task(
                        self._ping_loop(ws)
                    )
                )

                done, pending = await asyncio.wait(

                    [

                        self.receive_task,
                        self.ping_task

                    ],

                    return_when=
                    asyncio.FIRST_COMPLETED
                )

                for task in pending:

                    task.cancel()

                    try:
                        await task
                    except:
                        pass

            except Exception as e:

                print(
                    f"❌ Cloud lost: {e}"
                )

            finally:

                self.connected = False

                self.connection.update_cloud(
                    False
                )

                for task in [

                    self.receive_task,
                    self.ping_task

                ]:

                    if task:

                        task.cancel()

                        try:
                            await task
                        except:
                            pass

                self.receive_task = None
                self.ping_task = None

                try:

                    if self.websocket:

                        await self.websocket.close()

                except:
                    pass

                self.websocket = None

                print(
                    f"🔄 Reconnect "
                    f"{RECONNECT_DELAY}s"
                )

                await asyncio.sleep(
                    RECONNECT_DELAY
                )

    # ==========================
    # RECEIVE LOOP
    # ==========================

    async def _receive_loop(
        self,
        ws
    ):

        while self.running:

            try:

                if ws != self.websocket:
                    break

                raw = await asyncio.wait_for(

                    ws.recv(),

                    timeout=PING_TIMEOUT
                )

                data = json.loads(raw)

                msg_type = data.get(
                    "type"
                )

                if msg_type == "pong":

                    self.last_pong = time.time()

                    continue

                elif msg_type == "command":

                    print(
                        "📨 Command packet"
                    )

                    await self._handle(
                        data
                    )

            except asyncio.TimeoutError:

                print(
                    "⚠️ Timeout"
                )

                break

            except websockets.ConnectionClosed:

                print(
                    "❌ Socket closed"
                )

                break

            except Exception as e:

                print(
                    f"❌ Receive: {e}"
                )

                traceback.print_exc()

                await asyncio.sleep(1)

    # ==========================
    # PING LOOP
    # ==========================

    async def _ping_loop(
        self,
        ws
    ):

        while self.running:

            try:

                if not self.connected:
                    break

                if ws != self.websocket:
                    break

                now = time.time()

                if (

                    now -
                    self.last_pong

                    > PING_TIMEOUT

                ):

                    print(
                        "❌ Pong timeout"
                    )

                    break

                payload = {

                    "type": "ping",

                    "device_id": DEVICE_ID,

                    "timestamp": int(now)
                }

                ok = await self._safe_send_raw(
                    payload
                )

                if not ok:
                    break

                self.last_ping = now

            except Exception as e:

                print(
                    f"❌ Ping: {e}"
                )

                break

            await asyncio.sleep(
                PING_INTERVAL
            )

    # ==========================
    # SAFE SEND
    # ==========================

    async def _safe_send_raw(
        self,
        payload
    ):

        try:

            if not self.websocket:
                return False

            if not self.connected:
                return False

            async with self.send_lock:

                await self.websocket.send(

                    json.dumps(
                        payload
                    )
                )

            return True

        except Exception as e:

            print(
                f"❌ Send: {e}"
            )

            self.connected = False

            return False

    # ==========================
    # HANDLE COMMANDS
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

            print(
                f"📩 {action}"
            )

            valid, msg = verify_request(

                action,

                ts,

                DEVICE_ID,

                sig,

                nonce
            )

            if not valid:

                print(
                    f"❌ Reject: {msg}"
                )

                return

            print(
                "✅ Verified"
            )

            if action == "lock":

                self.core.lock()

            elif action == "unlock":

                self.core.unlock()

            elif action == "start_live_camera":

                self.core.start_live_camera()

            elif action == "stop_live_camera":

                self.core.stop_live_camera()

            elif action == "camera_status":

                print(

                    self.core
                    .is_camera_running()

                )

        except Exception as e:

            print(
                f"❌ Command: {e}"
            )

            traceback.print_exc()

    async def send(
        self,
        payload
    ):

        return await self._safe_send_raw(
            payload
        )

    def stop(self):

        self.running = False

        self.connected = False

        print(
            "☁️ Cloud stopped"
        )