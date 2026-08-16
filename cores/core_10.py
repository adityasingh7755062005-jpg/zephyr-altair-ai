# cores/core_10.py
# Core 10 – Behavior & Decision Engine — Hardened

import os
import hashlib
import logging
import datetime

logging.basicConfig(
    filename="core10_behavior.log",
    level=logging.INFO,
    format="%(asctime)s [Core 10] %(message)s"
)


class Core10BehaviorEngine:
    """
    Phase 2 – Core 10 (Hardened)
    ----------------------------
    Responsibility:
    - Gate developer mode behind an owner code (not just a spoken phrase)
    - Block self-upgrade commands unless developer mode is active
    - Block dangerous intents outright
    - Log every attempt (success, failure, blocked) for auditing
    - Provide a hook for future phone-app remote approval
      (Core 18 pairing/trust + Core 21 communication will call
      approve_pending() once built — no rework needed here later)

    Set your owner code via an environment variable, never hardcode it:
        Windows (PowerShell):  $env:ZEPHYR_OWNER_CODE = "yourcode"
        Or add it to your OS's persistent environment variables.
    """

    MAX_FAILED_ATTEMPTS = 3

    def __init__(self, owner_code_env_var: str = "ZEPHYR_OWNER_CODE"):
        self.developer_mode = False
        self.pending_verification = None  # e.g. "enable_dev_mode"
        self.failed_attempts = 0
        self.locked = False  # permanent until restart or manual reset — no auto-timer

        raw_code = os.environ.get(owner_code_env_var)
        if not raw_code:
            print(
                f"[Core 10] WARNING: No owner code set in env var '{owner_code_env_var}'. "
                f"Developer mode cannot be enabled until one is set."
            )
            self._code_hash = None
        else:
            self._code_hash = self._hash(raw_code)

        print("[Core 10] Behavior engine initialized (Hardened)")
        logging.info("Core 10 initialized")

    # --------------------------------------------------
    # Developer mode control
    # --------------------------------------------------
    def handle_dev_mode(self, text: str):
        """Returns (handled: bool, message: str|None)."""
        text = text.lower()

        if "developer mode on" in text:
            if self.developer_mode:
                return True, "Developer mode is already enabled."
            if self.locked:
                return True, "Developer mode is locked due to too many failed attempts. Restart to reset."
            if not self._code_hash:
                return True, "No owner code is configured — developer mode can't be enabled."

            self.pending_verification = "enable_dev_mode"
            logging.info("Dev mode requested — awaiting owner code")
            return True, "Please provide your access code to enable developer mode."

        if "developer mode off" in text:
            # Turning OFF (reducing privilege) never needs a code —
            # safety should always be easy to re-establish.
            self.developer_mode = False
            self.pending_verification = None
            logging.info("Dev mode disabled")
            return True, "Developer mode DISABLED."

        return False, None

    def provide_code(self, code: str) -> dict:
        """
        Call this when the pipeline detects a spoken/typed code while
        pending_verification is set (Core 4 should route to this,
        not straight to is_allowed, when awaiting_code is True).
        """
        if self.pending_verification != "enable_dev_mode":
            return {"success": False, "message": "No pending verification."}

        if self.locked:
            return {"success": False, "message": "Locked due to too many failed attempts."}

        if self._code_hash and self._hash(code) == self._code_hash:
            self.developer_mode = True
            self.pending_verification = None
            self.failed_attempts = 0
            logging.info("Dev mode ENABLED via correct owner code")
            return {"success": True, "message": "Developer mode ENABLED."}

        self.failed_attempts += 1
        logging.warning(f"Incorrect owner code attempt ({self.failed_attempts}/{self.MAX_FAILED_ATTEMPTS})")

        if self.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
            self.locked = True
            self.pending_verification = None
            logging.warning("Core 10 LOCKED after repeated failed code attempts")
            return {"success": False, "message": "Too many incorrect attempts. Developer mode is now locked until restart."}

        return {"success": False, "message": "Incorrect code. Please try again."}

    def approve_pending(self, source: str = "remote") -> dict:
        """
        Hook for future phone-app / Core 18+21 approval.
        Once your phone app can talk to the assistant (Core 21) and
        is itself authenticated (Core 18 pairing), it can call this
        directly to approve a pending dev-mode request WITHOUT the
        spoken code — the authenticated phone connection IS the
        second factor at that point.
        """
        if self.pending_verification != "enable_dev_mode":
            return {"success": False, "message": "No pending verification."}
        if self.locked:
            return {"success": False, "message": "Locked due to too many failed attempts."}

        self.developer_mode = True
        self.pending_verification = None
        self.failed_attempts = 0
        logging.info(f"Dev mode ENABLED via remote approval (source={source})")
        return {"success": True, "message": f"Developer mode ENABLED (approved via {source})."}

    # --------------------------------------------------
    # Main permission check
    # --------------------------------------------------
    def is_allowed(self, intent: str, text: str) -> dict:
        """
        Returns:
        {
            "allowed": bool,
            "message": str | None,
            "awaiting_code": bool
        }
        """
        text = text.lower()

        # 1. Dev mode commands
        handled, response = self.handle_dev_mode(text)
        if handled:
            return {
                "allowed": False,  # this call was a mode toggle, not an action request
                "message": response,
                "awaiting_code": self.pending_verification == "enable_dev_mode",
            }

        # 2. Self-upgrade commands — only if dev mode is genuinely active
        if any(x in text for x in ["upgrade yourself", "modify yourself", "add this feature"]):
            if not self.developer_mode:
                logging.warning(f"Blocked self-upgrade attempt (dev mode off): '{text}'")
                return {
                    "allowed": False,
                    "message": "Self-upgrade commands are locked. Say 'developer mode on' to unlock.",
                    "awaiting_code": False,
                }
            logging.info(f"Self-upgrade request accepted: '{text}'")
            return {"allowed": True, "message": "Self-upgrade request accepted.", "awaiting_code": False}

        # 3. Dangerous intents — always blocked, regardless of dev mode
        dangerous_intents = ["delete_system", "format_disk", "disable_security"]
        if intent in dangerous_intents:
            logging.warning(f"Blocked dangerous intent: '{intent}'")
            return {"allowed": False, "message": "This action is not permitted.", "awaiting_code": False}

        # 4. Unknown intent
        if intent == "unknown":
            return {"allowed": False, "message": "I did not understand clearly. Please repeat.", "awaiting_code": False}

        # 5. Otherwise allowed
        return {"allowed": True, "message": None, "awaiting_code": False}

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    # For this demo, simulate an owner code being set:
    os.environ["ZEPHYR_OWNER_CODE"] = "zephyr-1234"

    engine = Core10BehaviorEngine()

    # Someone just says the phrase — should NOT enable immediately
    print(engine.is_allowed("unknown", "developer mode on"))

    # Wrong code
    print(engine.provide_code("wrong-code"))

    # Correct code
    print(engine.provide_code("zephyr-1234"))

    # Now self-upgrade should be accepted
    print(engine.is_allowed("unknown", "please upgrade yourself with a new feature"))

    # Dangerous intent — always blocked regardless of dev mode
    print(engine.is_allowed("format_disk", "format the disk"))

    # Turn dev mode off — no code needed
    print(engine.is_allowed("unknown", "developer mode off"))