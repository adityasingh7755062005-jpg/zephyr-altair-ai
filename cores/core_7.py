# =====================================================
# Core 7 – Voice Output — Hardened (Coqui TTS / XTTS v2)
# =====================================================

import os
import threading
import tempfile


class Core7VoiceOutput:
    """
    Phase 2 – Core 7 (Hardened) — Coqui TTS (XTTS v2)
    -----------------------------------------------------
    Responsibility:
    - Speak AI responses using Coqui's XTTS v2 model (offline,
      GPU-accelerated on this machine's RTX 4050)
    - Support both English and Hindi out of the box
    - Lazy-load the model (only loads when first needed, and only
      if Coqui TTS is actually installed) so this core never
      crashes the assistant just by existing
    - Always fall back to text output if the model, GPU, or audio
      playback fails for any reason
    - Thread-safe: speak() calls never overlap
    """

    # Coqui XTTS v2 language codes for the languages we support
    LANGUAGE_MAP = {
        "en": "en",
        "hi": "hi",
    }

    # Built-in XTTS v2 speaker used when no custom voice (speaker_wav)
    # has been provided. This lets Core 7 work immediately with zero
    # setup — swap in a speaker_wav later to switch to a cloned voice,
    # no other code changes needed.
    DEFAULT_BUILTIN_SPEAKER = "Claribel Dervla"

    def __init__(
        self,
        enabled: bool = False,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        speaker_wav: str = None,
        builtin_speaker: str = None,
    ):
        """
        speaker_wav: optional path to a reference voice sample (for
        voice cloning) — use this if you want Zephyr to speak in a
        specific/cloned voice (e.g. your own).

        builtin_speaker: optional name of one of XTTS v2's built-in
        speakers. If neither speaker_wav nor builtin_speaker is given,
        DEFAULT_BUILTIN_SPEAKER is used automatically — so Core 7 works
        out of the box with no recording required.

        You can list all available built-in speakers after the model
        loads via: core7.list_builtin_speakers()
        """
        self.enabled = enabled
        self.model_name = model_name
        self.speaker_wav = speaker_wav
        self.builtin_speaker = builtin_speaker or self.DEFAULT_BUILTIN_SPEAKER

        self._lock = threading.Lock()
        self._tts_engine = None          # loaded lazily
        self._device = None              # "cuda" or "cpu"
        self._load_attempted = False
        self._load_failed_reason = None

        if self.enabled:
            mode = "cloned voice" if self.speaker_wav else f"built-in voice ('{self.builtin_speaker}')"
            print(f"[Core 7] Voice output enabled (Coqui XTTS v2, {mode} — loads on first use)")
        else:
            print("[Core 7] Voice output disabled (text-only mode)")

    # --------------------------------------------------
    # Lazy model loading
    # --------------------------------------------------
    def _ensure_loaded(self) -> bool:
        """Loads the TTS model on first use. Returns True if ready to use."""
        if self._tts_engine is not None:
            return True

        if self._load_attempted:
            # Already tried and failed earlier — don't retry every call
            return False

        self._load_attempted = True

        try:
            import torch
            from TTS.api import TTS
        except ImportError as e:
            self._load_failed_reason = (
                f"Coqui TTS not installed ({e}). "
                f"Run: pip install TTS torch"
            )
            print(f"[Core 7] WARNING: {self._load_failed_reason}")
            return False

        try:
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[Core 7] Loading XTTS v2 on device: {self._device} "
                  f"(this may take a while on first run)...")

            self._tts_engine = TTS(self.model_name).to(self._device)

            print("[Core 7] XTTS v2 loaded successfully")
            return True

        except Exception as e:
            self._load_failed_reason = f"Failed to load XTTS v2: {e}"
            print(f"[Core 7] ERROR: {self._load_failed_reason}")
            self._tts_engine = None
            return False

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def speak(self, text: str, language: str = "en") -> bool:
        """
        Speaks the given text via Coqui XTTS v2.
        Returns True if real voice output succeeded, False if it
        fell back to text output (for ANY reason — missing package,
        no GPU/model, playback error, invalid input, etc).
        """

        # ---- Validate input ----
        if not text or not isinstance(text, str) or not text.strip():
            print("[Core 7] Skipped — empty or invalid text")
            return False

        text = text.strip()
        lang_code = self.LANGUAGE_MAP.get(language, "en")
        if language not in self.LANGUAGE_MAP:
            print(f"[Core 7] Unsupported language '{language}', defaulting to English")

        # ---- Text-only mode: skip straight to fallback ----
        if not self.enabled:
            print(f"[AI TEXT OUTPUT] {text}")
            return False

        with self._lock:
            if not self._ensure_loaded():
                print(f"[AI TEXT OUTPUT] {text}")  # fallback — model unavailable
                return False

            try:
                return self._synthesize_and_play(text, lang_code)
            except Exception as e:
                print(f"[Core 7] TTS playback failed ({e}) — falling back to text")
                print(f"[AI TEXT OUTPUT] {text}")
                return False

    # --------------------------------------------------
    # Synthesis + playback
    # --------------------------------------------------
    def _synthesize_and_play(self, text: str, lang_code: str) -> bool:
        import soundfile as sf
        import sounddevice as sd

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = tmp.name

        try:
            tts_kwargs = {
                "text": text,
                "language": lang_code,
                "file_path": out_path,
            }
            if self.speaker_wav:
                tts_kwargs["speaker_wav"] = self.speaker_wav
            else:
                tts_kwargs["speaker"] = self.builtin_speaker

            self._tts_engine.tts_to_file(**tts_kwargs)

            data, samplerate = sf.read(out_path)
            print(f"[AI VOICE OUTPUT] {text}")
            sd.play(data, samplerate)
            sd.wait()
            return True

        finally:
            try:
                os.remove(out_path)
            except OSError:
                pass

    # --------------------------------------------------
    # Runtime toggle
    # --------------------------------------------------
    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        state = "enabled" if enabled else "disabled"
        print(f"[Core 7] Voice output {state}")

    def is_ready(self) -> bool:
        """Check if the real TTS engine is loaded and usable."""
        return self._tts_engine is not None

    def list_builtin_speakers(self):
        """
        Returns the list of built-in XTTS v2 speaker names you can pass
        as `builtin_speaker`. Requires the model to already be loaded
        (call speak() once first, or this triggers a load).
        """
        if not self._ensure_loaded():
            print(f"[Core 7] Can't list speakers — model not loaded ({self._load_failed_reason})")
            return []
        try:
            return list(self._tts_engine.synthesizer.tts_model.speaker_manager.speakers.keys())
        except Exception as e:
            print(f"[Core 7] Couldn't retrieve speaker list: {e}")
            return []


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    # Text-only mode (no model load at all)
    voice = Core7VoiceOutput(enabled=False)
    voice.speak("The time is 6:22 PM.")

    # Voice mode with NO speaker_wav set — works immediately using a
    # built-in XTTS voice. No recording needed to get started.
    voice2 = Core7VoiceOutput(enabled=True)
    voice2.speak("Lights turned off.", language="en")
    voice2.speak("Aapka samay ho gaya hai.", language="hi")

    # See what other built-in voices are available:
    # print(voice2.list_builtin_speakers())

    # LATER, if you want Zephyr in your own voice, just add speaker_wav
    # — nothing else about how you call speak() changes:
    # voice3 = Core7VoiceOutput(enabled=True, speaker_wav="assets/voice_reference.wav")

    # Invalid input — safely skipped
    voice2.speak("", language="en")