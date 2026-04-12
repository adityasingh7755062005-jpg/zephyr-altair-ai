import time
import psutil


class LoginWatcher:

    def __init__(self, on_login_callback):
        self.on_login_callback = on_login_callback
        self._armed = False
        self._last_explorer = False

    def arm(self):
        self._armed = True
        self._last_explorer = False
        print("[Core 18] LoginWatcher armed")

    def _explorer_running(self):
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == "explorer.exe":
                    return True
            except:
                continue
        return False

    def start(self):
        print("[Core 18] LoginWatcher started")

        while True:
            try:
                explorer_now = self._explorer_running()

                if self._armed and explorer_now and not self._last_explorer:
                    print("[Core 18] Desktop detected (Explorer appeared)")
                    self._armed = False
                    self.on_login_callback()

                self._last_explorer = explorer_now
                time.sleep(0.4)

            except Exception as e:
                print("[Core 18] LoginWatcher error:", e)
                time.sleep(1)