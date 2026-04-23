import tkinter as tk
import threading
import queue


class FreezeOverlay:

    def __init__(self):
        self.active = False
        self._cmd_queue = queue.Queue()

        self._thread = threading.Thread(
            target=self._ui_loop,
            daemon=True
        )
        self._thread.start()

    def show(self):
        self._cmd_queue.put("SHOW")

    def hide(self):
        self._cmd_queue.put("HIDE")

    def _ui_loop(self):

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

        title = tk.Label(
            frame,
            text="ZEPHYR SECURITY LOCK",
            fg="white",
            bg="black",
            font=("Segoe UI", 42, "bold")
        )
        title.pack(pady=(0, 30))

        message = tk.Label(
            frame,
            text=(
                "This device is protected by Zephyr Altair AI.\n\n"
                "Authorized mobile device required to unlock."
            ),
            fg="white",
            bg="black",
            font=("Segoe UI", 20),
            justify="center"
        )
        message.pack()

        overlay.withdraw()

        def poll():
            try:
                cmd = self._cmd_queue.get_nowait()

                if cmd == "SHOW":
                    overlay.deiconify()
                    overlay.lift()
                    overlay.attributes("-topmost", True)
                    overlay.focus_force()
                    self.active = True

                elif cmd == "HIDE":
                    overlay.withdraw()
                    self.active = False

            except queue.Empty:
                pass

            root.after(50, poll)

        poll()
        root.mainloop()