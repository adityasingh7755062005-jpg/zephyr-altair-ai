from collections import deque


class Core13ContextMemory:
    """
    Phase 2 – Core 13
    -----------------
    Handles short-term conversational context.
    """

    def __init__(self, max_turns: int = 5):
        self.max_turns = max_turns
        self.history = deque(maxlen=max_turns)

        print("[Core 13] Context memory initialized (Phase 2)")

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def process(self, packet: dict) -> dict:
        intent = packet.get("intent", "unknown")
        response = packet.get("response_text", "")

        # Store current turn
        self.history.append({
            "intent": intent,
            "response": response
        })

        # Attach last context
        packet["context"] = self._build_context()

        print(f"[Core 13] Context updated | last_intent={intent}")

        return packet

    # --------------------------------------------------
    # Internal helper
    # --------------------------------------------------
    def _build_context(self) -> dict:
        if not self.history:
            return {}

        last = self.history[-1]

        return {
            "last_intent": last["intent"],
            "last_response": last["response"],
            "turns": len(self.history)
        }