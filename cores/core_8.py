# cores/core_8.py
# =========================
# Core 8 – Response Engine
# Text-only responses
# =========================

import datetime

class Core8ResponseEngine:
    def generate_response(self, intent, data=None, language="en"):

        if intent == "time":
            return f"Current time is {datetime.datetime.now().strftime('%I:%M %p')}"

        elif intent == "date":
            return f"Today's date is {datetime.date.today()}"

        elif intent == "greeting":
            return "Hello, I am Zephyr Altair AI"

        elif intent == "exit":
            return "Shutting down. Goodbye."

        else:
            return "Sorry, I did not understand the command"