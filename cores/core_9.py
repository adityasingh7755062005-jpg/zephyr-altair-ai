# cores/core_9.py
# =========================
# Core 9 – Automation & Routine — Hardened
# Now routed through Core 4 (schedule_reminder intent) instead of
# being called directly from main_app.
# =========================

import threading
import time
import datetime
import re
import json
import os
import uuid


class Core9Automation:
    """
    Phase 2 – Core 9 (Hardened)
    ----------------------------
    Responsibility:
    - Schedule and fire reminders (one-time, at-time, daily)
    - Persist jobs to disk so they survive a restart
    - Speak reminders via Core 7 if provided, else print
    - Return structured results so Core 4 can ask Core 8 to phrase them

    Called by Core 4 (via a "schedule_reminder" intent), not directly
    from main_app — keeps automation inside the same permission/response
    pipeline as everything else.
    """

    MAX_JOBS = 100
    STORE_PATH = "data/core9_jobs.json"

    def __init__(self, voice_output=None):
        self.jobs = []
        self._lock = threading.Lock()
        self.voice_output = voice_output  # optional Core 7 instance

        os.makedirs(os.path.dirname(self.STORE_PATH), exist_ok=True)
        self._load_jobs()

        self._runner = threading.Thread(target=self._run, daemon=True)
        self._runner.start()
        print("[Core 9] Automation engine started (background, persisted)")

    # --------------------------------------------------
    # Public scheduling methods
    # --------------------------------------------------
    def add_reminder_in(self, minutes: int, message: str) -> dict:
        if minutes <= 0:
            return self._error_result("Minutes must be positive")
        run_at = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        return self._add_job(run_at, message, repeat=None)

    def add_reminder_at(self, hh_mm: str, message: str) -> dict:
        parsed = self._parse_hh_mm(hh_mm)
        if parsed is None:
            return self._error_result(f"Invalid time format: '{hh_mm}'")
        h, m = parsed

        now = datetime.datetime.now()
        run_at = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if run_at <= now:
            run_at += datetime.timedelta(days=1)
        return self._add_job(run_at, message, repeat=None)

    def add_daily(self, hh_mm: str, message: str) -> dict:
        parsed = self._parse_hh_mm(hh_mm)
        if parsed is None:
            return self._error_result(f"Invalid time format: '{hh_mm}'")
        h, m = parsed

        now = datetime.datetime.now()
        run_at = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if run_at <= now:
            run_at += datetime.timedelta(days=1)
        return self._add_job(run_at, message, repeat="daily")

    def list_reminders(self) -> list:
        with self._lock:
            return [
                {"id": j["id"], "message": j["message"],
                 "run_at": j["run_at"].strftime("%Y-%m-%d %H:%M"),
                 "repeat": j["repeat"]}
                for j in self.jobs
            ]

    def cancel_reminder(self, job_id: str) -> bool:
        with self._lock:
            for job in self.jobs:
                if job["id"] == job_id:
                    self.jobs.remove(job)
                    self._save_jobs()
                    print(f"[Core 9] Cancelled reminder: {job['message']}")
                    return True
        return False

    # --------------------------------------------------
    # Main entry point Core 4 calls
    # --------------------------------------------------
    def parse_and_schedule(self, text: str, language: str = "en") -> dict:
        """
        Parses raw text and schedules a reminder if it matches a
        known pattern. Returns a structured result for Core 4/8:

        {
            "success": bool,
            "message": str | None,
            "run_at": datetime | None,
            "repeat": str | None,
            "error": str | None
        }
        """
        text = text.lower().strip()

        # "remind me in 10 minutes [to call mom]"
        m = re.search(r"remind me in (\d+)\s*minutes?\s*(?:to\s+)?(.*)", text)
        if m:
            minutes = int(m.group(1))
            message = m.group(2).strip() or "Reminder"
            return self.add_reminder_in(minutes, message)

        # "remind me at 18:30 [to call mom]"
        m = re.search(r"remind me at (\d{1,2}:\d{2})\s*(?:to\s+)?(.*)", text)
        if m:
            message = m.group(2).strip() or "Reminder"
            return self.add_reminder_at(m.group(1), message)

        # "every day at 8:00 remind me to study"
        m = re.search(r"every day at (\d{1,2}:\d{2}) remind me (.+)", text)
        if m:
            message = m.group(2).strip() or "Reminder"
            return self.add_daily(m.group(1), message)

        return self._error_result("Couldn't understand the reminder request")

    # --------------------------------------------------
    # Internal: job management
    # --------------------------------------------------
    def _add_job(self, run_at: datetime.datetime, message: str, repeat) -> dict:
        with self._lock:
            if len(self.jobs) >= self.MAX_JOBS:
                return self._error_result(f"Reminder limit reached ({self.MAX_JOBS})")

            job = {
                "id": str(uuid.uuid4())[:8],
                "run_at": run_at,
                "message": message,
                "repeat": repeat,
            }
            self.jobs.append(job)
            self._save_jobs()

        print(f"[Core 9] Scheduled: '{message}' at {run_at.strftime('%Y-%m-%d %H:%M')}")
        return {
            "success": True,
            "message": message,
            "run_at": run_at,
            "repeat": repeat,
            "error": None,
        }

    def _run(self):
        while True:
            now = datetime.datetime.now()
            with self._lock:
                fired_any = False
                for job in list(self.jobs):
                    if now >= job["run_at"]:
                        self._fire(job)
                        fired_any = True
                        if job["repeat"] == "daily":
                            job["run_at"] += datetime.timedelta(days=1)
                        else:
                            self.jobs.remove(job)
                if fired_any:
                    self._save_jobs()
            time.sleep(1)

    def _fire(self, job: dict):
        print(f"\n[REMINDER] {job['message']}  ({datetime.datetime.now().strftime('%H:%M')})")
        if self.voice_output:
            try:
                self.voice_output.speak(job["message"], language="en")
            except Exception as e:
                print(f"[Core 9] Voice output failed for reminder: {e}")

    # --------------------------------------------------
    # Persistence
    # --------------------------------------------------
    def _save_jobs(self):
        try:
            serializable = [
                {**j, "run_at": j["run_at"].isoformat()} for j in self.jobs
            ]
            with open(self.STORE_PATH, "w") as f:
                json.dump(serializable, f, indent=2)
        except OSError as e:
            print(f"[Core 9] Failed to save jobs: {e}")

    def _load_jobs(self):
        if not os.path.exists(self.STORE_PATH):
            return
        try:
            with open(self.STORE_PATH, "r") as f:
                raw = json.load(f)
            self.jobs = [
                {**j, "run_at": datetime.datetime.fromisoformat(j["run_at"])}
                for j in raw
            ]
            print(f"[Core 9] Loaded {len(self.jobs)} persisted reminder(s)")
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"[Core 9] Failed to load persisted jobs, starting fresh: {e}")
            self.jobs = []

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _parse_hh_mm(self, hh_mm: str):
        try:
            h, m = map(int, hh_mm.split(":"))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h, m
            return None
        except (ValueError, AttributeError):
            return None

    def _error_result(self, error: str) -> dict:
        return {"success": False, "message": None, "run_at": None, "repeat": None, "error": error}


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    automation = Core9Automation(voice_output=None)

    print(automation.parse_and_schedule("remind me in 1 minutes to check the oven"))
    print(automation.parse_and_schedule("remind me at 23:59 to sleep"))
    print(automation.parse_and_schedule("every day at 08:00 remind me to stretch"))
    print(automation.parse_and_schedule("what's the weather"))  # no match

    print(automation.list_reminders())