# cores/core_6.py
# Core 6 - Speech to Text (Primary Pipeline STT) — Hardened

import os
import json
import wave
from vosk import Model, KaldiRecognizer


class Core6SpeechToText:
    """
    Phase 2 – Core 6 (Hardened) — PRIMARY PIPELINE STT
    -----------------------------------------------------
    This is the main STT engine for the Core 1 -> 11 -> 6 -> 3 -> 4
    pipeline. Takes Core 11's packet (audio_path + is_valid), runs
    both EN and HI models, and picks the more likely language using
    real word-level confidence instead of raw word count.

    (See Core 2 for the secondary/supportive live-streaming STT,
    used for quick follow-ups rather than the main pipeline.)
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

        try:
            self.en_model = Model(en_model_path)
            self.hi_model = Model(hi_model_path)
        except Exception as e:
            raise RuntimeError(f"[Core 6] Failed to load models: {e}")

        print("[Core 6] Initialized (Phase 2 – EN + HI, Hardened)")

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def process(self, packet: dict) -> dict:
        """
        Takes Core 11's packet and returns an enriched packet.

        Adds to packet:
        {
            "success": bool,
            "text": str | None,
            "language": str | None,
            "stt_confidence": float,
            "error": str | None
        }
        """

        if not packet.get("is_valid", False):
            # Audio rejected upstream (too quiet/noisy) — don't attempt STT
            packet["success"] = False
            packet["text"] = None
            packet["language"] = None
            packet["stt_confidence"] = 0.0
            packet["error"] = "Audio marked invalid by Core 11 (noise/confidence check)"
            print("[Core 6] Skipped — audio not valid")
            return packet

        audio_path = packet.get("audio_path")

        if not audio_path or not os.path.exists(audio_path):
            packet["success"] = False
            packet["text"] = None
            packet["language"] = None
            packet["stt_confidence"] = 0.0
            packet["error"] = f"Audio file not found: {audio_path}"
            print(f"[Core 6] ERROR — {packet['error']}")
            return packet

        try:
            en_text, en_conf = self._transcribe(audio_path, self.en_model)
            hi_text, hi_conf = self._transcribe(audio_path, self.hi_model)
        except Exception as e:
            packet["success"] = False
            packet["text"] = None
            packet["language"] = None
            packet["stt_confidence"] = 0.0
            packet["error"] = f"Transcription failed: {e}"
            print(f"[Core 6] ERROR — {packet['error']}")
            return packet

        # ---- Decide language using real confidence, not word count ----
        if not en_text and not hi_text:
            packet["success"] = False
            packet["text"] = None
            packet["language"] = None
            packet["stt_confidence"] = 0.0
            packet["error"] = "No speech recognized in either language"
            print("[Core 6] No speech recognized")
            return packet

        if en_conf >= hi_conf:
            packet["text"] = en_text
            packet["language"] = "en"
            packet["stt_confidence"] = en_conf
        else:
            packet["text"] = hi_text
            packet["language"] = "hi"
            packet["stt_confidence"] = hi_conf

        packet["success"] = True
        packet["error"] = None

        print(
            f"[Core 6] STT -> {packet['language'].upper()} | "
            f"text='{packet.get('text', '')}' | "
            f"confidence={packet['stt_confidence']:.2f}"
        )

        return packet

    # --------------------------------------------------
    # Internal helper
    # --------------------------------------------------
    def _transcribe(self, audio_path: str, model: Model):
        """
        Transcribes audio and returns (text, confidence).
        Confidence is the AVERAGE of Vosk's per-word confidence scores
        (real acoustic confidence), not a word-count proxy.
        Falls back gracefully if word-level conf data isn't available.
        """
        wf = None
        try:
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

            # ---- Real confidence: average per-word "conf" score ----
            word_entries = result.get("result", [])
            if word_entries:
                confidences = [w.get("conf", 0.0) for w in word_entries]
                confidence = sum(confidences) / len(confidences)
            elif text:
                # Model returned text but no word-level data —
                # treat as low-moderate confidence rather than 0.
                confidence = 0.3
            else:
                confidence = 0.0

            return text, confidence

        finally:
            if wf is not None:
                wf.close()


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    stt = Core6SpeechToText(
        en_model_path="models/vosk-model-en-us-0.22",
        hi_model_path="models/vosk-model-hi-0.22",
    )

    # Simulating a packet from Core 11 (valid audio)
    fake_packet = {
        "audio_path": "data/recordings/2026-08-08/command_test.wav",
        "energy": 0.05,
        "timestamp": "2026-08-08_10-00-00",
        "is_valid": True,
        "confidence": 1.8,
        "noise_floor": 0.001,
    }

    result = stt.process(fake_packet)
    print(result)