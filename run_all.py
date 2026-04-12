import subprocess
import sys

print("🚀 Starting Zephyr Full System...\n")

cloud_server = subprocess.Popen([sys.executable, "zephyr_cloud_server.py"])
cloud_client = subprocess.Popen([sys.executable, "cloud_client.py"])
main_app = subprocess.Popen([sys.executable, "main_app.py"])

print("✅ All services started!")

try:
    cloud_server.wait()
    cloud_client.wait()
    main_app.wait()
except KeyboardInterrupt:
    print("\n🛑 Stopping...")

    cloud_server.terminate()
    cloud_client.terminate()
    main_app.terminate()