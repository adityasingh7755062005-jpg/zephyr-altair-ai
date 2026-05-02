# ==============================
# FILE: network/connection_manager.py (CLEAN SWITCHER ONLY)
# ==============================

import time
import threading
import requests


class ConnectionManager:
    """
    🧠 ONLY decides:
    LOCAL vs CLOUD
    """

    def __init__(self):
        self.local_latency = 999
        self.cloud_alive = False

        self.LOCAL_URL = "http://127.0.0.1:5001"

        threading.Thread(target=self._monitor, daemon=True).start()

    # ==========================
    # LOCAL CHECK
    # ==========================
    def _ping_local(self):
        try:
            start = time.time()
            requests.get(f"{self.LOCAL_URL}/", timeout=1)
            self.local_latency = int((time.time() - start) * 1000)
        except:
            self.local_latency = 999

    # ==========================
    # CLOUD STATUS UPDATE
    # ==========================
    def update_cloud(self, status: bool):
        self.cloud_alive = status

    # ==========================
    # DECISION
    # ==========================
    def get_best(self):
        if self.local_latency < 150:
            return "LOCAL"
        if self.cloud_alive:
            return "CLOUD"
        return "OFFLINE"

    # ==========================
    # MONITOR LOOP
    # ==========================
    def _monitor(self):
        while True:
            self._ping_local()

            print(
                f"[Connection] LOCAL={self.local_latency}ms | CLOUD={self.cloud_alive}"
            )

            time.sleep(3)