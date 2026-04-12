class Core16EmotionDetector:
    """
    Phase 2 – Core 16
    -----------------
    Detects user emotional state.
    Analysis only. No expression.
    """

    def __init__(self):
        print("[Core 16] Emotion detector initialized (Phase 2)")

        self.angry_keywords = {
            "stupid", "idiot", "shut up", "hate", "angry"
        }

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def process(self, packet: dict) -> dict:
        text = packet.get("normalized_text", "")
        energy = packet.get("energy", 0.0)
        confidence = packet.get("confidence", 0.0)

        emotion = "neutral"
        score = 0.6

        # ---- Angry detection ----
        if any(word in text for word in self.angry_keywords):
            emotion = "angry"
            score = 0.9

        # ---- Tired detection ----
        elif energy < 0.008 and confidence < 1.3:
            emotion = "tired"
            score = 0.75

        # ---- Focused detection ----
        elif confidence > 2.5:
            emotion = "focused"
            score = 0.8

        # ---- Calm detection ----
        elif 1.5 <= confidence <= 2.5:
            emotion = "calm"
            score = 0.7

        packet["emotion"] = emotion
        packet["emotion_confidence"] = round(score, 2)

        print(
            f"[Core 16] Emotion -> {emotion} "
            f"(confidence={packet['emotion_confidence']})"
        )

        return packet