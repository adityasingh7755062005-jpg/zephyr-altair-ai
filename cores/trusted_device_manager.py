# cores/trusted_device_manager.py
# HARDENED — atomic writes, owner-only permissions (same pattern as Core 14/15)

import json
import os
import stat
import shutil


class TrustedDeviceManager:
    def __init__(self, path="data/trusted_device.json"):
        self.path = path
        self.backup_path = path + ".bak"
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._restrict_permissions(os.path.dirname(self.path))

    def load(self):
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[TrustedDevice] Primary file unreadable ({e}), trying backup")
            if os.path.exists(self.backup_path):
                try:
                    with open(self.backup_path, "r") as f:
                        return json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass
            return None

    def save(self, data: dict):
        tmp_path = self.path + ".tmp"
        try:
            if os.path.exists(self.path):
                shutil.copy2(self.path, self.backup_path)
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=4)
            os.replace(tmp_path, self.path)
            self._restrict_permissions_file(self.path)
        except OSError as e:
            print(f"[TrustedDevice] Save failed: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def clear(self):
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except OSError as e:
            print(f"[TrustedDevice] Clear failed: {e}")

    def _restrict_permissions(self, path):
        try:
            os.chmod(path, stat.S_IRWXU)
        except (PermissionError, NotImplementedError, OSError):
            pass

    def _restrict_permissions_file(self, path):
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except (PermissionError, NotImplementedError, OSError):
            pass