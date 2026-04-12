# cores/core_17.py
# =====================================================
# CORE 17 – Personality & Emotion Expression Engine
# Zephyr (authority) + Altair (companion)
# =====================================================

import time
import re
import webbrowser


class Core17PersonalityEngine:
    """
    FINAL Core 17
    - Overwork detection
    - Emotion escalation
    - Zephyr override
    - Controlled actions (YouTube)
    - Zephyr ↔ Altair dialogue
    """

    def __init__(self):
        # ----------------------------
        # Overwork tracking
        # ----------------------------
        self.work_start_time = None
        self.state = "normal"

        self.FIRST_WARNING = 45 * 60      # 45 minutes
        self.OVERWORK = 90 * 60           # 90 minutes

        # ----------------------------
        # Override (Zephyr authority)
        # ----------------------------
        self.override_active = False
        self.last_override_time = None
        self.override_cooldown = 30 * 60  # 30 minutes

        self.override_patterns = [
            r"zephyr.*need to work",
            r"zephyr.*focus",
            r"zephyr.*stop",
            r"zephyr.*override",
            r"zephyr.*tell her"
        ]

        # ----------------------------
        # Controlled actions
        # ----------------------------
        self.last_action_time = None
        self.action_cooldown = 60 * 60    # 1 hour

        # ----------------------------
        # Dialogue control
        # ----------------------------
        self.last_dialogue_time = None
        self.dialogue_cooldown = 60 * 60  # 1 hour

        # ----------------------------
        # Silent mode
        # ----------------------------
        self.silent_mode = False

        print("[Core 17] Personality engine fully initialized")

    # =================================================
    # PUBLIC METHODS (CALLED FROM MAIN)
    # =================================================

    def register_activity(self):
        """Call this whenever user gives a command"""
        now = time.time()
        if self.work_start_time is None:
            self.work_start_time = now
        self._update_state()

    def reset_by_break(self):
        """Explicit reset only by user command"""
        self.work_start_time = None
        self.state = "normal"
        print("[Core 17] Work timer reset by user")

    def enable_silent_mode(self):
        self.silent_mode = True
        print("[Core 17] Silent mode ENABLED")

    def disable_silent_mode(self):
        self.silent_mode = False
        print("[Core 17] Silent mode DISABLED")

    def process(
        self,
        text: str,
        identity: str,
        private_mode: bool
    ):
        """
        Main entry point.
        Returns:
        - list of messages to speak (ordered)
        - action flags (youtube_opened, etc.)
        """

        responses = []
        actions = []

        # ----------------------------
        # Register activity
        # ----------------------------
        self.register_activity()

        # ----------------------------
        # Check Zephyr override
        # ----------------------------
        if self._detect_override(text):
            responses.append(
                "Zephyr: Understood. You need to focus."
            )
            responses.append(
                "Altair: Okay… I understand. "
                "Just don’t forget me again, alright?"
            )
            return responses, actions

        # ----------------------------
        # Silent mode
        # ----------------------------
        if self.silent_mode:
            return [], actions

        # ----------------------------
        # Identity check
        # ----------------------------
        if identity != "owner":
            responses.append(
                "Zephyr: Unauthorized or limited access."
            )
            return responses, actions

        # ----------------------------
        # Emotion escalation
        # ----------------------------
        if self.state == "long_work":
            responses.append(
                "Altair: You’ve been working for quite a while… "
                "don’t you think you deserve a tiny break?"
            )

        elif self.state == "overworked":
            responses.append(
                "Altair: Please… just a short break. "
                "I’m a little worried about you."
            )

            # ----------------------------
            # Dialogue (private only)
            # ----------------------------
            if self._can_dialogue(private_mode):
                responses.extend(self._run_dialogue())

            # ----------------------------
            # Controlled action (YouTube)
            # ----------------------------
            if self._can_open_youtube(private_mode):
                webbrowser.open("https://www.youtube.com")
                self.last_action_time = time.time()
                actions.append("youtube_opened")
                responses.append(
                    "Zephyr: Enjoy your break. "
                    "I’ll remind you to return to work shortly."
                )

        return responses, actions

    # =================================================
    # INTERNAL HELPERS
    # =================================================

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

    def _detect_override(self, text: str):
        text = text.lower()
        for pattern in self.override_patterns:
            if re.search(pattern, text):
                self.override_active = True
                self.last_override_time = time.time()
                print("[Core 17] Zephyr override activated")
                return True
        return False

    def _override_active(self):
        if not self.override_active:
            return False

        elapsed = time.time() - self.last_override_time
        if elapsed >= self.override_cooldown:
            self.override_active = False
            return False
        return True

    def _can_open_youtube(self, private_mode: bool):
        if not private_mode:
            return False

        if self._override_active():
            return False

        if self.last_action_time:
            if time.time() - self.last_action_time < self.action_cooldown:
                return False

        return True

    def _can_dialogue(self, private_mode: bool):
        if not private_mode:
            return False

        if self._override_active():
            return False

        if self.last_dialogue_time:
            if time.time() - self.last_dialogue_time < self.dialogue_cooldown:
                return False

        return True

    def _run_dialogue(self):
        self.last_dialogue_time = time.time()
        dialogue = [
            "Zephyr: Altair, he’s been working too long.",
            "Altair: I know… I just worry about him.",
            "Zephyr: We’ll allow a short break. Then he focuses.",
            "Altair: Alright… I trust you."
        ]
        return dialogue