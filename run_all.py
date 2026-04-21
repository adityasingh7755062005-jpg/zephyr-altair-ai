import subprocess
import sys
import time

print("🚀 Starting Zephyr Full System...\n")

while True:
    try:
        cloud_client = subprocess.Popen([sys.executable, "cloud_client.py"])
        main_app = subprocess.Popen([sys.executable, "main_app.py"])

        print("✅ All services started!")

        cloud_client.wait()
        main_app.wait()

    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        cloud_client.terminate()
        main_app.terminate()
        break

    except Exception as e:
        print("❌ System crashed, restarting...", e)
        time.sleep(3)