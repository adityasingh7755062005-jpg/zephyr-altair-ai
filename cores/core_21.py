# cores/core_21.py
# Core 21 - Communication Layer
#
# The "secretary" for every other core — two jobs:
#
# 1. ASK/ANSWER: a generic, reusable version of the "ask a question,
#    wait for a reply, handle a timeout" pattern that Core 10, Core 17,
#    and Core 19 each currently reimplement separately. Other cores
#    call ask() and get notified when answer() resolves it (or when
#    it silently expires).
#
# 2. DELIVER: other cores say WHAT needs to reach the user and how
#    urgent it is — Core 21 decides WHICH channel (voice, phone push,
#    freeze overlay) actually carries it, so callers never need to
#    know how any specific channel works.
#
# Channels are registered via dependency injection (register_channel),
# not imported directly — this keeps Core 21 fully testable standalone,
# same principle as Core 19/20. The real orchestrator wires in the
# actual voice/push/overlay functions once everything is assembled;
# in isolation, tests just register simple stand-in functions.

import time


class Core21CommunicationLayer:
    """
    Phase 2 - Core 21
    -------------------
    Responsibility:
    - Track pending questions asked by any other core, resolve them
      when a reply comes in, and expire them safely if nothing does
    - Route outgoing messages to the right delivery channel based on
      urgency, without the caller needing to know how that channel works
    """

    def __init__(self):
        print("[Core 21] Communication layer initialized")
        self.pending_questions = {}  # question_id -> {question_text, asked_at, timeout_seconds, on_answer}
        self.channel_handlers = {}   # channel_name -> callable(message, **kwargs)

    # ==========================
    # CHANNEL REGISTRATION (dependency injection)
    # ==========================
    def register_channel(self, channel_name: str, handler_fn):
        """Lets the real orchestrator wire in actual voice/push/overlay
        functions later without Core 21 importing Core 7 or cloud_client
        directly. In isolation, tests register simple stand-ins instead."""
        self.channel_handlers[channel_name] = handler_fn
        print(f"[Core 21] Channel registered: '{channel_name}'")

    # ==========================
    # ASK / ANSWER
    # ==========================
    def ask(self, question_id: str, question_text: str, timeout_seconds: int = 90, on_answer=None) -> dict:
        """Registers a pending question. on_answer, if given, is called
        once with the resolution — either a real answer or an expiry."""
        self.pending_questions[question_id] = {
            "question_text": question_text,
            "asked_at": time.time(),
            "timeout_seconds": timeout_seconds,
            "on_answer": on_answer,
        }
        print(f"[Core 21] Asked '{question_id}': {question_text}")
        return {"success": True, "question_id": question_id}

    def answer(self, question_id: str, reply_text: str) -> dict:
        """Called when a reply for this question comes in from
        wherever it was actually asked (voice, phone, etc.)."""
        self._expire_stale_questions()

        pending = self.pending_questions.get(question_id)
        if not pending:
            return {"success": False, "message": "No matching pending question (it may have expired)"}

        del self.pending_questions[question_id]
        interpretation = self._interpret_reply(reply_text)

        result = {
            "success": True,
            "question_id": question_id,
            "interpretation": interpretation,  # "yes" | "no" | "unclear"
            "raw_reply": reply_text,
        }

        print(f"[Core 21] Answered '{question_id}': {interpretation} (raw: '{reply_text}')")

        if pending["on_answer"]:
            pending["on_answer"](result)

        return result

    def has_pending(self, question_id: str) -> bool:
        self._expire_stale_questions()
        return question_id in self.pending_questions

    def _expire_stale_questions(self):
        now = time.time()
        expired_ids = [
            qid for qid, q in self.pending_questions.items()
            if now - q["asked_at"] > q["timeout_seconds"]
        ]
        for qid in expired_ids:
            pending = self.pending_questions.pop(qid)
            age = round(now - pending["asked_at"])
            print(f"[Core 21] Question '{qid}' expired after {age}s with no answer")
            if pending["on_answer"]:
                pending["on_answer"]({
                    "success": False,
                    "question_id": qid,
                    "interpretation": "expired",
                    "raw_reply": None,
                })

    CONFIRM_WORDS = {"yes", "yeah", "yep", "confirm", "sure", "ok", "okay"}
    CANCEL_WORDS = {"no", "nope", "cancel", "stop", "dont", "don't", "abort"}

    def _interpret_reply(self, reply_text: str) -> str:
        words = set(reply_text.lower().strip().split())
        if words & self.CONFIRM_WORDS:
            return "yes"
        if words & self.CANCEL_WORDS:
            return "no"
        return "unclear"

    # ==========================
    # DELIVER
    # ==========================
    def deliver(self, message: str, channel: str = "auto", urgent: bool = False, **kwargs) -> dict:
        """Delivers a message via the right channel. 'auto' picks
        phone_push for urgent messages, voice otherwise — callers
        don't need to make that call themselves."""
        if channel == "auto":
            channel = "phone_push" if urgent else "voice"

        handler = self.channel_handlers.get(channel)
        if not handler:
            return {"success": False, "message": f"No handler registered for channel '{channel}'"}

        try:
            handler(message, **kwargs)
            print(f"[Core 21] Delivered via '{channel}': {message}")
            return {"success": True, "channel": channel}
        except Exception as e:
            return {"success": False, "message": f"Delivery via '{channel}' failed: {e}"}


# --------------------------------------------------
# Example usage — run this file directly to test Core 21 by itself,
# same pattern as every other core. Registers simple stand-in
# channels since the real voice/push functions don't exist here.
# --------------------------------------------------
if __name__ == "__main__":
    core21 = Core21CommunicationLayer()

    # ---- Register stand-in channels (real ones get wired in later) ----
    def fake_voice(message, **kwargs):
        print(f"    🔊 [FAKE VOICE] Zephyr would say: \"{message}\"")

    def fake_phone_push(message, **kwargs):
        print(f"    📱 [FAKE PHONE PUSH] Notification would show: \"{message}\"")

    core21.register_channel("voice", fake_voice)
    core21.register_channel("phone_push", fake_phone_push)

    # ---- Deliver demo ----
    print("\n--- Deliver ---")
    core21.deliver("Volume set to 50%", channel="voice")
    core21.deliver("Self-upgrade needs your confirmation", channel="phone_push")
    core21.deliver("Routine update applied", urgent=False)  # auto -> voice
    core21.deliver("Urgent: unauthorized access attempt", urgent=True)  # auto -> phone_push
    print(core21.deliver("test", channel="carrier_pigeon"))  # unregistered channel

    # ---- Ask/answer demo — this is what Core 19 would delegate to ----
    print("\n--- Ask / Answer: real reply ---")
    received_results = []

    def on_answer(result):
        received_results.append(result)
        print(f"    -> Callback fired with: {result}")

    core21.ask("demo-q1", "Are you sure you want to exit?", timeout_seconds=90, on_answer=on_answer)
    print("Pending?", core21.has_pending("demo-q1"))
    core21.answer("demo-q1", "yes go ahead")
    print("Pending after answer?", core21.has_pending("demo-q1"))
    print("Callback received:", received_results[-1])

    # ---- Ask/answer demo — unclear reply ----
    print("\n--- Ask / Answer: unclear reply ---")
    core21.ask("demo-q2", "Confirm restart?", timeout_seconds=90)
    result = core21.answer("demo-q2", "what's the weather like")
    print("Result for unclear reply:", result)

    # ---- Ask/answer demo — timeout, no callback fires until checked ----
    print("\n--- Ask / Answer: timeout ---")
    core21.ask("demo-q3", "A question nobody answers", timeout_seconds=90, on_answer=on_answer)
    core21.pending_questions["demo-q3"]["asked_at"] -= 95  # simulate 95s passing
    print("Pending before expiry check?", "demo-q3" in core21.pending_questions)
    print("Pending after expiry check?", core21.has_pending("demo-q3"))
    print("Callback received on expiry:", received_results[-1])

    print("\nDemo complete.")