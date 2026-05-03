# ==============================
# FILE: network/local_server.py (CLEAN - NO TOKEN + IP PRINT)
# ==============================

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import threading
import time
import logging

# 🔥 CLEAN LOGS
logging.getLogger("uvicorn.access").disabled = True

HOST = "0.0.0.0"
PORT = 5001


class LocalServer:

    def __init__(self, core):
        self.core = core
        self.app = FastAPI()
        self._setup_routes()

    def _setup_routes(self):

        @self.app.get("/")
        async def home():
            return {"status": "Zephyr Local Server Running"}

        @self.app.get("/ping")
        async def ping():
            return {"status": "alive", "time": int(time.time())}

        # 🔒 LOCK
        @self.app.api_route("/lock", methods=["GET", "POST"])
        async def lock(request: Request):
            try:
                print("📥 LOCAL LOCK")
                self.core.lock()
                return {"status": "locked"}
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})

        # 🔓 UNLOCK
        @self.app.api_route("/unlock", methods=["GET", "POST"])
        async def unlock(request: Request):
            try:
                print("📥 LOCAL UNLOCK")
                self.core.unlock()
                return {"status": "unlocked"}
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})

    def start(self):
        import uvicorn
        import socket

        # 🔥 Get correct local IP (works reliably)
        def get_local_ip():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            except:
                ip = "Unable to detect"
            finally:
                s.close()
            return ip

        local_ip = get_local_ip()

        print(f"[LocalServer] Running on {HOST}:{PORT}")
        print(f"🌐 Access from phone: http://{local_ip}:{PORT}")

        uvicorn.run(
            self.app,
            host=HOST,
            port=PORT,
            log_level="error"
        )


def start_local_server(core):
    server = LocalServer(core)

    threading.Thread(
        target=server.start,
        daemon=True
    ).start()