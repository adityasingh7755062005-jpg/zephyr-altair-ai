# cores/core_1.py
# Core 1 – Wake Word Engine — Hardened
# Real front door of the pipeline: listens for "Zephyr" / "Altair",
# then records the command that follows, producing the same packet
# shape Core 11 already expects.

import os
import stat
import hashlib
import queue
import json
import time
from datetime import datetime

import numpy as np
import sounddevice as sd
import soundfile as sf

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except Exception:
    VOSK_AVAILABLE = False


WAKE_WORDS = {"zephyr": "male", "altair": "female"}
MODEL_PATH = os.path.join("vosk-model", "vosk-model-small-en-us-0.15")
SAMPLE_RATE = 16000
RECORDING_DIR = os.path.join("data", "recordings")


class Core1WakeWordEngine:
    """
    Phase 2 – Core 1 (Hardened)
    ------------------------------
    Responsibility:
    - Continuously listen for the wake words "Zephyr" / "Altair"
    - Once triggered, record the following command
    - Return the SAME packet shape the original Core 1 produced,
      so Core 11 onward needs no changes

    CRITICAL FIX: original had `def _init_` (single underscores) —
    this is NOT the Python constructor and was never called
    automatically. Fixed to `__init__` here.
    """

    def __init__(
        self,
        model_path: str = MODEL_PATH,
        sample_rate: int = SAMPLE_RATE,
        recording_dir: str = RECORDING_DIR,
        command_seconds: float = 5.0,
    ):
        print("[Core 1] Initializing wake word engine...")

        self.sample_rate = sample_rate
        self.recording_dir = recording_dir
        self.command_seconds = command_seconds
        self.online = False
        self.audio_queue = queue.Queue()  # instance-level, not global —
        # avoids the original's shared module-level queue, which would
        # have broken if more than one engine instance ever existed

        os.makedirs(self.recording_dir, exist_ok=True)
        self._restrict_permissions(self.recording_dir)

        print("VOSK_AVAILABLE =", VOSK_AVAILABLE)
        print("MODEL_PATH =", model_path)
        print("Model directory exists:", os.path.isdir(model_path))

        if VOSK_AVAILABLE and os.path.isdir(model_path):
            try:
                print("[Core 1] Loading Vosk model...")
                self.model = Model(model_path)
                grammar = json.dumps(list(WAKE_WORDS.keys()))
                self.recognizer = KaldiRecognizer(self.model, sample_rate, grammar)
                self.online = True
                print("[Core 1] ONLINE")
            except Exception as e:
                print(f"[Core 1] Error loading model: {e!r}")
                self.online = False
        else:
            print("[Core 1] OFFLINE (model missing)")
            self.online = False

        self.stream = None
        try:
            print("[Core 1] Starting microphone stream...")
            self.stream = sd.InputStream(
                channels=1,
                samplerate=sample_rate,
                dtype="int16",
                callback=self._audio_callback,
            )
            self.stream.start()
            print("[Core 1] Microphone stream started")
        except Exception as e:
            print(f"[Core 1] Failed to start microphone: {e!r}")
            self.stream = None
            self.online = False

    # --------------------------------------------------
    # Microphone callback (bound to this instance now)
    # --------------------------------------------------
    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[Core 1] Stream status: {status}")
        self.audio_queue.put(bytes(indata))

    # --------------------------------------------------
    # Wake word listener — call this in a loop
    # --------------------------------------------------
    def listen(self, poll_timeout: float = 1.0):
        """
        Pulls the next queued audio chunk and checks it against the
        wake-word grammar. Returns "zephyr", "altair", or None.
        Non-blocking beyond poll_timeout, so it can never hang forever
        if the microphone stops producing audio.
        """
        if not self.online:
            return None

        try:
            data = self.audio_queue.get(timeout=poll_timeout)
        except queue.Empty:
            return None

        try:
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "").strip().lower()
                if text in WAKE_WORDS:
                    print(f"[Core 1] Wake word detected: {text}")
                    return text
        except Exception as e:
            print(f"[Core 1] Recognizer error: {e}")

        return None

    # --------------------------------------------------
    # Record the command following a wake word
    # --------------------------------------------------
    def record_command(self, persona: str = None) -> dict:
        """
        Records for command_seconds after a wake word fires.
        Returns the SAME packet shape as the original hardened Core 1
        (success/audio_path/energy/timestamp/checksum/error), plus
        persona info, so Core 11 works unchanged.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        try:
            day_folder = os.path.join(self.recording_dir, datetime.now().strftime("%Y-%m-%d"))
            os.makedirs(day_folder, exist_ok=True)
            self._restrict_permissions(day_folder)

            audio_path = os.path.join(day_folder, f"command_{timestamp}.wav")

            print(f"[Core 1] Recording command ({self.command_seconds}s)...")
            frames = []
            start = time.time()

            while time.time() - start < self.command_seconds:
                try:
                    data = self.audio_queue.get(timeout=0.5)
                    frames.append(data)
                except queue.Empty:
                    continue  # keep waiting for the remaining time,
                    # never blocks past 0.5s on any single read

            if not frames:
                return self._error_packet(timestamp, "No audio captured")

            audio_bytes = b"".join(frames)
            arr = np.frombuffer(audio_bytes, dtype=np.int16)

            # Same energy metric as the original Core 1 (mean abs
            # amplitude, normalized to 0-1 scale)
            energy = float(np.mean(np.abs(arr.astype(np.float32) / 32768.0)))

            sf.write(audio_path, arr, self.sample_rate)
            self._restrict_permissions_file(audio_path)
            checksum = self._file_checksum(audio_path)

            packet = {
                "success": True,
                "audio_path": audio_path,
                "energy": energy,
                "timestamp": timestamp,
                "persona": persona,
                "persona_gender": WAKE_WORDS.get(persona) if persona else None,
                "checksum": checksum,
                "error": None,
            }

            print(f"[Core 1] Command saved: {audio_path} (persona={persona})")
            return packet

        except Exception as e:
            return self._error_packet(timestamp, str(e))

    # --------------------------------------------------
    # Cleanup
    # --------------------------------------------------
    def stop(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print(f"[Core 1] Error stopping stream: {e}")

    # --------------------------------------------------
    # Helpers (same hardening pattern as the original Core 1)
    # --------------------------------------------------
    def _restrict_permissions(self, path: str):
        try:
            os.chmod(path, stat.S_IRWXU)
        except (PermissionError, NotImplementedError, OSError):
            pass

    def _restrict_permissions_file(self, path: str):
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except (PermissionError, NotImplementedError, OSError):
            pass

    def _file_checksum(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _error_packet(self, timestamp: str, error_msg: str) -> dict:
        print(f"[Core 1] ERROR: {error_msg}")
        return {
            "success": False, "audio_path": None, "energy": None,
            "timestamp": timestamp, "persona": None, "persona_gender": None,
            "checksum": None, "error": error_msg,
        }


# --------------------------------------------------
# Example usage — the real wake-word loop
# --------------------------------------------------
if __name__ == "__main__":
    engine = Core1WakeWordEngine()

    print("Say 'Zephyr' or 'Altair'...")
    try:
        while True:
            persona = engine.listen()
            if persona:
                packet = engine.record_command(persona=persona)
                print(packet)
    except KeyboardInterrupt:
        engine.stop()