# cores/core_16.py
# Core 16 – Emotion Analysis — Hardened v2 (pretrained model + fallback)

class Core16EmotionDetector:
    """
    Phase 2 – Core 16 (Hardened v2)
    -------------------------------
    Detects user emotional state. Analysis only. No expression.

    Text emotion now uses a small pretrained model (trained offline,
    in advance, on public text by its authors) instead of a 4-word
    keyword list — genuinely better emotional intelligence without
    ever listening to or analyzing anyone else's live conversation.
    Falls back to the word-boundary-safe keyword method automatically
    if the model can't load (e.g. transformers not installed).

    Audio-based state (tired/focused/calm) is unchanged — that's a
    behavioral signal from Core 11, not something a text model helps with.

    Install (optional but recommended):
        pip install transformers torch
    First use downloads the model (~300MB) once, then works offline.
    """

    MODEL_LABEL_MAP = {
        "anger": "angry", "joy": "happy", "sadness": "sad",
        "fear": "fearful", "surprise": "surprised", "disgust": "disgusted",
        "neutral": "neutral",
    }
    ML_CONFIDENCE_THRESHOLD = 0.55  # below this, don't trust the model's guess

    def __init__(self):
        self.angry_words = {"stupid", "idiot", "hate", "angry"}
        self.angry_phrases = {"shut up"}

        self._pipeline = None
        try:
            from transformers import pipeline
            self._pipeline = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                top_k=1,
            )
            print("[Core 16] Emotion detector initialized (Hardened v2 — pretrained model)")
        except Exception as e:
            print(f"[Core 16] Pretrained emotion model unavailable ({e}) — using keyword fallback")

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def process(self, packet: dict) -> dict:
        text = (packet.get("normalized_text") or packet.get("text", "")).lower()
        energy = packet.get("energy", 0.0)
        audio_confidence = packet.get("audio_confidence", 0.0)

        text_emotion, text_score, source = self._detect_text_emotion(text)
        audio_emotion, audio_score = self._detect_audio_state(energy, audio_confidence)

        if text_emotion and text_emotion != "neutral":
            emotion, score = text_emotion, text_score
        elif audio_emotion:
            emotion, score, source = audio_emotion, audio_score, "audio_heuristic"
        else:
            emotion, score, source = "neutral", 0.6, "default"

        packet["emotion"] = emotion
        packet["emotion_confidence"] = round(score, 2)
        packet["emotion_source"] = source  # useful for debugging/trust calibration

        print(f"[Core 16] Emotion -> {emotion} (confidence={packet['emotion_confidence']}, source={source})")
        return packet

    # --------------------------------------------------
    # Text emotion: pretrained model first, keyword fallback second
    # --------------------------------------------------
    def _detect_text_emotion(self, text: str):
        if not text.strip():
            return None, 0.0, "empty"

        if self._pipeline:
            try:
                result = self._pipeline(text)[0][0]
                label = result["label"].lower()
                score = float(result["score"])
                if score >= self.ML_CONFIDENCE_THRESHOLD:
                    return self.MODEL_LABEL_MAP.get(label, label), score, "text_model"
                return "neutral", score, "text_model_low_confidence"
            except Exception as e:
                print(f"[Core 16] Model inference failed ({e}), falling back to keywords")

        # ---- Fallback: word-boundary-safe keyword matching ----
        words = set(text.split())
        is_angry = bool(words & self.angry_words) or any(p in text for p in self.angry_phrases)
        if is_angry:
            return "angry", 0.9, "keyword_fallback"
        return None, 0.0, "keyword_fallback"

    # --------------------------------------------------
    # Audio-based state (unchanged from previous hardened version)
    # --------------------------------------------------
    def _detect_audio_state(self, energy: float, audio_confidence: float):
        if energy < 0.008 and audio_confidence < 1.3:
            return "tired", 0.75
        if audio_confidence > 2.5:
            return "focused", 0.8
        if 1.5 <= audio_confidence <= 2.5:
            return "calm", 0.7
        return None, 0.0


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    detector = Core16EmotionDetector()

    print(detector.process({
        "normalized_text": "i am so happy today, this is amazing",
        "energy": 0.05, "audio_confidence": 2.0,
    }))

    print(detector.process({
        "normalized_text": "i don't know whatever you want",
        "energy": 0.05, "audio_confidence": 2.0,
    }))

    print(detector.process({
        "normalized_text": "turn off the lights",
        "energy": 0.003, "audio_confidence": 1.1,
    }))