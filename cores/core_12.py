class Core12NLPNormalizer:
    """
    Phase 2 – Core 12
    -----------------
    Cleans and normalizes raw STT text
    into canonical command forms.
    """

    def __init__(self):
        print("[Core 12] NLP Normalizer initialized")

        # Canonical command maps
        self.english_map = {
            "time": [
                "time", "what is the time", "current time", "tell me time"
            ],
            "date": [
                "date", "today date", "what is the date", "current date"
            ],
            "greeting": [
                "hello", "hi", "hey"
            ],
            "exit": [
                "exit", "quit", "stop"
            ]
        }

        self.hindi_map = {
            "time": [
                "अभी कितना बजा है",
                "समय क्या है",
                "कितना बजा है"
            ],
            "date": [
                "आज तारीख क्या है",
                "आज की तारीख",
                "तारीख बताओ"
            ],
            "greeting": [
                "नमस्ते", "हैलो"
            ],
            "exit": [
                "बंद करो", "रुको"
            ]
        }

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def process(self, packet: dict) -> dict:
        text = packet.get("text", "")
        language = packet.get("language", "en")

        normalized = self._normalize(text, language)

        packet["normalized_text"] = normalized

        print(
            f"[Core 12] Normalized -> '{text}' → '{normalized}'"
        )

        return packet

    # --------------------------------------------------
    # Internal helper
    # --------------------------------------------------
    def _normalize(self, text: str, language: str) -> str:
        if not text:
            return "unknown"

        text = text.lower().strip()

        mapping = self.hindi_map if language == "hi" else self.english_map

        for canonical, variants in mapping.items():
            for phrase in variants:
                if phrase in text:
                    return canonical

        return "unknown"