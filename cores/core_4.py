# cores/core_4.py
# Core 4 - Command Router — Hardened v2 (delegates ALL text to Core 8)
# + Core 19 (Ethics & Rules) wired into the permission gate

from datetime import datetime


class Core4CommandRouter:
    """
    Phase 2 – Core 4 (Hardened v2)
    ----------------------------------
    Responsibility:
    - Take Core 3's packet (intent + confidence + text)
    - Decide whether to execute (permission gate + confidence check)
    - Execute via system_utils where applicable
    - Ask Core 8 for the response text — NEVER build response
      strings itself
    """

    # FIXED: was 0.5, which rejected perfectly clear commands. Core 3
    # computes confidence as (matched keywords / total words), so a
    # normal phrasing like "what's the time" scores 1/3 = 0.33 and was
    # being thrown out. 0.3 accepts real single-keyword intents while
    # still rejecting genuine non-matches (which score 0.0).
    CONFIDENCE_THRESHOLD = 0.3

    # Which intents map to a real system_utils call, and a human label
    # Core 8 can use in "Done — {label}" style responses.
    ACTION_INTENTS = {
        "lights_off": "turn off the lights",
        "lights_on": "turn on the lights",
        "volume_up": "increase the volume",
        "volume_down": "decrease the volume",
        "stop_listening": "stop listening",
        "open_app": "open the app",
        "close_app": "close the app",
        "change_wallpaper": "change the wallpaper",
    }

    # Intents that don't need system_utils — Core 8 handles them with
    # just context data (time/date) or nothing at all (greeting).
    INFO_INTENTS = {"time", "date", "greeting"}

    def __init__(self, system_utils=None, response_engine=None, automation_engine=None,
                 behavior_engine=None, personality_engine=None, ethics_engine=None):
        self.system_utils = system_utils
        self.response_engine = response_engine  # Core 8 instance
        self.automation_engine = automation_engine  # Core 9 instance
        self.behavior_engine = behavior_engine  # Core 10 instance
        self.personality_engine = personality_engine  # Core 17 instance
        self.ethics_engine = ethics_engine  # Core 19 instance
        print("[Core 4] Command router initialized (Hardened v2)")

    # --------------------------------------------------
    # PERMISSION HOOK
    # --------------------------------------------------
    def _is_permitted(self, intent: str, packet: dict) -> bool:
        # Core 10 (Behavior & Decision Engine) — real check.
        if self.behavior_engine is not None:
            text = packet.get("text", "") or ""
            result = self.behavior_engine.is_allowed(intent, text)
            if not result["allowed"]:
                return False
        # Core 18 (security/trust) checks happen upstream of Core 4
        # entirely — this pipeline only runs for the voice/text path,
        # which Core 18 already gates via freeze/lock state.
        return True  # Core 19's tier check happens separately, in route()

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def route(self, packet: dict) -> dict:
        """
        Takes Core 3's packet, executes if appropriate, and returns:
        {
            "response": str,        # from Core 8, always
            "routed_intent": str,
            "executed": bool,
            "blocked_reason": str | None
        }
        """
        intent = packet.get("intent", "none")
        confidence = packet.get("confidence", 0.0)
        text = (packet.get("text") or "").strip()

        if not self.response_engine:
            raise RuntimeError("Core 4 requires a response_engine (Core 8) instance")

        identity = packet.get("identity", "unknown")  # set by Core 18 once it exists
        private_mode = packet.get("private_mode", False)  # safe default
        nudge_lines = []

        # ---- Core 19: reply to a pending confirmation bypasses
        # normal intent routing entirely — same position/priority as
        # Core 10's dev-mode code check below, since "yes"/"no" isn't
        # a real intent Core 3 would classify meaningfully anyway. ----
        if self.ethics_engine and self.ethics_engine.has_pending_confirmation():
            result = self.ethics_engine.resolve_confirmation_reply(text)

            if result["outcome"] == "confirmed":
                confirmed_intent = result["intent"]
                confirmed_packet = result["packet"]
                print(f"[Core 4] Confirmed by user -> executing '{confirmed_intent}'")
                return self._execute_confirmed(confirmed_intent, confirmed_packet)

            if result["outcome"] == "cancelled":
                return self._finish("action_cancelled", {}, packet, executed=False, blocked_reason="user_cancelled")

            # "unclear" — didn't sound like yes or no, ask again rather
            # than silently dropping the pending confirmation.
            question = self.ethics_engine._confirmation_question(
                self.ethics_engine.pending_confirmation["intent"]
            )
            return self._finish("clarify_confirmation", {"question": question}, packet,
                                 executed=False, blocked_reason="awaiting_confirmation")

        # ---- Core 17: Zephyr override check (highest priority, every turn) ----
        if self.personality_engine and text:
            override_lines = self.personality_engine.detect_override(text)
            if override_lines:
                return self._dialogue_result(override_lines, "zephyr_override")

        # ---- Core 17: register this turn as activity, check for overwork ----
        if self.personality_engine:
            self.personality_engine.register_activity()

            # If this turn's intent is a reply to a pending break question,
            # handle it via the dialogue system instead of normal routing.
            if intent in ("accept_break", "decline_break", "delegate_work_break"):
                reply_lines = self.personality_engine.handle_reply(intent, identity, private_mode)
                if reply_lines:
                    return self._dialogue_result(reply_lines, intent)

            # Otherwise, check if overwork just crossed the threshold —
            # if so, prepend Altair/Zephyr's nudge to whatever normal
            # response this turn produces.
            nudge_lines = self.personality_engine.check_overwork_and_nudge(identity, private_mode)
            self._pending_nudge_lines = nudge_lines if nudge_lines else None

        # ---- Meta-commands (dev mode toggle / code entry) bypass normal
        # intent gating entirely — they're control-plane commands about
        # the assistant itself, not content commands, and must work
        # even if Core 3 can't classify them as a known intent. ----
        if self.behavior_engine:
            if self.behavior_engine.pending_verification == "enable_dev_mode":
                code_result = self.behavior_engine.provide_code(text)
                return self._finish("dev_mode_code_result", code_result, packet,
                                     executed=code_result["success"],
                                     blocked_reason=None if code_result["success"] else "invalid_code")

            handled, message = self.behavior_engine.handle_dev_mode(text)
            if handled:
                awaiting = self.behavior_engine.pending_verification == "enable_dev_mode"
                return self._finish("dev_mode_toggle", {"message": message, "awaiting_code": awaiting},
                                     packet, executed=False, blocked_reason=None)

        # ---- Guard: nothing to route ----
        if intent in ("none", None) or not text:
            return self._finish("no_input", {}, packet, executed=False, blocked_reason="no_input")

        # ---- Guard: low confidence, don't guess ----
        if intent == "unknown" or confidence < self.CONFIDENCE_THRESHOLD:
            print(f"[Core 4] Low confidence ({confidence}) for intent '{intent}' — asking for clarification")
            return self._finish("low_confidence", {}, packet, executed=False, blocked_reason="low_confidence")

        # ---- Permission gate (Core 10 behavior check) ----
        if not self._is_permitted(intent, packet):
            print(f"[Core 4] Blocked by permission gate: {intent}")
            return self._finish("permission_denied", {}, packet, executed=False, blocked_reason="permission_denied")

        # ---- Core 19: tier check. Tier 0/1 falls through immediately
        # (return value ignored below); Tier 2/3 short-circuits here
        # and asks for confirmation instead of executing. ----
        if self.ethics_engine:
            tier_result = self.ethics_engine.check(intent, packet)
            if tier_result["decision"] == "confirm_needed":
                return self._finish("confirm_needed", {"question": tier_result["question"]}, packet,
                                     executed=False, blocked_reason="awaiting_confirmation")

        return self._route_action(intent, packet, text)

    # --------------------------------------------------
    # Everything past the permission/tier gates — shared by both the
    # normal path and the "user just confirmed a Tier 2/3 action" path.
    # --------------------------------------------------
    def _route_action(self, intent: str, packet: dict, text: str) -> dict:
        confidence = packet.get("confidence", 0.0)

        # ---- Info intents: gather data, let Core 8 phrase it ----
        if intent == "time":
            return self._finish("time", {"now": datetime.now()}, packet, executed=True, blocked_reason=None)

        if intent == "date":
            return self._finish("date", {"today": datetime.now().date()}, packet, executed=True, blocked_reason=None)

        if intent == "greeting":
            return self._finish("greeting", {}, packet, executed=True, blocked_reason=None)

        # ---- Exit: now flows through Core 19's Tier 2 confirmation
        # (see intent_tiers in core_19.py) instead of this ad-hoc
        # special case. Kept as a safety net only if ethics_engine
        # isn't connected for some reason (dev/testing).
        if intent == "exit_assistant":
            if self.ethics_engine:
                return self._finish("action_failed", {"error": "exit should have been gated by Core 19"},
                                     packet, executed=False, blocked_reason="internal_error")
            return self._finish("exit_assistant", {}, packet, executed=False, blocked_reason="needs_confirmation")

        # ---- Reminder scheduling: delegate to Core 9 ----
        if intent == "schedule_reminder":
            if not self.automation_engine:
                return self._finish("action_failed", {"error": "Automation engine not connected"},
                                     packet, executed=False, blocked_reason="not_connected")

            language = packet.get("language", "en")
            result = self.automation_engine.parse_and_schedule(text, language=language)
            print(f"[Core 4] Routed -> schedule_reminder | success={result['success']}")
            return self._finish("schedule_reminder", result, packet,
                                 executed=result["success"],
                                 blocked_reason=None if result["success"] else "schedule_failed")

        # ---- Action intents: call system_utils, report result ----
        if intent in self.ACTION_INTENTS:
            success, error = self._call_system_util(intent)
            data = {
                "success": success,
                "error": error,
                "action_label": self.ACTION_INTENTS[intent],
            }
            response_key = intent if success else "action_failed"
            print(f"[Core 4] Routed -> {intent} | success={success} | confidence={confidence}")
            return self._finish(response_key, data, packet, executed=success,
                                 blocked_reason=None if success else "action_failed")

        # ---- Recognized-but-unrouted intent ----
        return self._finish("unknown", {}, packet, executed=False, blocked_reason="unrouted_intent")

    def _execute_confirmed(self, intent: str, packet: dict) -> dict:
        """Called once Core 19 has confirmed a Tier 2/3 action — runs
        the SAME execution path as a normal action, just entered from
        the confirmation reply instead of a fresh command."""
        text = (packet.get("text") or "").strip()

        if intent == "exit_assistant":
            # FIXED: previously reused the "exit_assistant" response key,
            # which is the ASKING text ("Do you want me to shut down?") —
            # so confirming a shutdown replied by asking again. Now it
            # reports the real outcome instead.
            if self.system_utils:
                self.system_utils.shutdown(confirm=True)
                return self._finish("action_result",
                                     {"success": True, "action_label": "shut down"},
                                     packet, executed=True, blocked_reason=None)
            return self._finish("action_failed", {"error": "System utilities not connected"},
                                 packet, executed=False, blocked_reason="not_connected")

        return self._route_action(intent, packet, text)

    # --------------------------------------------------
    # Execution helper
    # --------------------------------------------------
    def _call_system_util(self, intent: str):
        """Calls the matching system_utils method safely. Returns (success, error)."""
        if self.system_utils is None:
            print(f"[Core 4] system_utils not connected — stubbing '{intent}'")
            return True, None  # stub success so the pipeline is testable end-to-end

        method_name = intent  # e.g. "lights_off" -> system_utils.lights_off()
        method = getattr(self.system_utils, method_name, None)

        if method is None:
            return False, f"No system_utils method for '{intent}'"

        try:
            method()
            return True, None
        except Exception as e:
            print(f"[Core 4] system_utils error on '{intent}': {e}")
            return False, str(e)

    # --------------------------------------------------
    # Helper: ask Core 8 for text, assemble final result
    # --------------------------------------------------
    def _finish(self, response_key: str, data: dict, packet: dict, executed: bool, blocked_reason) -> dict:
        language = packet.get("language", "en")
        response_text = self.response_engine.generate_response(response_key, data, language)

        # If Core 17 produced an overwork nudge this turn, prepend it to
        # the normal response so both happen together naturally.
        nudge = getattr(self, "_pending_nudge_lines", None)
        dialogue_lines = []
        if nudge:
            dialogue_lines = nudge
            nudge_text = " ".join(f"{l['speaker']}: {l['text']}" for l in nudge)
            response_text = f"{nudge_text} {response_text}"
            self._pending_nudge_lines = None

        return {
            "response": response_text,
            "dialogue_lines": dialogue_lines,  # structured, for future per-speaker TTS
            "routed_intent": packet.get("intent", "none"),
            "executed": executed,
            "blocked_reason": blocked_reason,
        }

    def _dialogue_result(self, lines: list, intent_label: str) -> dict:
        """Builds a route() result directly from Core 17's dialogue lines,
        bypassing Core 8 entirely — Core 17 owns this text, not Core 8."""
        response_text = " ".join(f"{l['speaker']}: {l['text']}" for l in lines)
        return {
            "response": response_text,
            "dialogue_lines": lines,
            "routed_intent": intent_label,
            "executed": True,
            "blocked_reason": None,
        }