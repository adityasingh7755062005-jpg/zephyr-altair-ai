# ==============================
# FILE: network/local_server.py (SECURE - TOKEN VERIFIED)
# ==============================

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import threading
import time
import logging
import hashlib

# 🔥 CLEAN LOGS
logging.getLogger("uvicorn.access").disabled = True

HOST = "0.0.0.0"
PORT = 5001

DEVICE_ID = "160c02a2018e7132"
SECRET_KEY = "c63bd8f574f9634e3f50bda3fd5cce15"
MAX_TIME_DIFF = 300  # 5 minutes


class LocalServer:

    def __init__(self, core):
        self.core = core
        self.app = FastAPI()
        self._setup_routes()

    # ==============================
    # TOKEN GENERATION (same as cloud)
    # ==============================
    def _generate_token(self, action, timestamp):
        raw = f"{DEVICE_ID}{SECRET_KEY}{timestamp}{action}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ==============================
    # VALIDATION
    # ==============================
    def _validate(self, action, timestamp, token):

        print(f"📩 Command received: {action}")
        print(f"🕒 timestamp: {timestamp}")
        print(f"🔑 token: {token}")

        # ❌ Missing
        if not action or not timestamp or not token:
            print("❌ Missing security data")
            return False, "Missing security data"

        # ❌ Expired
        if abs(int(time.time()) - int(timestamp)) > MAX_TIME_DIFF:
            print("❌ Request expired")
            return False, "Expired request"

        # ❌ Invalid token
        expected = self._generate_token(action, int(timestamp))
        if token != expected:
            print("❌ Invalid token")
            return False, "Invalid token"

        print("✅ Request verified")
        return True, None

    # ==============================
    # ROUTES
    # ==============================
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
                data = await request.json() if request.method == "POST" else request.query_params

                timestamp = int(data.get("timestamp", 0))
                token = data.get("token")

                valid, error = self._validate("lock", timestamp, token)

                if not valid:
                    return JSONResponse(status_code=403, content={"error": error})

                print("[Control] 🔒 Lock command received")
                self.core.lock()

                return {"status": "locked"}

            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})

        # 🔓 UNLOCK
        @self.app.api_route("/unlock", methods=["GET", "POST"])
        async def unlock(request: Request):

            try:
                data = await request.json() if request.method == "POST" else request.query_params

                timestamp = int(data.get("timestamp", 0))
                token = data.get("token")

                valid, error = self._validate("unlock", timestamp, token)

                if not valid:
                    return JSONResponse(status_code=403, content={"error": error})

                print("[Control] 🔓 Unlock command received")
                self.core.unlock()

                return {"status": "unlocked"}

            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})

    # ==============================
    # START
    # ==============================
    def start(self):
        import uvicorn

        print(f"[LocalServer] Running on {HOST}:{PORT}")
        print(f"📱 Device ID: {DEVICE_ID}")

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