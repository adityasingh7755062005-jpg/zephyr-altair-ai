# cores/core_15.py
# Core 15 – Knowledge Engine — Hardened

import json
import os
import stat
import shutil
import threading
from datetime import datetime


class Core15KnowledgeEngine:
    """
    Phase 2 – Core 15 (Hardened)
    -------------------------------
    Level 1 Knowledge Engine — stores explicit knowledge taught
    by the owner.

    Fixes vs original:
    - learn() now REQUIRES verified_owner=True to actually store
      anything — the old "OWNER ONLY" docstring was not enforced
      in code at all. Until Core 18 (voice/face verification) is
      built, nothing can set this to True except code you control
      directly — so this fails safe.
    - Atomic writes + rolling backup (same pattern as Core 14)
    - Owner-only file/folder permissions
    - Thread-safe
    """

    def __init__(self, kb_path: str = "data/knowledge/knowledge_base.json"):
        self.kb_path = kb_path
        self.backup_path = kb_path + ".bak"
        self._lock = threading.Lock()

        os.makedirs(os.path.dirname(kb_path), exist_ok=True)
        self._restrict_permissions(os.path.dirname(kb_path))

        self.knowledge = self._default_knowledge()
        self._load()

        print("[Core 15] Knowledge engine initialized (Hardened – Level 1)")

    # --------------------------------------------------
    # Defaults
    # --------------------------------------------------
    def _default_knowledge(self) -> dict:
        return {
            "meta": {
                "created": datetime.now().isoformat(),
                "last_updated": None,
            },
            "entries": [],       # Level 1: owner-taught (verified only)
            "general": [],       # Level 2: public knowledge (Wikipedia etc.)
            "stats": {
                "topics": {},
                "general_topics": {},
            },
        }

    # --------------------------------------------------
    # Load & Save (atomic, with backup recovery)
    # --------------------------------------------------
    def _load(self):
        if not os.path.exists(self.kb_path):
            return

        try:
            with open(self.kb_path, "r", encoding="utf-8") as f:
                self.knowledge = json.load(f)
            return
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Core 15] WARNING: Knowledge file unreadable ({e}). Trying backup...")

        if os.path.exists(self.backup_path):
            try:
                with open(self.backup_path, "r", encoding="utf-8") as f:
                    self.knowledge = json.load(f)
                print("[Core 15] Recovered knowledge from backup file")
                return
            except (json.JSONDecodeError, OSError) as e:
                print(f"[Core 15] WARNING: Backup also unreadable ({e}).")

        print("[Core 15] No usable knowledge file found — starting fresh")
        self.knowledge = self._default_knowledge()

    def _save(self):
        self.knowledge["meta"]["last_updated"] = datetime.now().isoformat()
        tmp_path = self.kb_path + ".tmp"

        try:
            if os.path.exists(self.kb_path):
                shutil.copy2(self.kb_path, self.backup_path)

            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.knowledge, f, indent=2, ensure_ascii=False)

            os.replace(tmp_path, self.kb_path)
            self._restrict_permissions_file(self.kb_path)

        except OSError as e:
            print(f"[Core 15] ERROR: Failed to save knowledge base: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # --------------------------------------------------
    # Explicit learning (OWNER ONLY — now actually enforced)
    # --------------------------------------------------
    def learn(self, topic: str, content: str, language: str, verified_owner: bool = False) -> bool:
        """
        Stores a Level 1 knowledge entry.

        verified_owner MUST be True or nothing is stored. This will
        be set by Core 18's voice/face verification once it exists.
        Until then, only code you control directly can pass True —
        it can never come from an unverified voice command.

        Returns True if the entry was stored, False if refused.
        """
        if not verified_owner:
            print(f"[Core 15] REFUSED — unverified attempt to teach topic '{topic}'")
            return False

        if not topic or not content:
            print("[Core 15] Skipped — empty topic or content")
            return False

        with self._lock:
            entry = {
                "topic": topic,
                "content": content,
                "language": language,
                "level": 1,
                "source": "owner",
                "timestamp": datetime.now().isoformat(),
            }
            self.knowledge["entries"].append(entry)

            self.knowledge["stats"]["topics"].setdefault(topic, 0)
            self.knowledge["stats"]["topics"][topic] += 1

            self._save()

        print(f"[Core 15] Learned topic: {topic}")
        return True

    def forget_topic(self, topic: str, verified_owner: bool = False) -> bool:
        """Removes all entries for a topic. Also owner-gated."""
        if not verified_owner:
            print(f"[Core 15] REFUSED — unverified attempt to forget topic '{topic}'")
            return False

        with self._lock:
            before = len(self.knowledge["entries"])
            self.knowledge["entries"] = [
                e for e in self.knowledge["entries"] if e["topic"].lower() != topic.lower()
            ]
            removed = before - len(self.knowledge["entries"])

            if removed > 0:
                self.knowledge["stats"]["topics"].pop(topic, None)
                self._save()
                print(f"[Core 15] Forgot topic '{topic}' ({removed} entries removed)")
                return True

        return False

    # --------------------------------------------------
    # Level 2: General knowledge (public sources — NOT owner-gated,
    # since this isn't personal data, but always source-tagged for
    # transparency). This is deliberately narrow: published content
    # only (Wikipedia), never live audio/conversation from anyone.
    # --------------------------------------------------
    def learn_general(self, topic: str, content: str, source: str = "unknown") -> bool:
        if not topic or not content:
            return False

        with self._lock:
            entry = {
                "topic": topic,
                "content": content,
                "level": 2,
                "source": source,
                "timestamp": datetime.now().isoformat(),
            }
            self.knowledge["general"].append(entry)
            self.knowledge["stats"]["general_topics"].setdefault(topic, 0)
            self.knowledge["stats"]["general_topics"][topic] += 1
            self._save()

        print(f"[Core 15] Learned general knowledge: {topic} (source: {source})")
        return True

    def fetch_from_wikipedia(self, topic: str) -> dict:
        """
        Pulls a short summary from Wikipedia's public REST API and
        stores it as Level 2 knowledge. This is published, publicly
        available content someone chose to write and publish — not
        live audio or conversation from anyone nearby. Requires the
        `requests` package (already in your requirements.txt).
        """
        try:
            import requests
        except ImportError:
            return {"success": False, "error": "requests library not installed"}

        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.strip().replace(' ', '_')}"
            resp = requests.get(url, timeout=5, headers={"User-Agent": "ZephyrAltairAI/1.0"})

            if resp.status_code != 200:
                return {"success": False, "error": f"No Wikipedia entry found for '{topic}'"}

            data = resp.json()
            extract = data.get("extract", "")

            if not extract:
                return {"success": False, "error": f"Empty result for '{topic}'"}

            self.learn_general(topic, extract, source="wikipedia")
            return {"success": True, "content": extract}

        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Network error: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --------------------------------------------------
    # Retrieval — searches BOTH tiers, owner-taught takes priority
    # --------------------------------------------------
    def recall(self, topic: str) -> dict:
        with self._lock:
            owner_entries = [
                e for e in self.knowledge["entries"] if e["topic"].lower() == topic.lower()
            ]
            general_entries = [
                e for e in self.knowledge["general"] if e["topic"].lower() == topic.lower()
            ]
        return {"owner_taught": owner_entries, "general": general_entries}

    def list_topics(self) -> list:
        with self._lock:
            return list(self.knowledge["stats"]["topics"].keys())

    def get_all(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self.knowledge))  # deep copy

    # --------------------------------------------------
    # Automatic safe tracking (NO learning, NO content stored —
    # low risk, so no owner verification required here)
    # --------------------------------------------------
    def auto_track(self, topic: str):
        if not topic:
            return

        with self._lock:
            self.knowledge["stats"]["topics"].setdefault(topic, 0)
            self.knowledge["stats"]["topics"][topic] += 1
            self._save()

    # --------------------------------------------------
    # Permission hardening
    # --------------------------------------------------
    def _restrict_permissions(self, path: str):
        try:
            os.chmod(path, stat.S_IRWXU)
        except (PermissionError, NotImplementedError, OSError):
            pass

    def _restrict_permissions_file(self, path: str):
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except (PermissionError, NotImplementedError, OSError):
            pass


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    kb = Core15KnowledgeEngine(kb_path="data/knowledge/test_kb.json")

    # Unverified attempt — should be REFUSED
    print(kb.learn("wifi_password", "some_password", "en"))  # False

    # Verified (simulating what Core 18 will eventually provide)
    print(kb.learn("wifi_password", "correct_password", "en", verified_owner=True))  # True

    print(kb.recall("wifi_password"))
    print(kb.list_topics())

    kb.auto_track("weather")  # allowed, no content stored
    print(kb.get_all()["stats"]["topics"])