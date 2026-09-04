# cores/orchestrator.py
# =========================================================
# THE ORCHESTRATOR — wires all 22 cores into one live loop
# =========================================================
#
# This is the piece that was genuinely missing: every core was built
# and tested individually, but nothing ran them together as a live,
# continuous assistant. This does that.
#
# PIPELINE ORDER (confirmed from the cores' own docstrings, not guessed):
#
#   Core 1  (wake word)        -> hears "Zephyr"/"Altair", records command
#   Core 11 (noise/confidence) -> is this real speech or background noise?
#   Core 6  (STT)              -> audio file -> text (EN/HI auto-detect)
#   Core 12 (normalize)        -> strip fillers/punctuation for cleaner matching
#   Core 16 (emotion)          -> read emotional state from text + audio
#   Core 13 (attach context)   -> make last turn available for follow-ups
#   Core 3  (intent)           -> text -> intent + confidence
#   Core 4  (router)           -> decides + executes, internally calling:
#                                   Core 19 (ethics tiers)
#                                   Core 10 (behavior/dev mode)
#                                   Core 17 (personality/overwork)
#                                   Core  9 (reminders)
#                                   Core  5 (system actions)
#                                   Core  8 (all response text)
#   Core 14 (long-term memory) -> learn from this turn
#   Core 15 (knowledge)        -> track topics
#   Core  7 (voice out)        -> speak the response
#   Core 13 (record turn)      -> remember for next time's follow-ups
#
# Core 18 runs as its own always-on security system in parallel
# (started by main_app.py, not here) — it guards the machine whether
# or not anyone is talking to Zephyr. Core 20/21/22 are wired in as
# services the pipeline and Core 18 can both reach.

import os
import time
import threading
import traceback

from cores.core_1 import Core1WakeWordEngine
from cores.core_3 import Core3IntentDetector
from cores.core_4 import Core4CommandRouter
from cores.core_6 import Core6SpeechToText
from cores.core_7 import Core7VoiceOutput
from cores.core_8 import Core8ResponseEngine
from cores.core_9 import Core9Automation
from cores.core_10 import Core10BehaviorEngine
from cores.core_11 import Core11NoiseConfidenceEngine
from cores.core_12 import Core12NLPNormalizer
from cores.core_13 import Core13ContextMemory
from cores.core_14 import Core14LongTermMemory
from cores.core_15 import Core15KnowledgeEngine
from cores.core_16 import Core16EmotionDetector
from cores.core_17 import Core17PersonalityEngine
from cores.core_19 import Core19EthicsEngine
from cores.core_20 import Core20SelfUpgrade
from cores.core_21 import Core21CommunicationLayer
from cores.core_22 import Core22ThreatCorrelation, Layer

EN_MODEL_PATH = os.path.join("models", "vosk-model-en-us-0.22")
HI_MODEL_PATH = os.path.join("models", "vosk-model-hi-0.22")


class ZephyrOrchestrator:
    """
    Owns the voice pipeline and the cross-cutting services (20/21/22).
    Takes an already-running Core 18 instance so the two systems share
    one Core 5, one Core 7, and one set of security state rather than
    each spinning up their own competing copies.
    """

    def __init__(self, core18=None, voice_enabled=True):
        print("\n" + "=" * 50)
        print("🧠 Orchestrator — wiring all cores together")
        print("=" * 50)

        self.core18 = core18
        self.running = False
        self._pipeline_thread = None

        # ---- Reuse Core 18's instances where they already exist ----
        # Two Core 7 instances would mean two XTTS models loaded into
        # GPU memory (~2GB each); two Core 5 instances would mean two
        # separate sets of disk/network delta trackers producing wrong
        # readings. Sharing is correctness, not just efficiency.
        if core18:
            self.system_utils = core18.system_utils      # Core 5
            self.voice_output = core18.voice_output      # Core 7
            print("[Orchestrator] Reusing Core 18's Core 5 + Core 7 instances")
        else:
            from cores.core_5 import Core5SystemUtils
            self.system_utils = Core5SystemUtils(require_confirmation=False)
            self.voice_output = Core7VoiceOutput(enabled=voice_enabled)
            print("[Orchestrator] Standalone mode — created own Core 5 + Core 7")

        # ---- Cross-cutting services ----
        self.communication = Core21CommunicationLayer()
        self.self_upgrade = Core20SelfUpgrade()
        self.threat_layer = Core22ThreatCorrelation()

        # ---- Memory & knowledge (previously built but never called) ----
        self.long_term_memory = Core14LongTermMemory()
        self.knowledge = Core15KnowledgeEngine()
        self.context_memory = Core13ContextMemory()

        # ---- Understanding chain ----
        self.noise_engine = Core11NoiseConfidenceEngine()
        self.normalizer = Core12NLPNormalizer()
        self.emotion = Core16EmotionDetector()
        self.intent_detector = Core3IntentDetector()

        # ---- Decision & response chain ----
        self.response_engine = Core8ResponseEngine()
        self.automation = Core9Automation(voice_output=self.voice_output)
        self.behavior = Core10BehaviorEngine()
        self.personality = Core17PersonalityEngine()
        self.ethics = Core19EthicsEngine()

        self.router = Core4CommandRouter(
            system_utils=self.system_utils,
            response_engine=self.response_engine,
            automation_engine=self.automation,
            behavior_engine=self.behavior,
            personality_engine=self.personality,
            ethics_engine=self.ethics,
        )

        # ---- STT + wake word (heaviest; loaded last so any earlier
        # failure surfaces before spending time on model loading) ----
        self.stt = None
        self.wake_engine = None
        self._init_speech()

        self._register_communication_channels()
        self._register_threat_handler()

        if core18:
            # Makes cloud_client.py's confirm_upgrade/deny_upgrade
            # handlers work — they look for exactly this attribute
            # via getattr(self.core, "self_upgrade", None).
            core18.self_upgrade = self.self_upgrade
            print("[Orchestrator] Core 20 attached to Core 18 (phone upgrade confirmation now live)")

        print("=" * 50)
        print("✅ All cores wired")
        print("=" * 50 + "\n")

    # --------------------------------------------------
    def _init_speech(self):
        """Core 6 and Core 1 need real model files and a real
        microphone. If either is missing, the assistant still runs —
        it just can't hear you (text_command() still works fully)."""
        try:
            self.stt = Core6SpeechToText(EN_MODEL_PATH, HI_MODEL_PATH)
        except Exception as e:
            print(f"[Orchestrator] ⚠️ Core 6 STT unavailable: {e}")
            print("[Orchestrator]    Voice input disabled — text_command() still works")

        try:
            self.wake_engine = Core1WakeWordEngine()
            if not self.wake_engine.online:
                print("[Orchestrator] ⚠️ Core 1 offline (model or mic missing)")
        except Exception as e:
            print(f"[Orchestrator] ⚠️ Core 1 wake word unavailable: {e}")

    def _register_communication_channels(self):
        """Core 21 doesn't import Core 7 or cloud_client itself — the
        real handlers get injected here, which is exactly why Core 21
        was testable standalone with fake ones."""
        def voice_channel(message, **kwargs):
            self.voice_output.speak(message, language=kwargs.get("language", "en"))

        def phone_push_channel(message, **kwargs):
            if self.core18 and getattr(self.core18, "cloud", None):
                self.core18.cloud._push_state_change(
                    "assistant_message", {"message": message, **kwargs}
                )
            else:
                print(f"[Orchestrator] (no phone connection) would push: {message}")

        def overlay_channel(message, **kwargs):
            if self.core18:
                self.core18.freeze_overlay.show(locked=False)
            else:
                print(f"[Orchestrator] (no overlay) would show: {message}")

        self.communication.register_channel("voice", voice_channel)
        self.communication.register_channel("phone_push", phone_push_channel)
        self.communication.register_channel("overlay", overlay_channel)

    def _register_threat_handler(self):
        """Core 22's actual block action. Deliberately conservative:
        locks the machine and arms intruder detection, matching the
        existing response to any other unauthorized access."""
        def block_handler(source, layer, detail):
            print(f"[Orchestrator] 🚫 Core 22 block: {source} ({layer})")
            if self.core18:
                try:
                    self.core18.lock()
                    self.core18.intruder_detector.enable()
                except Exception as e:
                    print(f"[Orchestrator] Block action failed: {e}")

        self.threat_layer.register_block_handler(block_handler)

    # ==================================================
    # THE PIPELINE — one full turn, start to finish
    # ==================================================
    def process_text(self, text: str, language: str = "en", identity: str = "owner",
                      private_mode: bool = True) -> dict:
        """Runs everything downstream of speech recognition. Used
        directly by text_command(), and by the voice loop once Core 6
        has produced text. Keeping this separate is what makes the
        whole pipeline testable without a microphone."""
        packet = {
            "success": True,
            "text": text,
            "language": language,
            "error": None,
            "timed_out": False,
            "identity": identity,
            "private_mode": private_mode,
        }
        return self._run_understanding_and_routing(packet)

    def _run_understanding_and_routing(self, packet: dict) -> dict:
        # ---- Core 12: clean the text ----
        packet = self.normalizer.process(packet)

        # ---- Core 16: emotional state ----
        packet = self.emotion.process(packet)

        # ---- Core 13: attach last turn's context BEFORE Core 3, so
        # follow-ups like "do it again" can resolve ----
        packet = self.context_memory.attach_context(packet)

        # ---- Core 3: intent ----
        packet = self.intent_detector.process(packet)

        # ---- Core 4: decide + execute (calls 19/10/17/9/5/8 inside) ----
        result = self.router.route(packet)

        # ---- Core 14 + 15: LEARN from this turn.
        # This is the gap that existed before — both cores were fully
        # built but nothing ever called them, so the assistant never
        # actually accumulated anything across conversations. ----
        try:
            self.long_term_memory.auto_update(packet)
            intent = packet.get("intent")
            if intent and intent not in ("unknown", "none"):
                self.knowledge.auto_track(intent)
        except Exception as e:
            print(f"[Orchestrator] Memory update failed (non-fatal): {e}")

        # ---- Core 7: speak it ----
        response_text = result.get("response", "")
        if response_text:
            try:
                self.voice_output.speak(response_text, language=packet.get("language", "en"))
            except Exception as e:
                print(f"[Orchestrator] Voice output failed: {e}")
                print(f"[AI TEXT OUTPUT] {response_text}")

        # ---- Core 13: record what happened, for next turn ----
        self.context_memory.record_turn(
            text=packet.get("text", ""),
            intent=result.get("routed_intent", "none"),
            response=response_text,
        )

        return result

    def text_command(self, text: str, **kwargs) -> dict:
        """Type instead of speak — the whole pipeline minus the
        microphone. Genuinely useful: works when the mic is busy,
        when models aren't installed, and is how the pipeline gets
        tested without hardware."""
        print(f"\n[Orchestrator] Text command: '{text}'")
        return self.process_text(text, **kwargs)

    # ==================================================
    # VOICE LOOP
    # ==================================================
    def _voice_loop(self):
        print("[Orchestrator] 🎤 Listening for 'Zephyr' or 'Altair'...")

        while self.running:
            try:
                persona = self.wake_engine.listen(poll_timeout=1.0)
                if not persona:
                    continue

                print(f"[Orchestrator] Wake word: {persona}")

                # ---- Core 1: record what follows ----
                packet = self.wake_engine.record_command(persona=persona)
                if not packet.get("success"):
                    print(f"[Orchestrator] Recording failed: {packet.get('error')}")
                    continue

                # ---- Core 11: real speech, or just noise? ----
                packet = self.noise_engine.process(packet)

                # ---- Core 6: audio -> text ----
                if not self.stt:
                    print("[Orchestrator] No STT available — skipping")
                    continue
                packet = self.stt.process(packet)

                if not packet.get("success"):
                    print(f"[Orchestrator] STT failed: {packet.get('error')}")
                    continue

                packet["identity"] = "owner"
                packet["private_mode"] = True

                self._run_understanding_and_routing(packet)

            except Exception as e:
                print(f"[Orchestrator] Pipeline error: {e}")
                traceback.print_exc()
                time.sleep(1)

    def start(self):
        """Starts the voice loop in the background. Returns True if
        voice is actually available — False means text_command()
        still works but nothing is listening."""
        if not self.wake_engine or not self.wake_engine.online:
            print("[Orchestrator] ⚠️ Voice loop NOT started (wake word engine unavailable)")
            print("[Orchestrator]    text_command() still works normally")
            return False

        self.running = True
        self._pipeline_thread = threading.Thread(target=self._voice_loop, daemon=True)
        self._pipeline_thread.start()
        return True

    def stop(self):
        self.running = False
        if self.wake_engine:
            try:
                self.wake_engine.stop()
            except Exception:
                pass
        print("[Orchestrator] Stopped")