# =========================================================
# CORE 5 – SYSTEM UTILITIES
# =========================================================

from datetime import datetime
import os

class Core5SystemUtils:
    def __init__(self):
        print("[Core 5] System utilities online")

    def get_time(self):
        return datetime.now().strftime("Current time is %I:%M %p")

    def get_date(self):
        return datetime.now().strftime("Today's date is %d %B %Y")

    def shutdown(self):
        os.system("shutdown /s /t 5")
        return "System shutting down"