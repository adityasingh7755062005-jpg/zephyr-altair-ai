# ==============================
# FILE: network/local_discovery.py
# ==============================

import socket
import threading
import time


# ==============================
# CONFIG
# ==============================
BROADCAST_PORT = 5002
BROADCAST_INTERVAL = 2  # seconds

DISCOVERY_MESSAGE = "ZEPHYR_DISCOVERY"


class LocalDiscovery:
    """
    🔥 Broadcast laptop presence on local network
    Phone listens and detects IP automatically
    """

    def __init__(self):
        self.running = False

    # ==============================
    # START BROADCAST
    # ==============================
    def start(self):
        self.running = True

        threading.Thread(
            target=self._broadcast_loop,
            daemon=True
        ).start()

        print("[Discovery] 🚀 Broadcasting started")

    # ==============================
    # BROADCAST LOOP
    # ==============================
    def _broadcast_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running:
            try:
                message = DISCOVERY_MESSAGE.encode()

                # 🔥 Send to entire network
                sock.sendto(message, ("<broadcast>", BROADCAST_PORT))

                # Debug log
                print("[Discovery] 📡 Broadcast sent")

            except Exception as e:
                print("[Discovery] ❌ Error:", e)

            time.sleep(BROADCAST_INTERVAL)

    # ==============================
    # STOP
    # ==============================
    def stop(self):
        self.running = False


# ==============================
# HELPER FUNCTION
# ==============================
def start_local_discovery():
    discovery = LocalDiscovery()
    discovery.start()