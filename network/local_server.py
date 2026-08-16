# network/local_server.py
# HARDENED — real /pair endpoint, real per-device secret verification

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import threading, time, logging, socket

from network.security import verify_request

logging.getLogger("uvicorn.access").disabled = True

HOST = "0.0.0.0"
PORT = 5001


class LocalServer:
    def __init__(self, core):
        self.core = core  # gives access to core.trusted_device_manager, core.pairing_manager
        self.app = FastAPI()
        self._setup_routes()

    def verify(self, params):
        """Now looks up the REAL paired device's secret instead of
        checking against a hardcoded ID/secret pair."""
        try:
            device_id = params.get("device")
            trusted = self.core.trusted_device_manager.load()

            if not trusted or trusted.get("device_id") != device_id:
                return False, "untrusted device"

            secret = bytes.fromhex(trusted["secret_key"])

            valid, msg = verify_request(
                params.get("cmd"), params.get("ts"), device_id,
                params.get("sig"), params.get("nonce"), secret,
            )
            return valid, msg
        except Exception as e:
            return False, str(e)

    def _setup_routes(self):
        @self.app.get("/")
        async def home():
            return {"status": "Zephyr Local Server Running",
                    "camera_running": self.core.is_camera_running(),
                    "time": int(time.time())}

        @self.app.get("/ping")
        async def ping():
            return {"status": "alive", "time": int(time.time())}

        # ---- NEW: real pairing endpoints ----
        @self.app.post("/pair/start")
        async def pair_start():
            """Call this LOCALLY (e.g. via a voice command or hotkey on
            the laptop itself) to begin pairing. Shows a PIN on the
            laptop's own console — nothing is exposed over network here."""
            pin = self.core.pairing_manager.start_pairing()
            return {"status": "pairing_started", "message": "Enter the PIN shown on the laptop"}

        @self.app.post("/pair/confirm")
        async def pair_confirm(request: Request):
            """Phone app calls this over the LOCAL network with the PIN
            the owner read off the laptop screen and typed into the app."""
            body = await request.json()
            pin = body.get("pin", "")
            device_name = body.get("device_name", "Unknown Device")

            result = self.core.pairing_manager.confirm_pairing(pin, device_name)

            if not result["success"]:
                return JSONResponse(status_code=403, content={"error": result["error"]})

            # Secret is transmitted exactly once, here, over the local
            # network only — never over the cloud/internet path.
            return {"status": "paired", "device_id": result["device_id"], "secret_key": result["secret_key"]}

        @self.app.api_route("/lock", methods=["GET", "POST"])
        async def lock(request: Request):
            return await self._guarded(dict(request.query_params), self.core.lock, "locked")

        @self.app.api_route("/unlock", methods=["GET", "POST"])
        async def unlock(request: Request):
            return await self._guarded(dict(request.query_params), self.core.unlock, "unlocked")

        @self.app.api_route("/start_camera", methods=["GET", "POST"])
        async def start_camera(request: Request):
            params = dict(request.query_params)
            valid, msg = self.verify(params)
            if not valid:
                return JSONResponse(status_code=403, content={"error": msg})
            result = self.core.start_live_camera()
            return {"status": "camera_started", "running": result}

        @self.app.api_route("/stop_camera", methods=["GET", "POST"])
        async def stop_camera(request: Request):
            params = dict(request.query_params)
            valid, msg = self.verify(params)
            if not valid:
                return JSONResponse(status_code=403, content={"error": msg})
            self.core.stop_live_camera()
            return {"status": "camera_stopped"}

        @self.app.api_route("/camera_status", methods=["GET", "POST"])
        async def camera_status(request: Request):
            params = dict(request.query_params)
            valid, msg = self.verify(params)
            if not valid:
                return JSONResponse(status_code=403, content={"error": msg})
            return {"camera_running": self.core.is_camera_running()}

    async def _guarded(self, params, action_fn, success_status):
        valid, msg = self.verify(params)
        if not valid:
            print(f"❌ REJECTED: {msg}")
            return JSONResponse(status_code=403, content={"error": msg})
        action_fn()
        return {"status": success_status}

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"
        finally:
            s.close()

    def start(self):
        import uvicorn
        print(f"🌐 Zephyr Local Server: http://{self.get_local_ip()}:{PORT}")
        uvicorn.run(self.app, host=HOST, port=PORT, log_level="error", access_log=False)


def start_local_server(core):
    server = LocalServer(core)
    threading.Thread(target=server.start, daemon=True).start()