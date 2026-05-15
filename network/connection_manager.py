# ==============================
# FILE: network/connection_manager.py
# FINAL STABLE HYBRID VERSION
# LOCAL + CLOUD FAILOVER SYSTEM
# ==============================

import time
import threading
import requests


class ConnectionManager:

    def __init__(self):

        # ==============================
        # LOCAL
        # ==============================

        self.local_latency = 999

        self.local_alive = False

        self.LOCAL_URL = (
            "http://127.0.0.1:5001"
        )

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
        # LOCK
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
    # PING LOCAL
    # ==============================

    def _ping_local(self):

        try:

            start = time.time()

            response = requests.get(

                f"{self.LOCAL_URL}/",

                timeout=1
            )

            latency = int(
                (time.time() - start) * 1000
            )

            if response.status_code == 200:

                self.local_latency = latency

                self.local_alive = True

            else:

                self.local_latency = 999

                self.local_alive = False

        except:

            self.local_latency = 999

            self.local_alive = False

    # ==============================
    # UPDATE CLOUD
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
    # BEST CONNECTION
    # ==============================

    def get_best(self):

        with self.lock:

            # ==============================
            # LOCAL PRIORITY
            # ==============================

            if (

                self.local_alive

                and

                self.local_latency < 150

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

                "mode": self.current_mode,

                "local_alive": self.local_alive,

                "local_latency": self.local_latency,

                "cloud_alive": self.cloud_alive,

                "cloud_last_seen": self.cloud_last_seen
            }

    # ==============================
    # MONITOR LOOP
    # ==============================

    def _monitor(self):

        while True:

            try:

                self._ping_local()

                mode = self.get_best()

                print(

                    f"[Connection] "
                    f"Mode={mode} | "
                    f"Local={self.local_alive} "
                    f"({self.local_latency}ms) | "
                    f"Cloud={self.cloud_alive}"

                )

            except Exception as e:

                print(
                    f"[Connection] Monitor Error: {e}"
                )

            time.sleep(3)