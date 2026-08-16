# cores/core_17.py
# =====================================================
# CORE 17 – Personality & Emotion Expression Engine — Hardened
# Zephyr (authority) + Altair (companion)
# Now a real multi-turn conversation, not a fixed 4-line script.
# =====================================================

import time
import re
import webbrowser


class Core17PersonalityEngine:
    """
    Hardened Core 17
    - Overwork detection -> Altair nudges, Zephyr defends focus time
    - User can accept/decline the break, or delegate work to Zephyr
    - Zephyr override (tell them to back off)
    - Controlled actions (YouTube) — gated by private_mode
    - Fail-safe defaults: identity defaults to non-owner, private_mode
      defaults to False, so a caller that forgets to pass real values
      never accidentally gets more access than intended
    """

    def __init__(self):
        self.work_start_time = None
        self.state = "normal"

        self.FIRST_WARNING = 45 * 60
        self.OVERWORK = 90 * 60
        self.BREAK_DURATION = 15 * 60

        self.conversation_state = "idle"
        self.break_start_time = None

        self.override_active = False
        self.last_override_time = None
        self.override_cooldown = 30 * 60

        self.override_patterns = [
            r"\bzephyr\b.{0,25}\bneed to work\b",
            r"\bzephyr\b.{0,25}\bfocus\b",
            r"\bzephyr\b.{0,25}\bstop\b",
            r"\bzephyr\b.{0,25}\boverride\b",
            r"\bzephyr\b.{0,25}\btell her\b",
        ]

        self.last_action_time = None
        self.action_cooldown = 60 * 60

        self.last_dialogue_time = None
        self.dialogue_cooldown = 60 * 60

        self.silent_mode = False

        print("[Core 17] Personality engine initialized (Hardened, multi-turn)")

    # =================================================
    # ACTIVITY / STATE TRACKING
    # =================================================

    def register_activity(self):
        now = time.time()
        if self.work_start_time is None:
            self.work_start_time = now
        self._update_state()
        self._check_break_timeout()

    def reset_by_break(self):
        self.work_start_time = None
        self.state = "normal"
        print("[Core 17] Work timer reset by user")

    def enable_silent_mode(self):
        self.silent_mode = True
        print("[Core 17] Silent mode ENABLED")

    def disable_silent_mode(self):
        self.silent_mode = False
        print("[Core 17] Silent mode DISABLED")

    def _update_state(self):
        if not self.work_start_time:
            self.state = "normal"
            return
        elapsed = time.time() - self.work_start_time
        if elapsed >= self.OVERWORK:
            self.state = "overworked"
        elif elapsed >= self.FIRST_WARNING:
            self.state = "long_work"
        else:
            self.state = "normal"

    def _check_break_timeout(self):
        if self.conversation_state == "on_break" and self.break_start_time:
            if time.time() - self.break_start_time >= self.BREAK_DURATION:
                self.conversation_state = "idle"
                self.break_start_time = None
                self.work_start_time = None
                self.state = "normal"
                print("[Core 17] Break auto-ended, work timer reset")

    # =================================================
    # OVERRIDE DETECTION (checked first, every turn)
    # =================================================

    def detect_override(self, text: str) -> list:
        text = text.lower()
        for pattern in self.override_patterns:
            if re.search(pattern, text):
                self.override_active = True
                self.last_override_time = time.time()
                print("[Core 17] Zephyr override activated")
                return [
                    {"speaker": "Zephyr", "text": "Understood. You need to focus."},
                    {"speaker": "Altair", "text": "Okay... I understand. Just don't forget me again, alright?"},
                ]
        return []

    def _override_active_now(self) -> bool:
        if not self.override_active:
            return False
        elapsed = time.time() - self.last_override_time
        if elapsed >= self.override_cooldown:
            self.override_active = False
            return False
        return True

    # =================================================
    # OVERWORK NUDGE (Altair asks, Zephyr defends focus time)
    # =================================================

    def check_overwork_and_nudge(self, identity: str = "unknown", private_mode: bool = False) -> list:
        if identity != "owner" or self.silent_mode:
            return []

        if self.conversation_state != "idle":
            return []

        if self.state != "overworked":
            return []

        if not self._can_dialogue(private_mode):
            return []

        self.conversation_state = "awaiting_break_response"
        self.last_dialogue_time = time.time()

        return [
            {"speaker": "Altair", "text": "You've been working for so long... won't you take a little break with me?"},
            {"speaker": "Zephyr", "text": "Altair, can't you see he's working? Let him focus a little longer."},
        ]

    # =================================================
    # USER'S REPLY TO THE BREAK QUESTION
    # =================================================

    def handle_reply(self, intent: str, identity: str = "unknown", private_mode: bool = False) -> list:
        if identity != "owner":
            return []

        if self.conversation_state == "awaiting_break_response":
            if intent == "accept_break":
                self.conversation_state = "on_break_pending_delegation"
                return [
                    {"speaker": "Altair", "text": "Yay! Finally... I've been waiting for this."},
                    {"speaker": "Zephyr", "text": "Alright... but what about the work?"},
                ]
            if intent == "decline_break":
                self.conversation_state = "idle"
                return [{"speaker": "Zephyr", "text": "Understood. Focus mode continues."}]
            return []

        if self.conversation_state == "on_break_pending_delegation":
            if intent in ("delegate_work_break", "accept_break"):
                self.conversation_state = "on_break"
                self.break_start_time = time.time()

                lines = [{"speaker": "Zephyr", "text": "Understood. I'll continue the work — go enjoy your break."}]

                if self._can_open_youtube(private_mode):
                    try:
                        webbrowser.open("https://www.youtube.com")
                        self.last_action_time = time.time()
                        lines.append({"speaker": "Altair", "text": "Come on, let's go watch something!"})
                    except Exception as e:
                        print(f"[Core 17] Failed to open browser: {e}")

                return lines
            return []

        return []

    # =================================================
    # INTERNAL HELPERS
    # =================================================

    def _can_open_youtube(self, private_mode: bool) -> bool:
        if not private_mode:
            return False
        if self._override_active_now():
            return False
        if self.last_action_time and time.time() - self.last_action_time < self.action_cooldown:
            return False
        return True

    def _can_dialogue(self, private_mode: bool) -> bool:
        if not private_mode:
            return False
        if self._override_active_now():
            return False
        if self.last_dialogue_time and time.time() - self.last_dialogue_time < self.dialogue_cooldown:
            return False
        return True


# --------------------------------------------------
# Example usage — simulating your exact conversation
# --------------------------------------------------
if __name__ == "__main__":
    engine = Core17PersonalityEngine()
    engine.work_start_time = time.time() - (91 * 60)
    engine.register_activity()

    lines = engine.check_overwork_and_nudge(identity="owner", private_mode=True)
    for l in lines:
        print(f"{l['speaker']}: {l['text']}")

    print()
    lines = engine.handle_reply("accept_break", identity="owner", private_mode=True)
    for l in lines:
        print(f"{l['speaker']}: {l['text']}")

    print()
    lines = engine.handle_reply("delegate_work_break", identity="owner", private_mode=True)
    for l in lines:
        print(f"{l['speaker']}: {l['text']}")