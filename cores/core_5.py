# =========================================================
# CORE 5 – SYSTEM UTILITIES — Hardened
# =========================================================

import os
import platform
import subprocess
import logging
from datetime import datetime

# --------------------------------------------------
# Dedicated logger for system-level actions.
# Every destructive/system-touching action gets logged here,
# separate from normal print() debug output, so you have a
# real audit trail if something unexpected happens.
# --------------------------------------------------
logging.basicConfig(
    filename="core5_system_actions.log",
    level=logging.INFO,
    format="%(asctime)s [Core 5] %(message)s"
)


class Core5SystemUtils:
    """
    Phase 2 – Core 5 (Hardened)
    ----------------------------
    Responsibility:
    - Provide safe, cross-platform system-level actions
    - Require explicit confirmation for destructive actions
    - Log every attempt (success or failure) for auditing
    - Never let raw/dynamic user input reach a shell command

    IMPORTANT (build-order rule):
    Do NOT wire shutdown/restart into Core 4's live routing until
    Core 18 (Security & Trust) provides a real permission check.
    The `require_confirmation` flag here is a stopgap, not a
    replacement for that.
    """

    def __init__(self, require_confirmation: bool = True):
        self.os_type = platform.system()  # "Windows", "Linux", "Darwin"
        self.require_confirmation = require_confirmation
        self._pending_action = None  # tracks an action awaiting confirmation
        print(f"[Core 5] System utilities online (OS: {self.os_type})")
        logging.info(f"Core 5 initialized on {self.os_type}")

    # --------------------------------------------------
    # Safe informational utilities
    # --------------------------------------------------
    def get_time(self) -> str:
        return datetime.now().strftime("Current time is %I:%M %p")

    def get_date(self) -> str:
        return datetime.now().strftime("Today's date is %d %B %Y")

    # --------------------------------------------------
    # Destructive actions — require confirmation
    # --------------------------------------------------
    def shutdown(self, confirm: bool = False) -> str:
        return self._destructive_action("shutdown", confirm)

    def restart(self, confirm: bool = False) -> str:
        return self._destructive_action("restart", confirm)

    def cancel_shutdown(self) -> str:
        """Aborts a pending shutdown/restart (Windows/Linux support)."""
        try:
            if self.os_type == "Windows":
                result = subprocess.run(
                    ["shutdown", "/a"], capture_output=True, text=True, check=False
                )
            elif self.os_type == "Linux":
                result = subprocess.run(
                    ["shutdown", "-c"], capture_output=True, text=True, check=False
                )
            else:
                msg = f"Cancel not supported on {self.os_type}"
                logging.warning(msg)
                return msg

            self._pending_action = None

            if result.returncode == 0:
                logging.info("Pending shutdown/restart cancelled")
                return "Shutdown/restart cancelled."
            else:
                logging.info(f"Cancel attempted, nothing pending or failed: {result.stderr}")
                return "No pending shutdown to cancel."

        except Exception as e:
            logging.error(f"cancel_shutdown failed: {e}")
            return "Couldn't cancel — something went wrong."

    # --------------------------------------------------
    # Internal: confirmation-gated destructive action handler
    # --------------------------------------------------
    def _destructive_action(self, action: str, confirm: bool) -> str:
        if self.require_confirmation and not confirm:
            # First call: don't execute, ask for confirmation instead.
            self._pending_action = action
            logging.info(f"Action '{action}' requested but NOT confirmed — awaiting confirmation")
            return (
                f"Are you sure you want to {action}? "
                f"Say '{action} confirm' or call again with confirm=True."
            )

        # Confirmed (or confirmation disabled) — proceed.
        logging.info(f"Executing confirmed action: {action}")
        success, error = self._run_platform_command(action)

        self._pending_action = None

        if success:
            logging.info(f"Action '{action}' executed successfully")
            return f"{action.capitalize()} initiated."
        else:
            logging.error(f"Action '{action}' failed: {error}")
            return f"Failed to {action}: {error}"

    def _run_platform_command(self, action: str):
        """
        Runs the correct command per OS using subprocess with an
        argument LIST (never a shell string) — avoids injection risk
        entirely since there is no user-controlled input here.
        """
        try:
            if self.os_type == "Windows":
                if action == "shutdown":
                    cmd = ["shutdown", "/s", "/t", "5"]
                elif action == "restart":
                    cmd = ["shutdown", "/r", "/t", "5"]
                else:
                    return False, f"Unknown action: {action}"

            elif self.os_type == "Linux":
                if action == "shutdown":
                    cmd = ["shutdown", "-h", "+1"]  # 1 min delay
                elif action == "restart":
                    cmd = ["shutdown", "-r", "+1"]
                else:
                    return False, f"Unknown action: {action}"

            elif self.os_type == "Darwin":  # macOS
                if action == "shutdown":
                    cmd = ["sudo", "shutdown", "-h", "+1"]
                elif action == "restart":
                    cmd = ["sudo", "shutdown", "-r", "+1"]
                else:
                    return False, f"Unknown action: {action}"

            else:
                return False, f"Unsupported OS: {self.os_type}"

            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr.strip() or f"Exit code {result.returncode}"

        except FileNotFoundError:
            return False, "Shutdown command not found on this system"
        except Exception as e:
            return False, str(e)

    # --------------------------------------------------
    # Helper: check if there's an action waiting on confirmation
    # --------------------------------------------------
    def has_pending_action(self) -> bool:
        return self._pending_action is not None

    def get_pending_action(self):
        return self._pending_action


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    utils = Core5SystemUtils(require_confirmation=True)

    print(utils.get_time())
    print(utils.get_date())

    # First call — NOT executed, just asks for confirmation
    print(utils.shutdown())
    print("Pending action:", utils.get_pending_action())

    # Second call, now confirmed — this WOULD actually shut down the
    # machine if uncommented, so it's left commented for safety in this demo.
    # print(utils.shutdown(confirm=True))

    # Cancel a pending shutdown/restart
    print(utils.cancel_shutdown())