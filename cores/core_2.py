# cores/core_2.py
# Core 2 - Speech to Text (English + Hindi)

import queue
import json
import sounddevice as sd
from vosk import Model, KaldiRecognizer

EN_MODEL_PATH = "models/vosk-model-en-us-0.22"
HI_MODEL_PATH = "models/vosk-model-hi-0.22"


class Core2STT:
    def __init__(self, language="en"):
        print("[Core 2] Initializing STT...")
        self.language = language
        self.audio_queue = queue.Queue()

        if language == "hi":
            print("[Core 2] Loading Hindi Vosk model...")
            self.model = Model(HI_MODEL_PATH)
        else:
            print("[Core 2] Loading English Vosk model...")
            self.model = Model(EN_MODEL_PATH)

        self.recognizer = KaldiRecognizer(self.model, 16000)

    def callback(self, indata, frames, time, status):
        if status:
            print(status)
        self.audio_queue.put(bytes(indata))

    def listen(self):
        print(f"[Core 2] Listening ({self.language.upper()})... Speak now")

        with sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=self.callback
        ):
            while True:
                data = self.audio_queue.get()
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").strip()

                    if text:
                        print(f"[STT-{self.language.upper()}] {text}")
                        return text

    def switch_language(self, language):
        print(f"[Core 2] Switching language to {language.upper()}")
        self.__init__(language)