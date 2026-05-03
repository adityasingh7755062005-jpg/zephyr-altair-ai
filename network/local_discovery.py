# ==============================
# FILE: network/local_discovery.py (CLEAN)
# ==============================

import socket
import threading
import time

BROADCAST_PORT = 5002
BROADCAST_INTERVAL = 2
DISCOVERY_MESSAGE = "ZEPHYR_DISCOVERY"


class LocalDiscovery:

    def __init__(self):
        self.running = False

    def start(self):
        self.running = True

        threading.Thread(
            target=self._broadcast_loop,
            daemon=True
        ).start()

        print("[Discovery] started")

    def _broadcast_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while self.running:
            try:
                sock.sendto(DISCOVERY_MESSAGE.encode(), ("<broadcast>", BROADCAST_PORT))
            except:
                pass

            time.sleep(BROADCAST_INTERVAL)

    def stop(self):
        self.running = False


def start_local_discovery():
    discovery = LocalDiscovery()
    discovery.start()