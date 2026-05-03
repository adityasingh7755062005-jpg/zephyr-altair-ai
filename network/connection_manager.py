# ==============================
# FILE: network/connection_manager.py (CLEAN)
# ==============================

import time
import threading
import requests


class ConnectionManager:

    def __init__(self):
        self.local_latency = 999
        self.cloud_alive = False
        self.LOCAL_URL = "http://127.0.0.1:5001"

        threading.Thread(target=self._monitor, daemon=True).start()

    def _ping_local(self):
        try:
            start = time.time()
            requests.get(f"{self.LOCAL_URL}/", timeout=1)
            self.local_latency = int((time.time() - start) * 1000)
        except:
            self.local_latency = 999

    def update_cloud(self, status: bool):
        self.cloud_alive = status

    def get_best(self):
        if self.local_latency < 150:
            return "LOCAL"
        if self.cloud_alive:
            return "CLOUD"
        return "OFFLINE"

    def _monitor(self):
        while True:
            self._ping_local()
            time.sleep(3)