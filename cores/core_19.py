# cores/core_19.py
# Core 19 - Ethics & Rules Engine
#
# Governs the voice/text pipeline ONLY (Core 3 -> Core 19 -> Core 4).
# Phone app commands never pass through here — they already went
# through their own UI-level confirmation (WiFi-off warning,
# shutdown/restart dialog) before reaching the laptop, and take a
# completely separate code path (local_server.py / cloud_client.py
# straight to a Core 18 method). Re-confirming those here would just
# be annoying, not safer.
#
# Judgment model: tiers, not a single yes/no. Only Tier 2+ pauses.

class Tier:
    SAFE = 0           # no real effect — proceeds instantly
    ROUTINE = 1        # minor, easily reversible — proceeds instantly
    CONSEQUENTIAL = 2  # real, hard-to-undo effect — pauses for confirmation
    SENSITIVE = 3      # security/trust boundary, future self-upgrade actions — pauses for confirmation


CONFIRM_WORDS = {"yes", "yeah", "yep", "confirm", "sure", "do", "go", "ahead", "ok", "okay"}
CANCEL_WORDS = {"no", "nope", "cancel", "stop", "dont", "don't", "abort"}


class Core19EthicsEngine:
    """
    Phase 2 - Core 19
    -------------------
    Responsibility:
    - Classify every voice/text intent into a risk tier
    - Tier 0/1: no friction, proceed immediately
    - Tier 2/3: pause, ask for confirmation via Core 8, and correctly
      interpret the NEXT turn as the answer to that question
    - Extensible at runtime (matching Core 3's add_intent pattern),
      so new intents — including future self-upgrade actions Core 20
      will introduce — can register their tier without editing this
      class directly.
    """

    def __init__(self):
        print("[Core 19] Ethics engine initialized")

        self.intent_tiers = {
            # Tier 0 — Safe
            "time": Tier.SAFE,
            "date": Tier.SAFE,
            "greeting": Tier.SAFE,
            "stop_listening": Tier.SAFE,

            # Tier 1 — Routine
            "volume_up": Tier.ROUTINE,
            "volume_down": Tier.ROUTINE,
            "lights_on": Tier.ROUTINE,
            "lights_off": Tier.ROUTINE,
            "open_app": Tier.ROUTINE,
            "close_app": Tier.ROUTINE,
            "change_wallpaper": Tier.ROUTINE,
            "schedule_reminder": Tier.ROUTINE,

            # Tier 2 — Consequential
            "exit_assistant": Tier.CONSEQUENTIAL,

            # Tier 3 — Sensitive (reserved — nothing lives here yet;
            # future self-upgrade intents from Core 20 will register
            # here via add_intent(), same as Core 3's own pattern)
        }

        # Mirrors Core 10's pending_verification pattern — tracks a
        # question we just asked, so the NEXT turn is interpreted as
        # the answer, not routed as a brand-new command.
        self.pending_confirmation = None  # None, or {"intent": str, "packet": dict}

    # --------------------------------------------------
    # Runtime extensibility — same shape as Core 3's add_intent,
    # deliberately, so both cores feel consistent to extend later.
    # --------------------------------------------------
    def set_tier(self, intent_name: str, tier: int):
        self.intent_tiers[intent_name] = tier
        print(f"[Core 19] Registered '{intent_name}' at tier {tier}")

    def get_tier(self, intent_name: str) -> int:
        # Unknown intents default to CONSEQUENTIAL, not SAFE — an
        # unrecognized action is exactly the case that deserves a
        # pause, not a free pass.
        return self.intent_tiers.get(intent_name, Tier.CONSEQUENTIAL)

    # --------------------------------------------------
    # Main check — called from Core 4's permission gate
    # --------------------------------------------------
    def check(self, intent: str, packet: dict) -> dict:
        """
        Returns one of:
        {"decision": "proceed"}
        {"decision": "confirm_needed", "question": str}
        """
        tier = self.get_tier(intent)

        if tier <= Tier.ROUTINE:
            return {"decision": "proceed"}

        # Tier 2/3 — needs a spoken confirmation before executing.
        self.pending_confirmation = {"intent": intent, "packet": packet}
        question = self._confirmation_question(intent)
        print(f"[Core 19] Tier {tier} action '{intent}' — pausing for confirmation")
        return {"decision": "confirm_needed", "question": question}

    def _confirmation_question(self, intent: str) -> str:
        label = intent.replace("_", " ")
        return f"Are you sure you want to {label}? Say yes to confirm, or no to cancel."

    # --------------------------------------------------
    # Handling the reply to a pending confirmation — called EARLY in
    # Core 4's route(), before normal intent routing, same position
    # as Core 10's dev-mode code check.
    # --------------------------------------------------
    def has_pending_confirmation(self) -> bool:
        return self.pending_confirmation is not None

    def resolve_confirmation_reply(self, text: str) -> dict:
        """
        Returns one of:
        {"outcome": "confirmed", "intent": str, "packet": dict}
        {"outcome": "cancelled"}
        {"outcome": "unclear"}  # didn't sound like yes or no — ask again
        """
        if not self.pending_confirmation:
            return {"outcome": "cancelled"}

        words = set(text.lower().strip().split())

        if words & CONFIRM_WORDS:
            pending = self.pending_confirmation
            self.pending_confirmation = None
            return {"outcome": "confirmed", "intent": pending["intent"], "packet": pending["packet"]}

        if words & CANCEL_WORDS:
            self.pending_confirmation = None
            return {"outcome": "cancelled"}

        return {"outcome": "unclear"}