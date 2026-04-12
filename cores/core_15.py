import json
import os
from datetime import datetime


class Core15KnowledgeEngine:
    """
    Phase 2 – Core 15
    -----------------
    Level 1 Knowledge Engine.
    Stores explicit knowledge taught by the owner.
    """

    def __init__(self, kb_path="data/knowledge/knowledge_base.json"):
        self.kb_path = kb_path
        os.makedirs(os.path.dirname(kb_path), exist_ok=True)

        self.knowledge = {
            "meta": {
                "created": datetime.now().isoformat(),
                "last_updated": None
            },
            "entries": [],
            "stats": {
                "topics": {}
            }
        }

        self._load()
        print("[Core 15] Knowledge engine initialized (Phase 2 – Level 1)")

    # --------------------------------------------------
    # Load & Save
    # --------------------------------------------------
    def _load(self):
        if os.path.exists(self.kb_path):
            try:
                with open(self.kb_path, "r", encoding="utf-8") as f:
                    self.knowledge = json.load(f)
            except Exception:
                print("[Core 15] Knowledge file corrupted, starting fresh")

    def _save(self):
        self.knowledge["meta"]["last_updated"] = datetime.now().isoformat()
        with open(self.kb_path, "w", encoding="utf-8") as f:
            json.dump(self.knowledge, f, indent=2, ensure_ascii=False)

    # --------------------------------------------------
    # Explicit learning (OWNER ONLY)
    # --------------------------------------------------
    def learn(self, topic: str, content: str, language: str):
        """
        Stores a Level 1 knowledge entry.
        """

        entry = {
            "topic": topic,
            "content": content,
            "language": language,
            "level": 1,
            "source": "owner",
            "timestamp": datetime.now().isoformat()
        }

        self.knowledge["entries"].append(entry)

        # Update stats
        self.knowledge["stats"]["topics"].setdefault(topic, 0)
        self.knowledge["stats"]["topics"][topic] += 1

        self._save()

        print(f"[Core 15] Learned topic: {topic}")

    # --------------------------------------------------
    # Retrieval
    # --------------------------------------------------
    def recall(self, topic: str):
        """
        Retrieves all knowledge entries for a topic.
        """
        return [
            entry for entry in self.knowledge["entries"]
            if entry["topic"].lower() == topic.lower()
        ]

    def list_topics(self):
        return list(self.knowledge["stats"]["topics"].keys())

    # --------------------------------------------------
    # Automatic safe tracking (NO learning)
    # --------------------------------------------------
    def auto_track(self, topic: str):
        """
        Tracks topic frequency WITHOUT learning content.
        """
        if not topic:
            return

        self.knowledge["stats"]["topics"].setdefault(topic, 0)
        self.knowledge["stats"]["topics"][topic] += 1

        self._save()