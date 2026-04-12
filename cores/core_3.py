class Core3IntentDetector:
    """
    Phase 2 – Core 3
    ----------------
    Converts normalized text into intent.
    """

    def __init__(self):
        print("[Core 3] Intent detector initialized (Phase 2)")

    def process(self, packet: dict) -> dict:
        normalized = packet.get("normalized_text", "unknown")

        # Intent is directly the normalized command
        packet["intent"] = normalized if normalized else "unknown"

        print(f"[Core 3] Intent -> {packet['intent']}")

        return packet