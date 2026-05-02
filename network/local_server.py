# ==============================
# FILE: network/local_server.py
# ==============================

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import threading
import time

# ==============================
# CONFIG
# ==============================
HOST = "0.0.0.0"
PORT = 5001

# ==============================
# MAIN SERVER CLASS
# ==============================
class LocalServer:
    """
    🔥 Pure LOCAL server
    - Handles only local network requests
    - No cloud logic
    """

    def __init__(self, core):
        self.core = core
        self.app = FastAPI()

        self._setup_routes()

    # ==============================
    # ROUTES
    # ==============================
    def _setup_routes(self):

        # 🔥 HEALTH CHECK (VERY IMPORTANT)
        @self.app.get("/")
        async def home():
            return {"status": "Zephyr Local Server Running 🚀"}

        @self.app.get("/ping")
        async def ping():
            return {
                "status": "alive",
                "time": int(time.time())
            }

        # 🔒 LOCK
        @self.app.post("/lock")
        async def lock(request: Request):
            print("📥 LOCAL LOCK REQUEST")

            try:
                self.core.lock()
                return {"status": "locked"}
            except Exception as e:
                print("❌ Lock error:", e)
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e)}
                )

        # 🔓 UNLOCK
        @self.app.post("/unlock")
        async def unlock(request: Request):
            print("📥 LOCAL UNLOCK REQUEST")

            try:
                self.core.unlock()
                return {"status": "unlocked"}
            except Exception as e:
                print("❌ Unlock error:", e)
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e)}
                )

    # ==============================
    # START SERVER
    # ==============================
    def start(self):
        import uvicorn

        print(f"[LocalServer] 🚀 Running on {HOST}:{PORT}")

        uvicorn.run(
            self.app,
            host=HOST,
            port=PORT,
            log_level="info"
        )


# ==============================
# THREAD START HELPER
# ==============================
def start_local_server(core):
    server = LocalServer(core)

    threading.Thread(
        target=server.start,
        daemon=True
    ).start()