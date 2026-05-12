# ===============================
# FILE: run_all.py
# FULL FIXED STABLE VERSION
# AUTO RESTART ENGINE
# ===============================

import subprocess
import sys
import time

# ===============================
# START
# ===============================

print("")
print("======================================")
print("🚀 Starting Zephyr Altair AI")
print("======================================")
print("")

main_process = None

# ===============================
# LOOP
# ===============================

while True:

    try:

        print("🌐 Launching main_app.py...")
        print("")

        # ===============================
        # START MAIN APP
        # ===============================

        main_process = subprocess.Popen(

            [
                sys.executable,
                "main_app.py"
            ],

            stdin=None,

            stdout=None,

            stderr=None
        )

        print(
            f"✅ main_app.py started "
            f"(PID: {main_process.pid})"
        )

        # ===============================
        # WAIT
        # ===============================

        exit_code = main_process.wait()

        print("")
        print(
            f"⚠️ main_app.py exited "
            f"(Code: {exit_code})"
        )

    # ===============================
    # MANUAL STOP
    # ===============================

    except KeyboardInterrupt:

        print("")
        print("🛑 Zephyr stopped manually")

        try:

            if main_process:

                main_process.terminate()

        except:
            pass

        break

    # ===============================
    # CRASH
    # ===============================

    except Exception as e:

        print("")
        print(
            f"❌ Launcher Error: {e}"
        )

    # ===============================
    # RESTART DELAY
    # ===============================

    print("")
    print("🔄 Restarting In 3 Seconds...")
    print("")

    time.sleep(3)