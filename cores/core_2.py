# cores/core_2.py
# Core 2 - Speech to Text (English + Hindi) — Hardened — SECONDARY / SUPPORTIVE STT

import os
import queue
import json
import threading
import time
import sounddevice as sd
from vosk import Model, KaldiRecognizer

EN_MODEL_PATH = "models/vosk-model-en-us-0.22"
HI_MODEL_PATH = "models/vosk-model-hi-0.22"


class Core2STT:
    """
    Phase 2 – Core 2 (Hardened) — SECONDARY / SUPPORTIVE STT
    ------------------------------------------------------------
    NOT part of the main pipeline. Core 6 (Core 1 -> 11 -> 6 -> 3 -> 4)
    is the primary STT path for normal voice commands.

    Core 2 exists for situations where LIVE streaming recognition is
    more useful than record-then-transcribe, e.g.:
    - Quick yes/no confirmations (like Core 5's "say 'shutdown confirm'")
    - A future always-listening wake-word mode
    - Interrupting/cancelling an in-progress action verbally

    Returns the SAME packet shape as Core 6 (success/text/language/error)
    so it can be dropped into the same downstream cores (3, 4) without
    any changes on their end.

    Responsibility:
    - Stream mic audio into Vosk for offline speech-to-text
    - Return a structured packet (never raises to caller)
    - Support timeout, cancellation, and safe language switching
    """

    def __init__(self, language: str = "en", listen_timeout: float = 10.0):
        print("[Core 2] Initializing STT...")
        self.language = language
        self.listen_timeout = listen_timeout
        self.audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self.model = None
        self.recognizer = None

        self._load_model(language)

    # --------------------------------------------------
    # Model loading
    # --------------------------------------------------
    def _load_model(self, language: str):
        """Loads the Vosk model for a language, validating the path first."""
        model_path = HI_MODEL_PATH if language == "hi" else EN_MODEL_PATH

        if not os.path.isdir(model_path):
            raise FileNotFoundError(
                f"[Core 2] Model path not found: {model_path}. "
                f"Download/extract the Vosk model before starting Core 2."
            )

        try:
            print(f"[Core 2] Loading {language.upper()} Vosk model...")
            self.model = Model(model_path)
            self.recognizer = KaldiRecognizer(self.model, 16000)
            self.language = language
        except Exception as e:
            raise RuntimeError(f"[Core 2] Failed to load model at {model_path}: {e}")

    # --------------------------------------------------
    # Audio callback
    # --------------------------------------------------
    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[Core 2] Stream status: {status}")
        self.audio_queue.put(bytes(indata))

    # --------------------------------------------------
    # Main public method (blocking, with timeout)
    # --------------------------------------------------
    def listen(self) -> dict:
        """
        Listens until speech is recognized, timeout is hit, or stop() is called.

        Returns:
        {
            "success": bool,
            "text": str | None,
            "language": str,
            "error": str | None,
            "timed_out": bool
        }
        """
        # Clear any stale audio left over from a previous call
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()

        self._stop_event.clear()
        self.recognizer.Reset()  # fresh recognizer state each call

        print(f"[Core 2] Listening ({self.language.upper()})... Speak now")
        start_time = time.time()

        try:
            with sd.RawInputStream(
                samplerate=16000,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=self._callback
            ):
                while True:
                    # ---- Timeout check ----
                    if time.time() - start_time > self.listen_timeout:
                        return self._packet(success=False, text=None,
                                             error="Listen timed out", timed_out=True)

                    # ---- Manual stop check ----
                    if self._stop_event.is_set():
                        return self._packet(success=False, text=None,
                                             error="Listening stopped", timed_out=False)

                    try:
                        data = self.audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue  # loop back to re-check timeout/stop

                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "").strip()

                        if text:
                            print(f"[STT-{self.language.upper()}] {text}")
                            return self._packet(success=True, text=text, error=None,
                                                 timed_out=False)
                        # empty result (silence) — keep listening until timeout

        except sd.PortAudioError as e:
            return self._packet(success=False, text=None,
                                 error=f"Microphone error: {e}", timed_out=False)
        except Exception as e:
            return self._packet(success=False, text=None,
                                 error=f"Unexpected error: {e}", timed_out=False)

    # --------------------------------------------------
    # Cancellation
    # --------------------------------------------------
    def stop(self):
        """Call from another thread to interrupt an in-progress listen()."""
        self._stop_event.set()

    # --------------------------------------------------
    # Safe language switching
    # --------------------------------------------------
    def switch_language(self, language: str):
        if language == self.language:
            print(f"[Core 2] Already using {language.upper()}, skipping reload")
            return

        print(f"[Core 2] Switching language to {language.upper()}")
        try:
            self._load_model(language)
        except (FileNotFoundError, RuntimeError) as e:
            print(f"[Core 2] Language switch failed, keeping {self.language.upper()}: {e}")

    # --------------------------------------------------
    # Helper
    # --------------------------------------------------
    def _packet(self, success: bool, text, error, timed_out: bool) -> dict:
        return {
            "success": success,
            "text": text,
            "language": self.language,
            "error": error,
            "timed_out": timed_out,
        }


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    stt = Core2STT(language="en", listen_timeout=8.0)

    packet = stt.listen()

    if packet["success"]:
        print(f"You said: {packet['text']}")
    elif packet["timed_out"]:
        print("No speech detected within timeout.")
    else:
        print(f"STT failed: {packet['error']}")

    # Example: switching to Hindi for the next command
    stt.switch_language("hi")
    packet_hi = stt.listen()
    print(packet_hi)