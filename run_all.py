import subprocess
import sys
import time
import signal

print("🚀 Starting Zephyr Full System...\n")

processes = []

def start_process(name, file):
    print(f"🔄 Starting {name}...")
    return subprocess.Popen(
        [sys.executable, file],
        creationflags=subprocess.CREATE_NEW_CONSOLE  # ✅ important for Windows
    )

try:
    cloud_client = start_process("Cloud Client", "cloud_client.py")
    main_app = start_process("Main App", "main_app.py")

    processes.append(cloud_client)
    processes.append(main_app)

    print("\n✅ All services started!\n")

    # 🔥 Keep main thread alive
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Stopping all services...")

    for p in processes:
        try:
            p.terminate()
        except:
            pass

    print("✅ Shutdown complete")