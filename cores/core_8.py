# cores/core_8.py
# =========================
# Core 8 – Response Engine — Hardened
# Sole owner of ALL user-facing response text.
# Core 4 executes actions; Core 8 decides what to say about them.
# =========================

import datetime


class Core8ResponseEngine:
    """
    Phase 2 – Core 8 (Hardened)
    ----------------------------
    Responsibility:
    - Generate ALL text responses shown/spoken to the user
    - Cover every real intent Core 3 can detect
    - Cover Core 4's non-execution outcomes (blocked, low confidence, etc.)
    - Support English + Hindi

    Core 4 should call this for EVERY response — it should never
    build response strings itself.
    """

    def __init__(self):
        print("[Core 8] Response engine initialized (Hardened)")

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def generate_response(self, intent: str, data: dict = None, language: str = "en") -> str:
        """
        intent: the routed intent (or a status like "low_confidence",
                "permission_denied", "no_input", "action_failed")
        data:   optional dict with context (e.g. {"success": True} for
                actions, or nothing for simple intents)
        language: "en" or "hi"
        """
        data = data or {}
        language = language if language in ("en", "hi") else "en"

        handler = self._handlers().get(intent, self._unknown)
        return handler(data, language)

    # --------------------------------------------------
    # Handlers — one per intent / status
    # --------------------------------------------------
    def _handlers(self):
        return {
            "time": self._time,
            "date": self._date,
            "greeting": self._greeting,
            "exit_assistant": self._exit_assistant,
            "lights_off": self._action_result,
            "lights_on": self._action_result,
            "volume_up": self._action_result,
            "volume_down": self._action_result,
            "open_app": self._action_result,
            "close_app": self._action_result,
            "change_wallpaper": self._action_result,
            "stop_listening": self._action_result,
            "schedule_reminder": self._schedule_reminder,
            "dev_mode_toggle": self._passthrough_message,
            "dev_mode_code_result": self._passthrough_message,
            "unknown": self._unknown,
            "none": self._no_input,
            "no_input": self._no_input,
            "low_confidence": self._unknown,
            "permission_denied": self._permission_denied,
            "action_failed": self._action_failed,
        }

    def _time(self, data, language):
        now = data.get("now") or datetime.datetime.now()
        time_str = now.strftime("%I:%M %p")
        return {
            "en": f"The time is {time_str}.",
            "hi": f"Abhi samay {time_str} hai.",
        }[language]

    def _date(self, data, language):
        today = data.get("today") or datetime.date.today()
        date_str = today.strftime("%d %B %Y")
        return {
            "en": f"Today's date is {date_str}.",
            "hi": f"Aaj ki tareekh {date_str} hai.",
        }[language]

    def _greeting(self, data, language):
        return {
            "en": "Hello! I am Zephyr.",
            "hi": "Namaste! Main Zephyr hoon.",
        }[language]

    def _exit_assistant(self, data, language):
        # NOTE: this only asks for confirmation — Core 4 must NOT treat
        # this as an actual shutdown. Real shutdown goes through Core 5's
        # confirm-gated shutdown(), never triggered directly from a
        # single voice command.
        return {
            "en": "Do you want me to shut down? Please confirm.",
            "hi": "Kya aap chahte hain main band ho jaun? Kripya confirm karein.",
        }[language]

    def _action_result(self, data, language):
        success = data.get("success", False)
        action_label = data.get("action_label", "that")

        if success:
            return {
                "en": f"Done — {action_label}.",
                "hi": f"Ho gaya — {action_label}.",
            }[language]
        else:
            return {
                "en": f"I couldn't {action_label}. Something went wrong.",
                "hi": f"Main {action_label} nahi kar saka. Kuch galat ho gaya.",
            }[language]

    def _schedule_reminder(self, data, language):
        success = data.get("success", False)

        if success:
            run_at = data.get("run_at")
            time_str = run_at.strftime("%I:%M %p") if run_at else ""
            message = data.get("message", "Reminder")
            repeat = data.get("repeat")

            if repeat == "daily":
                return {
                    "en": f"Okay, I'll remind you to {message} every day at {time_str}.",
                    "hi": f"Theek hai, main aapko roz {time_str} baje '{message}' yaad dilaunga.",
                }[language]
            else:
                return {
                    "en": f"Okay, I'll remind you to {message} at {time_str}.",
                    "hi": f"Theek hai, main aapko {time_str} baje '{message}' yaad dilaunga.",
                }[language]
        else:
            error = data.get("error", "something went wrong")
            return {
                "en": f"I couldn't set that reminder — {error}.",
                "hi": f"Main woh reminder set nahi kar saka — {error}.",
            }[language]

    def _passthrough_message(self, data, language):
        # Core 10's messages are already phrased (security-critical
        # wording shouldn't be re-generated/translated automatically —
        # it's passed through as-is to avoid any mistranslation risk
        # around dev mode / access codes).
        return data.get("message", "")

    def _unknown(self, data, language):
        return {
            "en": "I understood you, but I don't know how to do that yet.",
            "hi": "Maine aapki baat samjhi, lekin mujhe abhi yeh karna nahi aata.",
        }[language]

    def _no_input(self, data, language):
        return {
            "en": "I didn't catch anything to act on.",
            "hi": "Mujhe kuch samajh nahi aaya.",
        }[language]

    def _permission_denied(self, data, language):
        return {
            "en": "Sorry, I'm not allowed to do that.",
            "hi": "Maaf kijiye, mujhe yeh karne ki anumati nahi hai.",
        }[language]

    def _action_failed(self, data, language):
        error = data.get("error", "an unknown error")
        return {
            "en": f"That failed: {error}",
            "hi": f"Yeh nahi ho paya: {error}",
        }[language]


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    engine = Core8ResponseEngine()

    print(engine.generate_response("time", language="en"))
    print(engine.generate_response("time", language="hi"))
    print(engine.generate_response("greeting", language="en"))
    print(engine.generate_response(
        "lights_off",
        data={"success": True, "action_label": "turn off the lights"},
        language="en"
    ))
    print(engine.generate_response(
        "lights_off",
        data={"success": False, "action_label": "turn off the lights"},
        language="en"
    ))
    print(engine.generate_response("low_confidence", language="en"))
    print(engine.generate_response("permission_denied", language="hi"))
    print(engine.generate_response("exit_assistant", language="en"))