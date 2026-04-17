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
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )


try:
    cloud_client = start_process("Cloud Client", "cloud_client.py")
    main_app = start_process("Main App", "main_app.py")

    processes.append(cloud_client)
    processes.append(main_app)

    print("\n✅ All services started!\n")

    # 🔥 KEEP RUNNING FOREVER
    while True:
        # Check if any process died
        for p in processes:
            if p.poll() is not None:
                print("❌ A process stopped unexpectedly")
        time.sleep(2)

except KeyboardInterrupt:
    print("\n🛑 Stopping all services...")

    for p in processes:
        try:
            p.terminate()
        except:
            pass

    print("✅ Shutdown complete")