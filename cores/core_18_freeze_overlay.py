# ==============================
# FILE: core_18_freeze_overlay.py
# ==============================

import tkinter as tk
import threading
import queue


class FreezeOverlay:
    """
    🔒 Fullscreen lock overlay
    - Blocks user visually
    - Always stays on top
    - Controlled via thread-safe queue
    """

    def __init__(self):
        self.active = False
        self._cmd_queue = queue.Queue()
        self._running = True

        # 🔥 Start UI thread (must be single thread)
        self._thread = threading.Thread(
            target=self._ui_loop,
            daemon=True
        )
        self._thread.start()

    # ==============================
    # PUBLIC CONTROL METHODS
    # ==============================
    def show(self):
        """Show lock screen"""
        self._cmd_queue.put("SHOW")

    def hide(self):
        """Hide lock screen"""
        self._cmd_queue.put("HIDE")

    def stop(self):
        """Stop overlay safely"""
        self._running = False
        self._cmd_queue.put("STOP")

    # ==============================
    # UI THREAD LOOP
    # ==============================
    def _ui_loop(self):

        try:
            root = tk.Tk()
            root.withdraw()  # Hide root window

            # ==============================
            # CREATE OVERLAY WINDOW
            # ==============================
            overlay = tk.Toplevel(root)
            overlay.configure(bg="black")

            # 🔥 Fullscreen + always on top
            overlay.attributes("-fullscreen", True)
            overlay.attributes("-topmost", True)

            # 🔥 Remove cursor
            overlay.config(cursor="none")

            # 🔥 Disable close button
            overlay.protocol("WM_DELETE_WINDOW", lambda: None)

            # ==============================
            # UI CONTENT
            # ==============================
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

            # Start hidden
            overlay.withdraw()

            # ==============================
            # 🔥 FORCE FOCUS LOOP (ANTI ESCAPE)
            # ==============================
            def enforce_focus():
                if self.active:
                    try:
                        overlay.lift()
                        overlay.attributes("-topmost", True)
                        overlay.focus_force()
                    except:
                        pass
                root.after(500, enforce_focus)

            # ==============================
            # COMMAND HANDLER
            # ==============================
            def process_commands():
                try:
                    while True:
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

                        elif cmd == "STOP":
                            root.destroy()
                            return

                except queue.Empty:
                    pass

                if self._running:
                    root.after(50, process_commands)

            # ==============================
            # START LOOPS
            # ==============================
            enforce_focus()
            process_commands()

            root.mainloop()

        except Exception as e:
            print("[FreezeOverlay ERROR]:", e)