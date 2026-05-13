# ==============================
# FILE: cloud_client.py
# FINAL ULTRA STABLE CLOUD CLIENT
# FIXED NETWORK SWITCHING VERSION
# FIXED DEAD SOCKET VERSION
# FIXED COMMAND DELIVERY VERSION
# FIXED AUTO RECONNECT VERSION
# FINAL HEARTBEAT STABLE VERSION
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

PING_INTERVAL = 20

PING_TIMEOUT = 90

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

        self.last_ping = 0

        self.send_lock = None

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

                # ==============================
                # REGISTER DEVICE
                # ==============================

                register_payload = {

                    "type": "register",

                    "device_id": DEVICE_ID
                }

                ok = await self._safe_send_raw(
                    register_payload
                )

                if not ok:

                    raise Exception(
                        "Register failed"
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
                    f"❌ Cloud connection lost: "
                    f"{e}"
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

    async def _receive_loop(
        self,
        ws
    ):

        while self.running:

            try:

                raw = await asyncio.wait_for(

                    ws.recv(),

                    timeout=PING_TIMEOUT
                )

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

            except asyncio.TimeoutError:

                print(
                    "⚠️ Cloud timeout detected"
                )

                break

            except websockets.ConnectionClosedOK:

                print(
                    "⚠️ Cloud websocket closed normally"
                )

                break

            except websockets.ConnectionClosedError as e:

                print(
                    f"❌ Cloud websocket error: "
                    f"{e}"
                )

                break

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

                if not self.connected:

                    break

                now = time.time()

                # ==============================
                # PONG TIMEOUT
                # ==============================

                if (

                    now -
                    self.last_pong

                    > PING_TIMEOUT
                ):

                    print(
                        "❌ Cloud pong timeout"
                    )

                    break

                # ==============================
                # SEND PING
                # ==============================

                ping_payload = {

                    "type": "ping",

                    "device_id": DEVICE_ID,

                    "timestamp": int(now)
                }

                ok = await self._safe_send_raw(
                    ping_payload
                )

                if not ok:

                    print(
                        "❌ Ping send failed"
                    )

                    break

                self.last_ping = now

            except Exception as e:

                print(
                    f"❌ Ping loop error: "
                    f"{e}"
                )

                break

            await asyncio.sleep(
                PING_INTERVAL
            )

    # ==============================
    # SAFE SEND RAW
    # ==============================

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

                    json.dumps(payload)
                )

            return True

        except websockets.ConnectionClosed:

            print(
                "❌ Websocket closed during send"
            )

            self.connected = False

            return False

        except Exception as e:

            print(
                f"❌ Cloud send failed: "
                f"{e}"
            )

            self.connected = False

            return False

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
        # START CAMERA
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
        # STOP CAMERA
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
        # UNKNOWN
        # ==============================

        else:

            print(
                f"⚠️ Unknown command: "
                f"{action}"
            )

    # ==============================
    # SEND MESSAGE
    # ==============================

    async def send(
        self,
        payload
    ):

        return await self._safe_send_raw(
            payload
        )

    # ==============================
    # STOP
    # ==============================

    def stop(self):

        self.running = False

        self.connected = False

        print(
            "☁️ Cloud client stopped"
        )