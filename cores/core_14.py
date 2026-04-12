import json
import os
from datetime import datetime


class Core14LongTermMemory:
    """
    Phase 2 – Core 14
    -----------------
    Long-term persistent memory.
    Supports:
    - Automatic safe learning
    - Explicit user-approved memory
    """

    def __init__(self, memory_path="data/memory/long_term_memory.json"):
        self.memory_path = memory_path
        os.makedirs(os.path.dirname(memory_path), exist_ok=True)

        self.memory = {
            "meta": {
                "created": datetime.now().isoformat(),
                "last_updated": None
            },
            "preferences": {},
            "habits": {},
            "facts": {},
            "stats": {
                "intent_counts": {}
            }
        }

        self._load()
        print("[Core 14] Long-term memory initialized (Phase 2)")

    # --------------------------------------------------
    # Load & Save
    # --------------------------------------------------
    def _load(self):
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
            except Exception:
                print("[Core 14] Memory file corrupted, starting fresh")

    def _save(self):
        self.memory["meta"]["last_updated"] = datetime.now().isoformat()
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=2, ensure_ascii=False)

    # --------------------------------------------------
    # Automatic learning (SAFE)
    # --------------------------------------------------
    def auto_update(self, packet: dict):
        """
        Learns safe patterns automatically.
        Called every successful interaction.
        """

        intent = packet.get("intent")
        language = packet.get("language")

        # Track frequent intents
        if intent:
            self.memory["stats"]["intent_counts"].setdefault(intent, 0)
            self.memory["stats"]["intent_counts"][intent] += 1

        # Track preferred language
        if language:
            self.memory["preferences"]["language"] = language

        self._save()

    # --------------------------------------------------
    # Explicit memory command
    # --------------------------------------------------
    def remember(self, key: str, value: str):
        """
        Stores user-approved memory explicitly.
        """
        self.memory["facts"][key] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
        self._save()

        print(f"[Core 14] Explicit memory stored: {key}")

    # --------------------------------------------------
    # Retrieval
    # --------------------------------------------------
    def recall(self, key: str):
        return self.memory["facts"].get(key)

    def get_all(self):
        return self.memory