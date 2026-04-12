import os
import time
import sounddevice as sd
import soundfile as sf
import numpy as np
from datetime import datetime


class Core1MicListener:
    """
    Phase 2 – Core 1
    ----------------
    Responsibility:
    - Capture microphone audio
    - Save to disk
    - Measure raw energy
    - Return a single structured packet
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        record_seconds: float = 3.5,
        base_dir: str = "data/recordings"
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.record_seconds = record_seconds
        self.base_dir = base_dir

        os.makedirs(self.base_dir, exist_ok=True)

        print("[Core 1] Initialized (Phase 2)")

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def listen(self) -> dict:
        """
        Records a single voice segment and returns a packet.

        Returns:
        {
            "audio_path": str,
            "energy": float,
            "timestamp": str
        }
        """

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Folder per day
        day_folder = os.path.join(
            self.base_dir,
            datetime.now().strftime("%Y-%m-%d")
        )
        os.makedirs(day_folder, exist_ok=True)

        audio_path = os.path.join(day_folder, f"command_{timestamp}.wav")

        # ---- Record audio ----
        audio = sd.rec(
            int(self.record_seconds * self.sample_rate),
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32"
        )
        sd.wait()

        # ---- Save audio ----
        sf.write(audio_path, audio, self.sample_rate)

        # ---- Compute raw energy ----
        energy = float(np.mean(np.abs(audio)))

        # ---- Build packet ----
        packet = {
            "audio_path": audio_path,
            "energy": energy,
            "timestamp": timestamp
        }

        # ---- Minimal logging (allowed) ----
        print(f"[Core 1] Audio saved: {audio_path}")
        print(f"[Core 1] Energy: {energy:.5f}")

        return packet