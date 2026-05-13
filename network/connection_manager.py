# ==============================
# FILE: network/connection_manager.py
# FINAL ULTRA STABLE HYBRID VERSION
# FIXED NETWORK SWITCHING
# FIXED CLOUD FAILOVER
# FIXED RANDOM OFFLINE BUG
# LOW LOG VERSION
# ==============================

import time
import threading
import requests

# ==============================
# SETTINGS
# ==============================

LOCAL_TIMEOUT = 2

LOCAL_MAX_LATENCY = 300

MONITOR_INTERVAL = 5

SHOW_LOGS = False

# ==============================
# CONNECTION MANAGER
# ==============================

class ConnectionManager:

    def __init__(self):

        # ==============================
        # LOCAL
        # ==============================

        self.LOCAL_URL = (
            "http://127.0.0.1:5001"
        )

        self.local_latency = 999

        self.local_alive = False

        self.last_local_success = 0

        # ==============================
        # CLOUD
        # ==============================

        self.cloud_alive = False

        self.cloud_last_seen = 0

        # ==============================
        # CURRENT MODE
        # ==============================

        self.current_mode = "OFFLINE"

        # ==============================
        # THREAD LOCK
        # ==============================

        self.lock = threading.Lock()

        # ==============================
        # START MONITOR
        # ==============================

        threading.Thread(

            target=self._monitor,

            daemon=True

        ).start()

    # ==============================
    # PING LOCAL SERVER
    # ==============================

    def _ping_local(self):

        try:

            start = time.time()

            response = requests.get(

                f"{self.LOCAL_URL}/ping",

                timeout=LOCAL_TIMEOUT
            )

            latency = int(

                (time.time() - start)

                * 1000
            )

            if response.status_code == 200:

                with self.lock:

                    self.local_latency = latency

                    self.local_alive = True

                    self.last_local_success = (
                        time.time()
                    )

            else:

                with self.lock:

                    self.local_latency = 999

                    self.local_alive = False

        except:

            with self.lock:

                self.local_latency = 999

                self.local_alive = False

    # ==============================
    # UPDATE CLOUD STATUS
    # ==============================

    def update_cloud(
        self,
        status: bool
    ):

        with self.lock:

            self.cloud_alive = status

            if status:

                self.cloud_last_seen = (
                    time.time()
                )

    # ==============================
    # GET BEST CONNECTION
    # ==============================

    def get_best(self):

        with self.lock:

            # ==============================
            # LOCAL PRIORITY
            # ==============================

            if (

                self.local_alive

                and

                self.local_latency
                <= LOCAL_MAX_LATENCY

            ):

                self.current_mode = "LOCAL"

                return "LOCAL"

            # ==============================
            # CLOUD FALLBACK
            # ==============================

            if self.cloud_alive:

                self.current_mode = "CLOUD"

                return "CLOUD"

            # ==============================
            # OFFLINE
            # ==============================

            self.current_mode = "OFFLINE"

            return "OFFLINE"

    # ==============================
    # GET STATUS
    # ==============================

    def get_status(self):

        with self.lock:

            return {

                "mode":
                self.current_mode,

                "local_alive":
                self.local_alive,

                "local_latency":
                self.local_latency,

                "cloud_alive":
                self.cloud_alive,

                "cloud_last_seen":
                self.cloud_last_seen,

                "last_local_success":
                self.last_local_success
            }

    # ==============================
    # MONITOR LOOP
    # ==============================

    def _monitor(self):

        previous_mode = None

        while True:

            try:

                # ==============================
                # CHECK LOCAL
                # ==============================

                self._ping_local()

                # ==============================
                # GET BEST MODE
                # ==============================

                mode = self.get_best()

                # ==============================
                # LOG ONLY ON CHANGE
                # ==============================

                if (

                    SHOW_LOGS

                    and

                    mode != previous_mode
                ):

                    print(

                        f"[Connection] "
                        f"Mode={mode} | "
                        f"Local={self.local_alive} "
                        f"({self.local_latency}ms) | "
                        f"Cloud={self.cloud_alive}"

                    )

                    previous_mode = mode

            except Exception as e:

                print(
                    f"[Connection] "
                    f"Monitor Error: {e}"
                )

            time.sleep(
                MONITOR_INTERVAL
            )