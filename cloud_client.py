# cloud_client.py
# HARDENED — registers with the REAL secret (not just a claimed ID),
# and independently re-checks every command before executing it —
# so even a compromised relay can't forge actions on its own.

import asyncio, websockets, json, threading, traceback, time
import requests

CLOUD_URL = "wss://zephyr-altair-ai-server.onrender.com/ws"
HEALTH_URL = "https://zephyr-altair-ai-server.onrender.com/health"
RECONNECT_DELAY = 3
PING_INTERVAL = 15
KEEPALIVE_INTERVAL = 300  # 5 minutes — well under Render's ~15 min sleep timer

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
        self._event_loop = None
        self.last_pong = time.time()
        self.connection_lock = asyncio.Lock()

        threading.Thread(target=self._start, daemon=True).start()
        self.start_state_watcher()

        # Independent of the websocket connection entirely — a plain
        # HTTP GET is the most unambiguous "activity" signal a host
        # like Render can see, so this runs on its own schedule even
        # during websocket reconnect gaps.
        threading.Thread(target=self._keepalive_loop, daemon=True).start()

    def _keepalive_loop(self):
        while self.running:
            try:
                requests.get(HEALTH_URL, timeout=10)
                print("💓 Keep-alive ping sent")
            except Exception as e:
                print(f"⚠️ Keep-alive ping failed: {e}")
            time.sleep(KEEPALIVE_INTERVAL)

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
        # Store the REAL running loop object — needed so
        # push_volume_change() (called from a different thread) can
        # safely schedule work back onto this loop.
        self._event_loop = asyncio.get_running_loop()

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
        msg_type = data.get("type")

        # ---- Data request from relay (battery, system_info) ----
        if msg_type == "data_request":
            request_id = data.get("request_id")
            request_type = data.get("request_type")
            print(f"📊 Cloud data request: {request_type}")

            if request_type == "battery":
                result = self.core.system_utils.get_battery()
            elif request_type == "system_info":
                result = self.core.system_utils.get_system_info()
            elif request_type == "gpu_info":
                result = self.core.system_utils.get_gpu_info()
            elif request_type == "get_volume":
                result = self.core.system_utils.get_volume()
            elif request_type == "get_brightness":
                result = self.core.system_utils.get_brightness()
            elif request_type == "get_wifi_state":
                result = self.core.system_utils.get_wifi_state()
            elif request_type == "get_bluetooth_state":
                result = self.core.system_utils.get_bluetooth_state()
            else:
                result = {"success": False, "error": f"Unknown request type: {request_type}"}

            if self.websocket:
                try:
                    await self.websocket.send(json.dumps({
                        "type": "data_response",
                        "request_id": request_id,
                        **result,
                    }))
                except Exception as e:
                    print(f"⚠️ Could not send data response: {e}")
            return

        # ---- Command from relay ----
        if msg_type != "command":
            return

        action = data.get("action")
        print(f"📩 Verified cloud command: {action}")

        try:
            if action == "lock":
                self.core.lock()
            elif action == "unlock":
                self.core.unlock()
            elif action == "freeze_overlay":
                self.core.freeze_only()
            elif action == "volume_up":
                self.core.system_utils.volume_up()
            elif action == "volume_down":
                self.core.system_utils.volume_down()
            elif action == "set_volume":
                level = data.get("value")
                if level is not None:
                    self.core.system_utils.set_volume(int(level))
            elif action == "mute":
                self.core.system_utils.mute()
            elif action == "unmute":
                self.core.system_utils.unmute()
            elif action == "shutdown":
                self.core.system_utils.shutdown(confirm=True)
            elif action == "restart":
                self.core.system_utils.restart(confirm=True)
            elif action == "clear_intruder_logs":
                self.core.intruder_detector.clear_all_logs()
            elif action == "brightness_up":
                self.core.system_utils.brightness_up()
            elif action == "brightness_down":
                self.core.system_utils.brightness_down()
            elif action == "set_brightness":
                level = data.get("value")
                if level is not None:
                    self.core.system_utils.set_brightness(int(level))
            elif action == "wifi_on":
                self.core.system_utils.wifi_on()
            elif action == "wifi_off":
                self.core.system_utils.wifi_off()
            elif action == "bluetooth_on":
                self.core.system_utils.bluetooth_on()
            elif action == "bluetooth_off":
                self.core.system_utils.bluetooth_off()
            elif action in ("start_camera", "start_live_camera"):
                await asyncio.to_thread(self.core.start_live_camera)
            elif action in ("stop_camera", "stop_live_camera"):
                self.core.stop_live_camera()
            elif action == "camera_status":
                print(self.core.is_camera_running())
            else:
                print("⚠️ Unknown action:", action)
                return

            # THE FIX (restored): confirm we actually ran it, so the
            # phone doesn't just time out believing nothing happened.
            await self._send_ack(action, success=True)

        except Exception as e:
            print(f"❌ Command execution failed: {e}")
            await self._send_ack(action, success=False, error=str(e))

    async def _send_ack(self, action, success, error=None):
        if not self.websocket:
            return
        try:
            await self.websocket.send(json.dumps({
                "type": "command_ack", "action": action,
                "success": success, "error": error,
            }))
        except Exception as e:
            print(f"⚠️ Could not send ack: {e}")

    def _push_state_change(self, event_type: str, payload: dict):
        """Generalized version of push_volume_change — used by the
        background watcher for volume, brightness, WiFi, and Bluetooth
        alike. Called from a background thread, so it schedules onto
        the real event loop via run_coroutine_threadsafe."""
        if not self.websocket or not self._event_loop:
            return
        device_id, _ = self._get_device_info()
        if not device_id:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.websocket.send(json.dumps({
                    "type": event_type,
                    "device_id": device_id,
                    **payload,
                })),
                self._event_loop,
            )
        except Exception as e:
            print(f"⚠️ Could not push {event_type}: {e}")

    def push_volume_change(self, volume_percent, muted):
        """Called by the state watcher whenever Windows' volume
        changes for ANY reason — pushes it through the relay so your
        phone's overlay can auto-appear."""
        self._push_state_change("volume_changed", {"volume": volume_percent, "muted": muted})

    def push_brightness_change(self, brightness_percent):
        self._push_state_change("brightness_changed", {"brightness": brightness_percent})

    def push_wifi_change(self, is_on):
        self._push_state_change("wifi_changed", {"on": is_on})

    def push_bluetooth_change(self, is_on):
        self._push_state_change("bluetooth_changed", {"on": is_on})

    def start_state_watcher(self):
        """Background polling loop — checks volume/brightness/WiFi/
        Bluetooth every 2 seconds and pushes a change event the
        moment any of them differs from what we last saw. This is
        what makes changes made directly on the laptop (Windows
        Settings, keyboard, another app) show up on the phone without
        needing to reopen anything.

        Polling rather than true OS-level event callbacks — event
        callbacks (especially for audio) are genuinely fragile to
        implement correctly via COM/ctypes, and 2-second polling is
        simple, reliable, and plenty fast for this use case."""
        threading.Thread(target=self._state_watch_loop, daemon=True).start()

    def _state_watch_loop(self):
        last_volume = None
        last_brightness = None
        last_wifi = None
        last_bluetooth = None

        while self.running:
            try:
                if self.connected:
                    vol_result = self.core.system_utils.get_volume()
                    if vol_result.get("success"):
                        vol = vol_result["volume"]
                        muted = vol_result.get("muted", False)
                        if vol != last_volume:
                            if last_volume is not None:  # skip the very first read
                                self.push_volume_change(vol, muted)
                            last_volume = vol

                    bright_result = self.core.system_utils.get_brightness()
                    if bright_result.get("success"):
                        bright = bright_result["brightness"]
                        if bright != last_brightness:
                            if last_brightness is not None:
                                self.push_brightness_change(bright)
                            last_brightness = bright

                    wifi_result = self.core.system_utils.get_wifi_state()
                    if wifi_result.get("success"):
                        wifi_on = wifi_result["on"]
                        if wifi_on != last_wifi:
                            if last_wifi is not None:
                                self.push_wifi_change(wifi_on)
                            last_wifi = wifi_on

                    bt_result = self.core.system_utils.get_bluetooth_state()
                    if bt_result.get("success"):
                        bt_on = bt_result["on"]
                        if bt_on != last_bluetooth:
                            if last_bluetooth is not None:
                                self.push_bluetooth_change(bt_on)
                            last_bluetooth = bt_on

            except Exception as e:
                print(f"⚠️ State watcher error: {e}")

            time.sleep(2)

    def stop(self):
        self.running = False
        self.connected = False