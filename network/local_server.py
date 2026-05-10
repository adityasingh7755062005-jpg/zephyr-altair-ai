# ==============================
# FILE: network/local_server.py
# FULL CAMERA CONTROL VERSION
# ==============================

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import threading
import time
import logging

from network.security import verify_request

logging.getLogger(
    "uvicorn.access"
).disabled = True

HOST = "0.0.0.0"
PORT = 5001

# ==============================
# TRUSTED DEVICE
# ==============================

TRUSTED_DEVICE_ID = "160c02a2018e7132"


class LocalServer:

    def __init__(self, core):

        self.core = core

        self.app = FastAPI()

        self._setup_routes()

    # ==============================
    # TRUST CHECK
    # ==============================

    def is_trusted_device(
        self,
        device_id
    ):

        return (
            device_id ==
            TRUSTED_DEVICE_ID
        )

    # ==============================
    # ROUTES
    # ==============================

    def _setup_routes(self):

        # ==============================
        # HOME
        # ==============================

        @self.app.get("/")
        async def home():

            return {

                "status":
                "Zephyr Local Server Running"
            }

        # ==============================
        # PING
        # ==============================

        @self.app.get("/ping")
        async def ping():

            return {

                "status": "alive",

                "time": int(time.time())
            }

        # ==============================
        # LOCK
        # ==============================

        @self.app.api_route(
            "/lock",
            methods=["GET", "POST"]
        )
        async def lock(
            request: Request
        ):

            try:

                params = dict(
                    request.query_params
                )

                device_id = params.get(
                    "device"
                )

                # ==============================
                # TRUST CHECK
                # ==============================

                if not self.is_trusted_device(
                    device_id
                ):

                    print(
                        "❌ Untrusted Device"
                    )

                    return JSONResponse(

                        status_code=403,

                        content={
                            "error":
                            "untrusted device"
                        }
                    )

                valid, msg = verify_request(

                    params.get("cmd"),

                    params.get("ts"),

                    device_id,

                    params.get("sig"),

                    params.get("nonce")
                )

                if not valid:

                    print(
                        f"❌ REJECTED LOCK: {msg}"
                    )

                    return JSONResponse(

                        status_code=403,

                        content={
                            "error": msg
                        }
                    )

                print(
                    "📥 LOCAL LOCK (VALID)"
                )

                self.core.lock()

                return {
                    "status": "locked"
                }

            except Exception as e:

                return JSONResponse(

                    status_code=500,

                    content={
                        "error": str(e)
                    }
                )

        # ==============================
        # UNLOCK
        # ==============================

        @self.app.api_route(
            "/unlock",
            methods=["GET", "POST"]
        )
        async def unlock(
            request: Request
        ):

            try:

                params = dict(
                    request.query_params
                )

                device_id = params.get(
                    "device"
                )

                # ==============================
                # TRUST CHECK
                # ==============================

                if not self.is_trusted_device(
                    device_id
                ):

                    print(
                        "❌ Untrusted Device"
                    )

                    return JSONResponse(

                        status_code=403,

                        content={
                            "error":
                            "untrusted device"
                        }
                    )

                valid, msg = verify_request(

                    params.get("cmd"),

                    params.get("ts"),

                    device_id,

                    params.get("sig"),

                    params.get("nonce")
                )

                if not valid:

                    print(
                        f"❌ REJECTED UNLOCK: {msg}"
                    )

                    return JSONResponse(

                        status_code=403,

                        content={
                            "error": msg
                        }
                    )

                print(
                    "📥 LOCAL UNLOCK (VALID)"
                )

                self.core.unlock()

                return {
                    "status": "unlocked"
                }

            except Exception as e:

                return JSONResponse(

                    status_code=500,

                    content={
                        "error": str(e)
                    }
                )

        # ==============================
        # START LIVE CAMERA
        # ==============================

        @self.app.api_route(
            "/start_live_camera",
            methods=["GET", "POST"]
        )
        async def start_live_camera(
            request: Request
        ):

            try:

                params = dict(
                    request.query_params
                )

                device_id = params.get(
                    "device"
                )

                # ==============================
                # TRUST CHECK
                # ==============================

                if not self.is_trusted_device(
                    device_id
                ):

                    print(
                        "❌ Untrusted Camera Start"
                    )

                    return JSONResponse(

                        status_code=403,

                        content={
                            "error":
                            "untrusted device"
                        }
                    )

                valid, msg = verify_request(

                    params.get("cmd"),

                    params.get("ts"),

                    device_id,

                    params.get("sig"),

                    params.get("nonce")
                )

                if not valid:

                    print(
                        f"❌ CAMERA START REJECTED: "
                        f"{msg}"
                    )

                    return JSONResponse(

                        status_code=403,

                        content={
                            "error": msg
                        }
                    )

                print(
                    "📷 START CAMERA REQUEST"
                )

                result = (
                    self.core
                    .start_live_camera()
                )

                return {

                    "status":
                    "camera_started",

                    "running":
                    result
                }

            except Exception as e:

                return JSONResponse(

                    status_code=500,

                    content={
                        "error": str(e)
                    }
                )

        # ==============================
        # STOP LIVE CAMERA
        # ==============================

        @self.app.api_route(
            "/stop_live_camera",
            methods=["GET", "POST"]
        )
        async def stop_live_camera(
            request: Request
        ):

            try:

                params = dict(
                    request.query_params
                )

                device_id = params.get(
                    "device"
                )

                # ==============================
                # TRUST CHECK
                # ==============================

                if not self.is_trusted_device(
                    device_id
                ):

                    print(
                        "❌ Untrusted Camera Stop"
                    )

                    return JSONResponse(

                        status_code=403,

                        content={
                            "error":
                            "untrusted device"
                        }
                    )

                valid, msg = verify_request(

                    params.get("cmd"),

                    params.get("ts"),

                    device_id,

                    params.get("sig"),

                    params.get("nonce")
                )

                if not valid:

                    print(
                        f"❌ CAMERA STOP REJECTED: "
                        f"{msg}"
                    )

                    return JSONResponse(

                        status_code=403,

                        content={
                            "error": msg
                        }
                    )

                print(
                    "🛑 STOP CAMERA REQUEST"
                )

                self.core.stop_live_camera()

                return {

                    "status":
                    "camera_stopped"
                }

            except Exception as e:

                return JSONResponse(

                    status_code=500,

                    content={
                        "error": str(e)
                    }
                )

        # ==============================
        # CAMERA STATUS
        # ==============================

        @self.app.api_route(
            "/camera_status",
            methods=["GET", "POST"]
        )
        async def camera_status(
            request: Request
        ):

            try:

                params = dict(
                    request.query_params
                )

                device_id = params.get(
                    "device"
                )

                # ==============================
                # TRUST CHECK
                # ==============================

                if not self.is_trusted_device(
                    device_id
                ):

                    return JSONResponse(

                        status_code=403,

                        content={
                            "error":
                            "untrusted device"
                        }
                    )

                valid, msg = verify_request(

                    params.get("cmd"),

                    params.get("ts"),

                    device_id,

                    params.get("sig"),

                    params.get("nonce")
                )

                if not valid:

                    return JSONResponse(

                        status_code=403,

                        content={
                            "error": msg
                        }
                    )

                running = (
                    self.core
                    .is_camera_running()
                )

                return {

                    "camera_running":
                    running
                }

            except Exception as e:

                return JSONResponse(

                    status_code=500,

                    content={
                        "error": str(e)
                    }
                )

    # ==============================
    # START SERVER
    # ==============================

    def start(self):

        import uvicorn
        import socket

        def get_local_ip():

            s = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )

            try:

                s.connect(
                    ("8.8.8.8", 80)
                )

                ip = s.getsockname()[0]

            except:

                ip = "Unable to detect"

            finally:

                s.close()

            return ip

        local_ip = get_local_ip()

        print(
            f"[LocalServer] Running on "
            f"{HOST}:{PORT}"
        )

        print(
            f"🌐 Access from phone: "
            f"http://{local_ip}:{PORT}"
        )

        uvicorn.run(

            self.app,

            host=HOST,

            port=PORT,

            log_level="error"
        )


# ==============================
# START LOCAL SERVER
# ==============================

def start_local_server(core):

    server = LocalServer(core)

    threading.Thread(

        target=server.start,

        daemon=True

    ).start()