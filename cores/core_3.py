# cores/core_3.py
# Core 3 - Intent Detection (Keyword/Rule-based) — Hardened

class Core3IntentDetector:
    """
    Phase 2 – Core 3 (Hardened)
    ----------------------------
    Responsibility:
    - Take Core 2's output packet (text + success/error)
    - Match text against a rule/keyword table to detect intent
    - Never blindly pass raw text through as "intent"
    - Flag low-confidence / unmatched commands instead of guessing
    """

    def __init__(self):
        print("[Core 3] Intent detector initialized (Hardened)")

        # ------------------------------------------------------------
        # Intent rules: each intent maps to a list of keyword GROUPS.
        # ALL keywords within a group must be present (as whole words)
        # for that group to match. Any group matching = intent matches.
        # This keeps matching flexible but still deliberate.
        # ------------------------------------------------------------
        self.intent_rules = {
            "lights_off": [
                ["lights", "off"],
                ["kill", "lights"],
            ],
            "lights_on": [
                ["lights", "on"],
                ["turn", "on", "lights"],
            ],
            "open_app": [
                ["open"],
            ],
            "close_app": [
                ["close"],
            ],
            "change_wallpaper": [
                ["change", "wallpaper"],
                ["set", "wallpaper"],
            ],
            "volume_up": [
                ["volume", "up"],
                ["increase", "volume"],
            ],
            "volume_down": [
                ["volume", "down"],
                ["decrease", "volume"],
                ["lower", "volume"],
            ],
            "stop_listening": [
                ["stop", "listening"],
                ["go", "to", "sleep"],
            ],
            # ---- Utility intents (moved here from Core 4's old raw-text
            # matching, so ALL intent detection goes through one system) ----
            "time": [
                ["time"],
            ],
            "date": [
                ["date"],
            ],
            "greeting": [
                ["hi"],
                ["hello"],
                ["hey"],
            ],
            "exit_assistant": [
                ["exit"],
                ["quit"],
                ["shutdown"],
            ],
            "schedule_reminder": [
                ["remind"],
                ["reminder"],
            ],
            # ---- Break dialogue intents (Core 17) ----
            "accept_break": [
                ["lets", "take", "break"],
                ["ok", "break"],
                ["yes", "break"],
                ["sure", "break"],
            ],
            "decline_break": [
                ["not", "now"],
                ["no", "break"],
                ["keep", "working"],
            ],
            "delegate_work_break": [
                ["you", "do", "the", "work"],
                ["you", "handle", "work"],
                ["you", "work", "i", "relax"],
            ],
        }

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def process(self, packet: dict) -> dict:
        """
        Takes Core 2's packet and adds "intent" + "confidence" fields.

        Expects packet shape from Core 2:
        {"success": bool, "text": str|None, "language": str, "error": str|None, "timed_out": bool}

        Returns the same packet, extended with:
        {
            "intent": str,        # matched intent name, or "unknown" / "none"
            "confidence": float,  # 0.0 - 1.0, rough heuristic
            "matched_keywords": list[str] | None
        }
        """

        # ---- Guard: upstream failure or timeout ----
        if not packet.get("success", False):
            packet["intent"] = "none"
            packet["confidence"] = 0.0
            packet["matched_keywords"] = None
            print(f"[Core 3] Skipped — upstream failure: {packet.get('error')}")
            return packet

        # Prefer Core 12's cleaned text if the pipeline includes it
        # (fillers stripped, punctuation removed). Falls back to raw
        # STT text if Core 12 hasn't run — Core 3 still works standalone.
        raw_text = packet.get("normalized_text") or packet.get("text", "")

        # ---- Guard: empty/missing text ----
        if not raw_text or not raw_text.strip():
            packet["intent"] = "none"
            packet["confidence"] = 0.0
            packet["matched_keywords"] = None
            print("[Core 3] Skipped — empty text")
            return packet

        normalized = raw_text.lower().strip()
        words = set(normalized.split())

        best_intent = "unknown"
        best_confidence = 0.0
        best_keywords = None

        for intent_name, keyword_groups in self.intent_rules.items():
            for group in keyword_groups:
                group_words = set(w.lower() for w in group)

                if group_words.issubset(words):
                    # Confidence heuristic: what fraction of the spoken
                    # sentence was made up of matched keywords. A tighter
                    # match (fewer extra words) = higher confidence.
                    confidence = len(group_words) / max(len(words), 1)

                    if confidence > best_confidence:
                        best_intent = intent_name
                        best_confidence = confidence
                        best_keywords = list(group_words)

        packet["intent"] = best_intent
        packet["confidence"] = round(best_confidence, 2)
        packet["matched_keywords"] = best_keywords
        packet["resolved_from_context"] = False

        # ---- Follow-up resolution using Core 13's context ----
        # If nothing matched directly, check whether this looks like a
        # follow-up to the previous turn (e.g. "turn it back on",
        # "do it again") and resolve it using recent history.
        if best_intent == "unknown":
            context = packet.get("context") or {}
            last_intent = context.get("last_intent")

            if last_intent and last_intent not in ("unknown", "none"):
                resolved = self._resolve_followup(words, last_intent)
                if resolved:
                    packet["intent"] = resolved
                    packet["confidence"] = 0.55  # moderate — inferred, not directly matched
                    packet["matched_keywords"] = None
                    packet["resolved_from_context"] = True
                    best_intent = resolved
                    print(f"[Core 3] Resolved follow-up '{raw_text}' -> {resolved} (from context)")

        if best_intent == "unknown":
            print(f"[Core 3] No intent matched for: '{raw_text}'")
        else:
            print(f"[Core 3] Intent -> {best_intent} (confidence: {packet['confidence']})")

        return packet

    # --------------------------------------------------
    # Follow-up resolution (uses Core 13's context)
    # --------------------------------------------------
    # Direction words that flip a previous intent to its opposite
    # (e.g. last turn was "lights_off", user now says "on")
    DIRECTION_MAP = {
        "on": {"lights_off": "lights_on"},
        "off": {"lights_on": "lights_off"},
        "up": {"volume_down": "volume_up"},
        "down": {"volume_up": "volume_down"},
    }

    # Words that mean "do the same thing again"
    REPEAT_WORDS = {"again", "same", "repeat"}

    def _resolve_followup(self, words: set, last_intent: str):
        """
        Tries to resolve a follow-up utterance using the previous
        turn's intent. Returns a resolved intent name, or None if
        this doesn't look like a follow-up at all.
        """
        # Direction-based flip: "turn it back on" after lights_off -> lights_on
        for direction_word, mapping in self.DIRECTION_MAP.items():
            if direction_word in words and last_intent in mapping:
                return mapping[last_intent]

        # Generic repeat: "do it again", "same thing"
        if words & self.REPEAT_WORDS:
            return last_intent

        return None

    # --------------------------------------------------
    # Utility: add new intents at runtime without editing the class
    # --------------------------------------------------
    def add_intent(self, intent_name: str, keyword_groups: list):
        """
        Add or extend an intent's keyword groups.
        Example: detector.add_intent("play_music", [["play", "music"], ["start", "song"]])
        """
        if intent_name not in self.intent_rules:
            self.intent_rules[intent_name] = []
        self.intent_rules[intent_name].extend(keyword_groups)
        print(f"[Core 3] Added rules for intent '{intent_name}'")


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    detector = Core3IntentDetector()

    # Simulating a successful Core 2 output
    fake_packet_1 = {
        "success": True,
        "text": "turn off the lights please",
        "language": "en",
        "error": None,
        "timed_out": False,
    }
    result_1 = detector.process(fake_packet_1)
    print(result_1)

    # Simulating unclear/unmatched speech
    fake_packet_2 = {
        "success": True,
        "text": "banana rocket sunday",
        "language": "en",
        "error": None,
        "timed_out": False,
    }
    result_2 = detector.process(fake_packet_2)
    print(result_2)

    # Simulating a failed Core 2 output (mic error, timeout, etc.)
    fake_packet_3 = {
        "success": False,
        "text": None,
        "language": "en",
        "error": "Listen timed out",
        "timed_out": True,
    }
    result_3 = detector.process(fake_packet_3)
    print(result_3)

    # Adding a new intent at runtime
    detector.add_intent("play_music", [["play", "music"], ["start", "song"]])
    fake_packet_4 = {
        "success": True,
        "text": "play music now",
        "language": "en",
        "error": None,
        "timed_out": False,
    }
    print(detector.process(fake_packet_4))