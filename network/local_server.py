# network/local_server.py
# Merged: real per-device secret verification (from the security
# rebuild) + your new intruder logs endpoint, plus a real delete route.

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import threading
import asyncio
import time
import os
import logging
import socket

from network.security import verify_request

logging.getLogger("uvicorn.access").disabled = True

HOST = "0.0.0.0"
PORT = 5001


class LocalServer:
    def __init__(self, core):
        self.core = core
        self.app = FastAPI()
        os.makedirs("intruders", exist_ok=True)
        self.app.mount("/intruders", StaticFiles(directory="intruders"), name="intruders")
        self._setup_routes()

    # ==============================
    # VERIFY — real per-device secret, not a hardcoded string
    # ==============================
    def verify(self, params):
        try:
            device_id = params.get("device")
            trusted = self.core.trusted_device_manager.load()

            if not trusted or trusted.get("device_id") != device_id:
                return False, "untrusted device"

            secret = bytes.fromhex(trusted["secret_key"])
            return verify_request(
                params.get("cmd"), params.get("ts"), device_id,
                params.get("sig"), params.get("nonce"), secret,
            )
        except Exception as e:
            return False, str(e)

    def _setup_routes(self):
        @self.app.get("/")
        async def home():
            return {"status": "Zephyr Local Server Running",
                    "camera_running": self.core.is_camera_running(), "time": int(time.time())}

        @self.app.get("/ping")
        async def ping():
            return {"status": "alive", "camera_running": self.core.is_camera_running(), "time": int(time.time())}

        # ---- PAIRING (was missing entirely from the last version you sent) ----
        @self.app.post("/pair/start")
        async def pair_start():
            self.core.pairing_manager.start_pairing()
            return {"status": "pairing_started", "message": "Enter the PIN shown on the laptop"}

        @self.app.post("/pair/confirm")
        async def pair_confirm(request: Request):
            body = await request.json()
            result = self.core.pairing_manager.confirm_pairing(
                body.get("pin", ""), body.get("device_name", "Unknown Device")
            )
            if not result["success"]:
                return JSONResponse(status_code=403, content={"error": result["error"]})
            return {"status": "paired", "device_id": result["device_id"], "secret_key": result["secret_key"]}

        # ---- LOCK / UNLOCK ----
        @self.app.api_route("/lock", methods=["GET", "POST"])
        async def lock(request: Request):
            return await self._guarded(dict(request.query_params), self.core.lock, "locked")

        @self.app.api_route("/unlock", methods=["GET", "POST"])
        async def unlock(request: Request):
            return await self._guarded(dict(request.query_params), self.core.unlock, "unlocked")

        # ---- CAMERA ----
        @self.app.api_route("/start_camera", methods=["GET", "POST"])
        async def start_camera(request: Request):
            params = dict(request.query_params)
            valid, msg = self.verify(params)
            if not valid:
                return JSONResponse(status_code=403, content={"error": msg})
            # FIXED: start_live_camera() blocks for ~2s (time.sleep).
            # Running it directly here froze the ENTIRE local server —
            # every other request (lock, unlock, ping) — for that
            # whole window. Running it in a thread keeps the event
            # loop free.
            result = await asyncio.to_thread(self.core.start_live_camera)
            return {"status": "camera_started", "running": result}

        @self.app.api_route("/stop_camera", methods=["GET", "POST"])
        async def stop_camera(request: Request):
            params = dict(request.query_params)
            valid, msg = self.verify(params)
            if not valid:
                return JSONResponse(status_code=403, content={"error": msg})
            # FIXED: stop_live_camera() can block up to 5s (subprocess.wait)
            await asyncio.to_thread(self.core.stop_live_camera)
            return {"status": "camera_stopped"}

        # ---- FREEZE OVERLAY (standalone — does NOT lock Windows) ----
        @self.app.api_route("/freeze_overlay", methods=["GET", "POST"])
        async def freeze_overlay(request: Request):
            return await self._guarded(dict(request.query_params), self.core.freeze_only, "freeze_only_armed")

        @self.app.api_route("/camera_status", methods=["GET", "POST"])
        async def camera_status(request: Request):
            params = dict(request.query_params)
            valid, msg = self.verify(params)
            if not valid:
                return JSONResponse(status_code=403, content={"error": msg})
            return {"camera_running": self.core.is_camera_running()}

        # ---- INTRUDER LOGS (your addition, now signature-gated) ----
        @self.app.api_route("/intruder_logs", methods=["GET", "POST"])
        async def intruder_logs(request: Request):
            params = dict(request.query_params)
            valid, msg = self.verify(params)
            if not valid:
                return JSONResponse(status_code=403, content={"error": msg})

            entries = self.core.intruder_detector.get_local_log()
            local_ip = self.get_local_ip()
            for entry in entries:
                entry["image_url"] = f"http://{local_ip}:{PORT}/intruders/{entry['filename']}"
            return {"status": "ok", "entries": entries}

        # ---- REAL DELETE — for "kept until I delete it" ----
        @self.app.api_route("/delete_intruder", methods=["GET", "POST"])
        async def delete_intruder(request: Request):
            params = dict(request.query_params)
            valid, msg = self.verify(params)
            if not valid:
                return JSONResponse(status_code=403, content={"error": msg})

            filename = params.get("filename")
            if not filename:
                return JSONResponse(status_code=400, content={"error": "filename required"})

            deleted = self.core.intruder_detector.delete_capture(filename)
            return {"status": "ok" if deleted else "not_found", "filename": filename}

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