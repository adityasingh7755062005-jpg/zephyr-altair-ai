import os
import queue
import json
import time
from datetime import datetime

import numpy as np
import sounddevice as sd
import soundfile as sf

# Try to import Vosk
try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except:
    VOSK_AVAILABLE = False


# ---- SETTINGS ----
WAKE_WORDS = {"zephyr": "male", "altair": "female"}

MODEL_PATH = os.path.join("vosk-model", "vosk-model-small-en-us-0.15")
SAMPLE_RATE = 16000

RECORDING_DIR = os.path.join("data", "recordings")
os.makedirs(RECORDING_DIR, exist_ok=True)

audio_queue = queue.Queue()


# Microphone callback
def audio_callback(indata, frames, time_info, status):
    audio_queue.put(bytes(indata))


class Core1WakeWordEngine:
    def _init_(self):
        print("Core 1 initializing...")

        self.online = False  # important default

        print("VOSK_AVAILABLE =", VOSK_AVAILABLE)
        print("MODEL_PATH =", MODEL_PATH)
        print("Model directory exists:", os.path.isdir(MODEL_PATH))

        # Load Vosk model
        if VOSK_AVAILABLE and os.path.isdir(MODEL_PATH):
            try:
                print("Loading Vosk model...")
                self.model = Model(MODEL_PATH)

                grammar = json.dumps(list(WAKE_WORDS.keys()))
                self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE, grammar)

                self.online = True
                print("Core 1 is ONLINE.")

            except Exception as e:
                print("Error loading model:", repr(e))
                self.online = False
        else:
            print("Core 1 OFFLINE (model missing).")
            self.online = False

        # Start microphone stream
        try:
            print("Starting microphone stream...")
            self.stream = sd.InputStream(
                channels=1,
                samplerate=SAMPLE_RATE,
                dtype="int16",
                callback=audio_callback
            )
            self.stream.start()
            print("Microphone stream started.")

        except Exception as e:
            print("Failed to start microphone stream:", repr(e))
            self.stream = None
            self.online = False


    # Wake word listener
    def listen(self):
        if not self.online:
            return None

        data = audio_queue.get()
        if self.recognizer.AcceptWaveform(data):
            result = json.loads(self.recognizer.Result())
            text = result.get("text", "").strip().lower()

            if text in WAKE_WORDS:
                return text

        return None


    # Record voice command after wake word
    def record_command(self):
        print("Listening for command…")

        frames = []
        start = time.time()

        while time.time() - start < 5:
            data = audio_queue.get()
            frames.append(data)

        audio = b"".join(frames)
        arr = np.frombuffer(audio, dtype=np.int16)

        filename = os.path.join(
            RECORDING_DIR,
            f"command_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        )

        sf.write(filename, arr, SAMPLE_RATE)
        print("Command saved:", filename)

        return filename