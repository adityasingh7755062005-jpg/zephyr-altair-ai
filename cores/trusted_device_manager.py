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
            print("[ERROR] Failed to load trusted device:", e)
            return None

    def save(self, device_info: dict):
        try:
            with open(self.path, "w") as f:
                json.dump(device_info, f, indent=4)
        except Exception as e:
            print("[ERROR] Failed to save trusted device:", e)

    def clear(self):
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except Exception as e:
            print("[ERROR] Failed to clear trusted device:", e)