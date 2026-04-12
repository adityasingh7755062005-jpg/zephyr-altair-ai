import time
import ctypes


class SessionWatcher:

    def __init__(self, on_lock, on_unlock, poll_interval=0.5):
        self.on_lock = on_lock
        self.on_unlock = on_unlock
        self.poll_interval = poll_interval
        self._last_locked = None

    def _is_locked(self):
        try:
            return ctypes.windll.user32.GetForegroundWindow() == 0
        except:
            return False

    def start(self):
        print("[Core 18] SessionWatcher started")

        while True:
            try:
                locked = self._is_locked()

                if locked != self._last_locked:
                    self._last_locked = locked

                    if locked:
                        self.on_lock()
                    else:
                        self.on_unlock()

                time.sleep(self.poll_interval)

            except Exception as e:
                print("[Core 18] SessionWatcher error:", e)
                time.sleep(1)