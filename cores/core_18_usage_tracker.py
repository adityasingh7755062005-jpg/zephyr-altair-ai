# cores/core_18_usage_tracker.py
#
# Tracks which app is actively being used during a Sibling or Guest
# session — not enforcement, just a live history log, matching the
# same local+cloud+offline pattern already proven for Intruder Logs.
#
# Detection method: checks the FOREGROUND (actively focused) window
# every 1.5s, using the same reliable pywin32+psutil combo already
# used elsewhere in this project (no new dependency).

import os
import json
import time
import threading
from datetime import datetime

try:
    import win32gui
    import win32process
    import psutil
    _WATCHER_AVAILABLE = True
except ImportError:
    _WATCHER_AVAILABLE = False

LOG_DIR = os.path.join("data", "security")
SIBLING_LOG_FILE = os.path.join(LOG_DIR, "sibling_history.json")
GUEST_LOG_FILE = os.path.join(LOG_DIR, "guest_history.json")
MAX_ENTRIES = 200
POLL_INTERVAL = 1.5


class UsageHistoryTracker:
    def __init__(self, push_callback=None):
        """push_callback(event_type: str, payload: dict) — called with
        a new entry the instant it's logged, for real-time push to
        the phone. Optional — history still gets recorded locally
        even if this is None."""
        self.active_session = None  # None | "sibling" | "guest"
        self.push_callback = push_callback
        self._last_app = None
        self.log_lock = threading.Lock()

        os.makedirs(LOG_DIR, exist_ok=True)

        if _WATCHER_AVAILABLE:
            threading.Thread(target=self._watch_loop, daemon=True).start()
            print("[UsageTracker] Ready")
        else:
            print("[UsageTracker] ⚠️ pywin32/psutil not available — usage tracking disabled")

    # ==========================
    # SESSION CONTROL
    # ==========================
    def start_session(self, session_type: str):
        self.active_session = session_type
        self._last_app = None
        print(f"[UsageTracker] {session_type} session started")

    def end_session(self):
        if self.active_session:
            print(f"[UsageTracker] {self.active_session} session ended")
        self.active_session = None
        self._last_app = None

    # ==========================
    # WATCH LOOP
    # ==========================
    def _watch_loop(self):
        while True:
            try:
                if self.active_session:
                    app_name = self._get_foreground_app()
                    if app_name and app_name != self._last_app:
                        self._last_app = app_name
                        self._log_entry(self.active_session, app_name)
            except Exception as e:
                print(f"[UsageTracker] Watch error: {e}")
            time.sleep(POLL_INTERVAL)

    def _get_foreground_app(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return psutil.Process(pid).name()
        except Exception:
            return None

    # ==========================
    # LOGGING
    # ==========================
    def _log_entry(self, session_type, app_name):
        now = datetime.now()
        entry = {
            "app_name": app_name,
            "timestamp": int(time.time()),
            "date": now.strftime("%d/%m/%Y"),
            "time": now.strftime("%H:%M:%S"),
        }

        log_file = SIBLING_LOG_FILE if session_type == "sibling" else GUEST_LOG_FILE
        with self.log_lock:
            entries = self._read_log(log_file)
            entries.insert(0, entry)
            entries = entries[:MAX_ENTRIES]
            self._write_log(log_file, entries)

        print(f"[UsageTracker] {session_type}: {app_name}")

        if self.push_callback:
            try:
                self.push_callback(f"{session_type}_app_opened", entry)
            except Exception as e:
                print(f"[UsageTracker] Push failed: {e}")

    def _read_log(self, path):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[UsageTracker] Read error: {e}")
        return []

    def _write_log(self, path, entries):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        except Exception as e:
            print(f"[UsageTracker] Write error: {e}")

    # ==========================
    # PUBLIC READ / CLEAR (used by local_server routes)
    # ==========================
    def get_history(self, session_type: str) -> list:
        log_file = SIBLING_LOG_FILE if session_type == "sibling" else GUEST_LOG_FILE
        with self.log_lock:
            return self._read_log(log_file)

    def clear_history(self, session_type: str):
        log_file = SIBLING_LOG_FILE if session_type == "sibling" else GUEST_LOG_FILE
        with self.log_lock:
            self._write_log(log_file, [])