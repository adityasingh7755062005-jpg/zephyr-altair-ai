# cores/core_18_freeze_overlay.py
# Adds a "locked" flag so the overlay shows a different message
# depending on whether Windows was actually locked, or this is the
# standalone freeze-only mode.

import tkinter as tk
import threading
import queue

EMERGENCY_KEY_SEQUENCE = ("Control_L", "Alt_L", "Shift_L", "z")

LOCKED_MESSAGE = (
    "This device is protected by Zephyr Altair AI.\n\n"
    "Authorized mobile device required to unlock."
)
FREEZE_ONLY_MESSAGE = (
    "Monitoring active. This device is NOT locked.\n\n"
    "Activity is being watched and recorded."
)


class FreezeOverlay:
    def __init__(self):
        self.active = False
        self._cmd_queue = queue.Queue()
        self._running = True
        self._keys_held = set()

        self._thread = threading.Thread(target=self._ui_loop, daemon=True)
        self._thread.start()

    def show(self, locked: bool = True):
        self._cmd_queue.put(("SHOW", locked))

    def hide(self):
        self._cmd_queue.put(("HIDE", None))

    def stop(self):
        self._running = False
        self._cmd_queue.put(("STOP", None))

    def _ui_loop(self):
        try:
            root = tk.Tk()
            root.withdraw()

            overlay = tk.Toplevel(root)
            overlay.configure(bg="black")
            overlay.attributes("-fullscreen", True)
            overlay.attributes("-topmost", True)
            overlay.config(cursor="none")
            overlay.protocol("WM_DELETE_WINDOW", lambda: None)

            frame = tk.Frame(overlay, bg="black")
            frame.pack(expand=True)

            title_label = tk.Label(frame, text="ZEPHYR SECURITY LOCK", fg="white", bg="black",
                                    font=("Segoe UI", 42, "bold"))
            title_label.pack(pady=(0, 30))

            body_label = tk.Label(frame, text=LOCKED_MESSAGE, fg="white", bg="black",
                                   font=("Segoe UI", 20), justify="center")
            body_label.pack()

            overlay.withdraw()

            def on_key_press(event):
                self._keys_held.add(event.keysym)
                if all(k in self._keys_held for k in EMERGENCY_KEY_SEQUENCE):
                    print("[FreezeOverlay] EMERGENCY OVERRIDE triggered locally")
                    overlay.withdraw()
                    self.active = False
                    self._keys_held.clear()

            def on_key_release(event):
                self._keys_held.discard(event.keysym)

            overlay.bind("<KeyPress>", on_key_press)
            overlay.bind("<KeyRelease>", on_key_release)

            def enforce_focus():
                if self.active:
                    try:
                        overlay.lift()
                        overlay.attributes("-topmost", True)
                        overlay.focus_force()
                    except Exception:
                        pass
                root.after(500, enforce_focus)

            def process_commands():
                try:
                    while True:
                        cmd, payload = self._cmd_queue.get_nowait()
                        if cmd == "SHOW":
                            locked = payload
                            body_label.config(text=LOCKED_MESSAGE if locked else FREEZE_ONLY_MESSAGE)
                            title_label.config(text="ZEPHYR SECURITY LOCK" if locked else "ZEPHYR MONITORING")
                            overlay.deiconify()
                            overlay.lift()
                            overlay.attributes("-topmost", True)
                            overlay.focus_force()
                            self.active = True
                        elif cmd == "HIDE":
                            overlay.withdraw()
                            self.active = False
                        elif cmd == "STOP":
                            root.destroy()
                            return
                except queue.Empty:
                    pass
                if self._running:
                    root.after(50, process_commands)

            enforce_focus()
            process_commands()
            root.mainloop()

        except Exception as e:
            print("[FreezeOverlay ERROR]:", e)