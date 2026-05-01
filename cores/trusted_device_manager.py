# ==============================
# FILE 3: trusted_device_manager.py
# ==============================

import json
import os


class TrustedDeviceManager:

    def __init__(self, path="data/trusted_device.json"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def load(self):
        try:
            if not os.path.exists(self.path):
                return None

            with open(self.path, "r") as f:
                return json.load(f)

        except Exception as e:
            print("[ERROR] Load failed:", e)
            return None

    def save(self, data: dict):
        try:
            with open(self.path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print("[ERROR] Save failed:", e)

    def clear(self):
        if os.path.exists(self.path):
            os.remove(self.path)