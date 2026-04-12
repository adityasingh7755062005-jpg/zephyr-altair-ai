import os
import json
import wave
from vosk import Model, KaldiRecognizer


class Core6SpeechToText:
    """
    Phase 2 – Core 6
    ----------------
    Responsibilities:
    - Convert audio to text
    - Detect language (EN / HI)
    - Attach STT data to packet
    """

    def __init__(
        self,
        en_model_path: str,
        hi_model_path: str
    ):
        if not os.path.exists(en_model_path):
            raise FileNotFoundError(f"English model not found: {en_model_path}")
        if not os.path.exists(hi_model_path):
            raise FileNotFoundError(f"Hindi model not found: {hi_model_path}")

        self.en_model = Model(en_model_path)
        self.hi_model = Model(hi_model_path)

        print("[Core 6] Initialized (Phase 2 – EN + HI)")

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def process(self, packet: dict) -> dict:
        """
        Takes Core 11 packet and returns enriched packet.
        """

        if not packet.get("is_valid", False):
            # Skip STT if audio is not valid
            return packet

        audio_path = packet["audio_path"]

        en_text, en_conf = self._transcribe(audio_path, self.en_model)
        hi_text, hi_conf = self._transcribe(audio_path, self.hi_model)

        # Decide language
        if en_conf >= hi_conf:
            packet["text"] = en_text
            packet["language"] = "en"
            packet["stt_confidence"] = en_conf
        else:
            packet["text"] = hi_text
            packet["language"] = "hi"
            packet["stt_confidence"] = hi_conf

        print(
            f"[Core 6] STT -> {packet['language'].upper()} | "
            f"text='{packet.get('text', '')}'"
        )

        return packet

    # --------------------------------------------------
    # Internal helper
    # --------------------------------------------------
    def _transcribe(self, audio_path: str, model: Model):
        wf = wave.open(audio_path, "rb")
        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)

        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            rec.AcceptWaveform(data)

        result = json.loads(rec.FinalResult())
        text = result.get("text", "").strip()

        # Simple confidence proxy
        confidence = len(text.split()) if text else 0.0

        return text, confidence