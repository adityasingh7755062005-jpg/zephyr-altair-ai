# cores/core_12.py
# Core 12 – NLP Normalizer — Hardened (repurposed)
# Cleans raw STT text so Core 3's intent matching works better.
# Does NOT classify intent itself anymore — that's Core 3's job.

import re


class Core12NLPNormalizer:
    """
    Phase 2 – Core 12 (Hardened)
    ------------------------------
    Responsibility:
    - Lowercase (English only — Hindi has no case)
    - Strip punctuation
    - Collapse extra whitespace
    - Remove filler words that add no meaning ("please", "um", etc.)
    - Output packet["normalized_text"] for Core 3 to match against

    Deliberately does NOT strip words that could be real command
    keywords (e.g. never removes "stop", "exit", "time", "date").
    Only removes words that are pure filler in every context.
    """

    def __init__(self):
        print("[Core 12] NLP Normalizer initialized (Hardened — cleanup only)")

        # Conservative filler lists — only words that are NEVER
        # meaningful as a command keyword themselves.
        self.english_fillers = {
            "please", "kindly", "um", "uh", "umm", "uhh", "actually", "just",
        }
        self.hindi_fillers = {
            "कृपया",  # please
            "जरा",    # just/a little
            "ज़रा",
        }

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def process(self, packet: dict) -> dict:
        text = packet.get("text", "")
        language = packet.get("language", "en")

        normalized = self._normalize(text, language)
        packet["normalized_text"] = normalized

        print(f"[Core 12] Normalized -> '{text}' -> '{normalized}'")
        return packet

    # --------------------------------------------------
    # Internal helper
    # --------------------------------------------------
    def _normalize(self, text: str, language: str) -> str:
        if not text or not text.strip():
            return ""

        text = text.strip()

        if language != "hi":
            text = text.lower()

        # Strip punctuation (including apostrophes, so "let's" -> "lets"
        # and matches consistently against our keyword lists)
        text = re.sub(r"[.,!?;:']", "", text)

        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text).strip()

        # Remove filler words (word-boundary safe — split on spaces,
        # not substring matching, so we never accidentally strip part
        # of a real word)
        fillers = self.hindi_fillers if language == "hi" else self.english_fillers
        words = [w for w in text.split(" ") if w not in fillers]

        cleaned = " ".join(words).strip()

        # Safety: if removing fillers left nothing (e.g. someone just
        # said "please"), fall back to the original text rather than
        # returning empty and losing the utterance entirely.
        return cleaned if cleaned else text


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    normalizer = Core12NLPNormalizer()

    print(normalizer.process({"text": "Could you please turn off the lights?", "language": "en"}))
    print(normalizer.process({"text": "um, what's the time", "language": "en"}))
    print(normalizer.process({"text": "please", "language": "en"}))  # fallback case
    print(normalizer.process({"text": "remind me in 10 minutes to call mom", "language": "en"}))