# ===============================
# FILE: run_all.py
# FULL FIXED STABLE VERSION
# AUTO RESTART ENGINE
# ===============================

import subprocess
import sys
import time

print("")
print("======================================")
print("🚀 Starting Zephyr Altair AI")
print("======================================")
print("")

main_process = None

while True:
    try:
        print("🌐 Launching main_app.py...")
        print("")

        main_process = subprocess.Popen(
            [sys.executable, "main_app.py"],
            stdin=None,
            stdout=None,
            stderr=None,
        )

        print(f"✅ main_app.py started (PID: {main_process.pid})")

        exit_code = main_process.wait()

        print("")
        print(f"⚠️ main_app.py exited (Code: {exit_code})")

    except KeyboardInterrupt:
        print("")
        print("🛑 Zephyr stopped manually")
        try:
            if main_process:
                main_process.terminate()
        except Exception:
            pass
        break

    except Exception as e:
        print("")
        print(f"❌ Launcher Error: {e}")

    print("")
    print("🔄 Restarting In 3 Seconds...")
    print("")
    time.sleep(3)