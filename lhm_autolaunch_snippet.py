import subprocess
import requests

# Add this near the top of main_app.py, alongside your other imports:
#
#   import subprocess
#   import requests

# Then add this function definition (anywhere before it's called):

LHM_PATH = r"C:\Users\ASUS\Downloads\LibreHardwareMonitor\LibreHardwareMonitor.exe"
LHM_URL = "http://localhost:8085/data.json"


def ensure_lhm_running():
    """Launches LibreHardwareMonitor if it's not already running.
    Now that UAC won't prompt, this happens silently. Its web server
    setting (Options > Remote Web Server > Run) should already be
    saved from when you enabled it manually — if CPU temp still
    shows "N/A" after this, that setting may need re-checking once."""
    try:
        requests.get(LHM_URL, timeout=1)
        print("[LHM] Already running")
        return
    except Exception:
        pass  # not running yet — start it below

    import os
    if not os.path.exists(LHM_PATH):
        print(f"[LHM] Not found at {LHM_PATH} — CPU temp will show unavailable")
        return

    try:
        subprocess.Popen([LHM_PATH], cwd=os.path.dirname(LHM_PATH))
        print("[LHM] Launched")
    except Exception as e:
        print(f"[LHM] Launch failed: {e}")


# Finally, call it EARLY — before Core18() is created — so it has a
# moment's head start:
#
#   ensure_lhm_running()
#   core = Core18()
#   ...