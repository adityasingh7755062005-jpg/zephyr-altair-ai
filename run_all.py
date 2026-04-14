import subprocess
import sys

print("🚀 Starting Zephyr Full System...\n")


cloud_client = subprocess.Popen([sys.executable, "cloud_client.py"])
main_app = subprocess.Popen([sys.executable, "main_app.py"])

print("✅ All services started!")

try:
   
    cloud_client.wait()
    main_app.wait()
except KeyboardInterrupt:
    print("\n🛑 Stopping...")

    
    cloud_client.terminate()
    main_app.terminate()