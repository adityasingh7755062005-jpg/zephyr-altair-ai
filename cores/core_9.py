# cores/core_9.py
# =========================
# Core 9 – Automation & Routine (TEXT MODE)
# =========================

import threading
import time
import datetime
import re

class Core9Automation:
    def __init__(self):
        self.jobs = []
        self._lock = threading.Lock()
        self._runner = threading.Thread(target=self._run, daemon=True)
        self._runner.start()
        print("[Core 9] Automation engine started (background)")

    def add_reminder_in(self, minutes, message):
        run_at = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        self._add_job(run_at, message, repeat=None)

    def add_reminder_at(self, hh_mm, message):
        h, m = map(int, hh_mm.split(":"))
        now = datetime.datetime.now()
        run_at = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if run_at <= now:
            run_at += datetime.timedelta(days=1)
        self._add_job(run_at, message, repeat=None)

    def add_daily(self, hh_mm, message):
        h, m = map(int, hh_mm.split(":"))
        now = datetime.datetime.now()
        run_at = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if run_at <= now:
            run_at += datetime.timedelta(days=1)
        self._add_job(run_at, message, repeat="daily")

    def _add_job(self, run_at, message, repeat):
        with self._lock:
            self.jobs.append({
                "run_at": run_at,
                "message": message,
                "repeat": repeat
            })
        print(f"[Core 9] Scheduled: '{message}' at {run_at.strftime('%Y-%m-%d %H:%M')}")

    def _run(self):
        while True:
            now = datetime.datetime.now()
            with self._lock:
                for job in list(self.jobs):
                    if now >= job["run_at"]:
                        print(f"\n[REMINDER] {job['message']}  ({now.strftime('%H:%M')})")
                        if job["repeat"] == "daily":
                            job["run_at"] += datetime.timedelta(days=1)
                        else:
                            self.jobs.remove(job)
            time.sleep(1)

    # Simple parser helper (used by main_app)
    def parse_and_schedule(self, text):
        text = text.lower()

        # "remind me in 10 minutes"
        m = re.search(r"remind me in (\d+) minute", text)
        if m:
            self.add_reminder_in(int(m.group(1)), "Reminder")
            return True

        # "remind me at 18:30"
        m = re.search(r"remind me at (\d{1,2}:\d{2})", text)
        if m:
            self.add_reminder_at(m.group(1), "Reminder")
            return True

        # "every day at 8 remind me to study"
        m = re.search(r"every day at (\d{1,2}:\d{2}) remind me (.+)", text)
        if m:
            self.add_daily(m.group(1), m.group(2))
            return True

        return False