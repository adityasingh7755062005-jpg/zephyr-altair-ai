# cores/core_10.py
# Core 10 – Behavior & Decision Engine

class Core10BehaviorEngine:
    def __init__(self):
        self.developer_mode = False

    # -------------------------
    # Developer mode control
    # -------------------------
    def handle_dev_mode(self, text: str):
        text = text.lower()

        if "developer mode on" in text:
            self.developer_mode = True
            return True, "Developer mode ENABLED."

        if "developer mode off" in text:
            self.developer_mode = False
            return True, "Developer mode DISABLED."

        return False, None

    # -------------------------
    # Main permission check
    # -------------------------
    def is_allowed(self, intent: str, text: str):
        text = text.lower()

        # 1️⃣ Handle developer mode commands
        handled, response = self.handle_dev_mode(text)
        if handled:
            return False, response

        # 2️⃣ Block self-upgrade commands unless dev mode
        if any(x in text for x in ["upgrade yourself", "modify yourself", "add this feature"]):
            if not self.developer_mode:
                return False, (
                    "Self-upgrade commands are locked. "
                    "Say 'developer mode on' to unlock."
                )
            return True, "Self-upgrade request accepted."

        # 3️⃣ Block dangerous intents
        dangerous_intents = ["delete_system", "format_disk", "disable_security"]
        if intent in dangerous_intents:
            return False, "This action is not permitted."

        # 4️⃣ Unknown intent → ask for clarity
        if intent == "unknown":
            return False, "I did not understand clearly. Please repeat."

        # 5️⃣ Otherwise allowed
        return True, None