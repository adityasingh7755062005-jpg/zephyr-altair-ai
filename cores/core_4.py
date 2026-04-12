import datetime


class Core4CommandRouter:
    def __init__(self, system_utils):
        self.system_utils = system_utils

    def route(self, text: str, language: str) -> str:
        text = text.lower().strip()

        # ---- TIME COMMAND ----
        if "time" in text:
            now = datetime.datetime.now()
            return f"The time is {now.strftime('%I:%M %p')}."

        # ---- DATE COMMAND ----
        if "date" in text:
            today = datetime.datetime.now()
            return f"Today's date is {today.strftime('%d %B %Y')}."

        # ---- GREETING ----
        if text in ["hi", "hello", "hey"]:
            return "Hello! I am Zephyr."

        # ---- FALLBACK ----
        return "I understood you, but I don't know how to do that yet."