import subprocess
import sys
import time

print("🚀 Starting Zephyr...")

while True:
    try:
        main_app = subprocess.Popen([sys.executable, "main_app.py"])

        main_app.wait()

    except KeyboardInterrupt:
        print("Stopping...")
        main_app.terminate()
        break

    except Exception as e:
        print("Restarting...", e)
        time.sleep(3)