# cores/core_13.py
# Core 13 – Short-Term Context Memory — Hardened (now functionally used)

from collections import deque


class Core13ContextMemory:
    """
    Phase 2 – Core 13 (Hardened)
    -------------------------------
    Responsibility:
    - Remember recent conversation turns
    - Make that history available to Core 3 BEFORE it processes the
      current turn, so follow-ups ("turn it off", "do it again") can
      be resolved
    - Record what actually happened AFTER Core 4 finishes routing

    USAGE (two-phase — different from other single-method cores):

        context_memory.attach_context(packet)   # BEFORE Core 3
        packet = core3.process(packet)
        packet = core12.process(packet)         # (or before Core 3, per pipeline order)
        ...
        result = core4.route(packet)
        context_memory.record_turn(
            text=packet.get("text", ""),
            intent=result["routed_intent"],
            response=result["response"],
        )
    """

    def __init__(self, max_turns: int = 5):
        self.max_turns = max_turns
        self.history = deque(maxlen=max_turns)

        print("[Core 13] Context memory initialized (Hardened, two-phase)")

    # --------------------------------------------------
    # Phase 1: attach recent context BEFORE Core 3 runs
    # --------------------------------------------------
    def attach_context(self, packet: dict) -> dict:
        packet["context"] = self._build_context()
        return packet

    # --------------------------------------------------
    # Phase 2: record what happened AFTER Core 4 finishes
    # --------------------------------------------------
    def record_turn(self, text: str, intent: str, response: str):
        self.history.append({
            "text": text,
            "intent": intent,
            "response": response,
        })
        print(f"[Core 13] Recorded turn | intent={intent}")

    # --------------------------------------------------
    # Internal helper
    # --------------------------------------------------
    def _build_context(self) -> dict:
        if not self.history:
            return {}

        last = self.history[-1]
        return {
            "last_text": last["text"],
            "last_intent": last["intent"],
            "last_response": last["response"],
            "turns": len(self.history),
        }


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    memory = Core13ContextMemory()

    packet = {"text": "turn off the lights"}
    memory.attach_context(packet)  # empty context, first turn
    print("Before turn 1:", packet["context"])

    memory.record_turn(text="turn off the lights", intent="lights_off",
                        response="Done — turn off the lights.")

    packet2 = {"text": "turn it back on"}
    memory.attach_context(packet2)  # now has last turn's context
    print("Before turn 2:", packet2["context"])