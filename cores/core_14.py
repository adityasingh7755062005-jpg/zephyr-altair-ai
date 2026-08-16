# cores/core_14.py
# Core 14 – Long-Term Memory — Hardened

import json
import os
import stat
import shutil
import threading
from datetime import datetime


class Core14LongTermMemory:
    """
    Phase 2 – Core 14 (Hardened)
    -------------------------------
    Long-term persistent memory.

    Fixes vs original:
    - Atomic writes (temp file + rename) so a crash mid-save can't
      corrupt the real memory file
    - Keeps one rolling backup of the last known-good file
    - Restricts file/folder permissions to owner-only (matches Core 1)
    - Narrower error handling with real logging instead of a silent
      catch-all that could mask real bugs
    - Thread-safe (lock around read/modify/write)
    - get_all() returns a copy, not a live reference
    """

    def __init__(self, memory_path: str = "data/memory/long_term_memory.json"):
        self.memory_path = memory_path
        self.backup_path = memory_path + ".bak"
        self._lock = threading.Lock()

        os.makedirs(os.path.dirname(memory_path), exist_ok=True)
        self._restrict_permissions(os.path.dirname(memory_path))

        self.memory = self._default_memory()
        self._load()

        print("[Core 14] Long-term memory initialized (Hardened)")

    # --------------------------------------------------
    # Defaults
    # --------------------------------------------------
    def _default_memory(self) -> dict:
        return {
            "meta": {
                "created": datetime.now().isoformat(),
                "last_updated": None,
            },
            "preferences": {},
            "habits": {},
            "facts": {},
            "stats": {
                "intent_counts": {}
            },
        }

    # --------------------------------------------------
    # Load & Save
    # --------------------------------------------------
    def _load(self):
        if not os.path.exists(self.memory_path):
            return

        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                self.memory = json.load(f)
            return
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Core 14] WARNING: Memory file unreadable ({e}). Trying backup...")

        # ---- Primary file failed — try the backup before giving up ----
        if os.path.exists(self.backup_path):
            try:
                with open(self.backup_path, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
                print("[Core 14] Recovered memory from backup file")
                return
            except (json.JSONDecodeError, OSError) as e:
                print(f"[Core 14] WARNING: Backup also unreadable ({e}).")

        print("[Core 14] No usable memory file found — starting fresh")
        self.memory = self._default_memory()

    def _save(self):
        """Atomic write: write to a temp file, then rename into place.
        Also rotates a backup of the previous good version first."""
        self.memory["meta"]["last_updated"] = datetime.now().isoformat()

        tmp_path = self.memory_path + ".tmp"

        try:
            # Back up the current good file before overwriting it
            if os.path.exists(self.memory_path):
                shutil.copy2(self.memory_path, self.backup_path)

            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2, ensure_ascii=False)

            os.replace(tmp_path, self.memory_path)  # atomic on POSIX and Windows
            self._restrict_permissions_file(self.memory_path)

        except OSError as e:
            print(f"[Core 14] ERROR: Failed to save memory: {e}")
            # Clean up a partial temp file if it exists
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # --------------------------------------------------
    # Automatic learning (SAFE)
    # --------------------------------------------------
    def auto_update(self, packet: dict):
        """Learns safe patterns automatically. Called every successful interaction."""
        with self._lock:
            intent = packet.get("intent")
            language = packet.get("language")

            if intent:
                self.memory["stats"]["intent_counts"].setdefault(intent, 0)
                self.memory["stats"]["intent_counts"][intent] += 1

            if language:
                self.memory["preferences"]["language"] = language

            self._save()

    # --------------------------------------------------
    # Explicit memory command
    # --------------------------------------------------
    def remember(self, key: str, value: str):
        """Stores user-approved memory explicitly."""
        if not key or not isinstance(key, str):
            print("[Core 14] Skipped remember() — invalid key")
            return

        with self._lock:
            self.memory["facts"][key] = {
                "value": value,
                "timestamp": datetime.now().isoformat(),
            }
            self._save()

        print(f"[Core 14] Explicit memory stored: {key}")

    def forget(self, key: str) -> bool:
        """Removes an explicitly remembered fact."""
        with self._lock:
            if key in self.memory["facts"]:
                del self.memory["facts"][key]
                self._save()
                print(f"[Core 14] Forgot: {key}")
                return True
        return False

    # --------------------------------------------------
    # Retrieval
    # --------------------------------------------------
    def recall(self, key: str):
        with self._lock:
            return self.memory["facts"].get(key)

    def get_all(self) -> dict:
        """Returns a COPY of memory — mutating this won't affect stored state."""
        with self._lock:
            return json.loads(json.dumps(self.memory))  # cheap deep copy

    # --------------------------------------------------
    # Permission hardening (matches Core 1's pattern)
    # --------------------------------------------------
    def _restrict_permissions(self, path: str):
        try:
            os.chmod(path, stat.S_IRWXU)  # 0o700 — owner only
        except (PermissionError, NotImplementedError, OSError):
            pass

    def _restrict_permissions_file(self, path: str):
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except (PermissionError, NotImplementedError, OSError):
            pass


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    memory = Core14LongTermMemory(memory_path="data/memory/test_long_term_memory.json")

    memory.auto_update({"intent": "lights_off", "language": "en"})
    memory.auto_update({"intent": "lights_off", "language": "en"})
    memory.auto_update({"intent": "time", "language": "en"})

    memory.remember("favorite_color", "blue")
    print(memory.recall("favorite_color"))

    snapshot = memory.get_all()
    print(snapshot["stats"]["intent_counts"])

    memory.forget("favorite_color")
    print(memory.recall("favorite_color"))