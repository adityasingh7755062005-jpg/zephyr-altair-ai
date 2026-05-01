# ==============================
# FILE 2: core_18_discovery_server.py
# ==============================

import socket
import threading

DISCOVERY_PORT = 5002
DISCOVERY_MESSAGE = "WHERE_IS_ZEPHYR"
RESPONSE_PREFIX = "I_AM_ZEPHYR"


def start_discovery_server(port=DISCOVERY_PORT):

    def run():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", port))

        while True:
            try:
                data, addr = sock.recvfrom(1024)

                if data.decode() == DISCOVERY_MESSAGE:
                    hostname = socket.gethostname()
                    response = f"{RESPONSE_PREFIX}:{hostname}"

                    sock.sendto(response.encode(), addr)

            except Exception as e:
                print("[Discovery ERROR]", e)

    threading.Thread(target=run, daemon=True).start()