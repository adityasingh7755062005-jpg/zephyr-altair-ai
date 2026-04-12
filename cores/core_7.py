# =====================================================
# Core 7 – Voice Output
# =====================================================

class Core7VoiceOutput:
    def __init__(self, enabled=False):
        self.enabled = enabled

        if self.enabled:
            print("[Core 7] Voice output enabled")
        else:
            print("[Core 7] Voice output disabled (text-only mode)")

    def speak(self, text, language="en"):
        if not self.enabled:
            print(f"[AI TEXT OUTPUT] {text}")
            return

        # Future TTS engine will go here
        print(f"[AI VOICE OUTPUT] {text}")