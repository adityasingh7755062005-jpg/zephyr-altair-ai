# cores/core_23.py
# Core 23 - LLM Engine (LM Studio client)
#
# Talks to a locally-running LM Studio server over its
# OpenAI-compatible API. Nothing leaves your machine.
#
# TWO-MODEL SWITCHER:
#   Primary model answers by default. Falls back to the secondary if
#   EITHER of these happens (whichever comes first):
#     1. The primary takes longer than `timeout_seconds`
#     2. The primary's answer looks like it doesn't actually know
#
# Point 2 is a HEURISTIC, not a certainty — we look for phrases like
# "I don't know" / "I'm not sure". A model can also be confidently
# wrong, which no amount of phrase-matching will catch. Treat the
# fallback as "worth a second opinion", not as error detection.
#
# Same design principles as every other core here: no hard imports of
# other cores, degrades gracefully when LM Studio isn't running, and
# fully testable standalone.

import time
import json

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False


DEFAULT_BASE_URL = "http://localhost:1234/v1"

# Phrases that suggest the model is admitting it doesn't know.
# Deliberately conservative — better to miss a fallback opportunity
# than to trigger a slow model swap on a perfectly good answer.
UNCERTAINTY_MARKERS = [
    "i don't know",
    "i do not know",
    "i'm not sure",
    "i am not sure",
    "i cannot answer",
    "i can't answer",
    "no information",
    "unable to determine",
    "i don't have",
    "i do not have",
]


class Core23LLMEngine:
    """
    Phase 3 - Core 23
    -------------------
    Responsibility:
    - Send prompts to LM Studio and return real answers
    - Fall back to a secondary model on timeout or admitted uncertainty
    - Never crash the assistant when LM Studio is closed or a model
      isn't loaded — always return a structured result instead
    """

    def __init__(
        self,
        primary_model: str,
        fallback_model: str = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: int = 30,
        max_tokens: int = 800,
        temperature: float = 0.7,
        enable_thinking: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        # Qwen3.5 is a reasoning model — left alone it generates a long
        # internal chain of thought before answering, which can turn a
        # 6-word reply into 900+ generated tokens. For a voice assistant
        # that means ~20s waits. Off by default; turn it on deliberately
        # for genuinely hard questions.
        self.enable_thinking = enable_thinking

        if not _REQUESTS_AVAILABLE:
            print("[Core 23] ⚠️ requests not installed — LLM disabled")
        else:
            print(f"[Core 23] LLM engine ready (primary: {primary_model}"
                  f"{', fallback: ' + fallback_model if fallback_model else ''})")

    # ==========================
    # AVAILABILITY
    # ==========================
    def is_available(self) -> bool:
        """Is LM Studio actually running and serving? Cheap check —
        used before trying to route a question to the LLM at all."""
        if not _REQUESTS_AVAILABLE:
            return False
        try:
            response = requests.get(f"{self.base_url}/models", timeout=3)
            return response.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list:
        """Returns the model IDs LM Studio currently reports. These are
        LM Studio's OWN identifiers, not the names on Hugging Face —
        this is how you find the exact string to configure."""
        if not _REQUESTS_AVAILABLE:
            return []
        try:
            response = requests.get(f"{self.base_url}/models", timeout=5)
            if response.status_code != 200:
                return []
            data = response.json()
            return [m.get("id") for m in data.get("data", []) if m.get("id")]
        except Exception as e:
            print(f"[Core 23] Could not list models: {e}")
            return []

    # ==========================
    # MAIN ENTRY POINT
    # ==========================
    def ask(self, prompt: str, system_prompt: str = None, use_fallback: bool = True) -> dict:
        """
        Returns:
        {
            "success": bool,
            "answer": str | None,
            "model_used": str | None,
            "elapsed_seconds": float,
            "fell_back": bool,
            "fallback_reason": str | None,   # "timeout" | "uncertain" | "error"
            "error": str | None,
        }
        """
        if not _REQUESTS_AVAILABLE:
            return self._failure("requests library not installed")

        # ---- Try the primary model ----
        result = self._call_model(self.primary_model, prompt, system_prompt)

        if result["success"]:
            if not use_fallback or not self.fallback_model:
                return result

            # Did it admit it doesn't know?
            if self._sounds_uncertain(result["answer"]):
                print(f"[Core 23] Primary sounded uncertain — trying {self.fallback_model}")
                return self._try_fallback(prompt, system_prompt, "uncertain", result)

            return result

        # ---- Primary failed. Was it a timeout, or something else? ----
        if not self.fallback_model or not use_fallback:
            return result

        reason = "timeout" if result.get("timed_out") else "error"
        print(f"[Core 23] Primary failed ({reason}) — trying {self.fallback_model}")
        return self._try_fallback(prompt, system_prompt, reason, result)

    def _try_fallback(self, prompt, system_prompt, reason, primary_result) -> dict:
        fallback_result = self._call_model(self.fallback_model, prompt, system_prompt)

        if fallback_result["success"]:
            fallback_result["fell_back"] = True
            fallback_result["fallback_reason"] = reason
            return fallback_result

        # Fallback ALSO failed. If the primary at least produced
        # something, return that rather than nothing at all — a
        # hedged answer beats no answer.
        if primary_result.get("success"):
            primary_result["fallback_reason"] = f"{reason} (fallback also failed)"
            return primary_result

        fallback_result["fell_back"] = True
        fallback_result["fallback_reason"] = reason
        return fallback_result

    # ==========================
    # THE ACTUAL CALL
    # ==========================
    def _call_model(self, model: str, prompt: str, system_prompt: str = None) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        if not self.enable_thinking:
            # ONLY the template flag. An earlier version also appended
            # "/no_think" to the message text — that was a mistake: if the
            # template doesn't recognise the token, the model just reads it
            # as part of your question and wastes tokens on it. Measured
            # result: appending it made responses SLOWER, not faster.
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        start = time.time()
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=self.timeout_seconds,
            )
            elapsed = time.time() - start

            if response.status_code != 200:
                return {
                    "success": False, "answer": None, "model_used": model,
                    "elapsed_seconds": round(elapsed, 2), "fell_back": False,
                    "fallback_reason": None, "timed_out": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                }

            data = response.json()
            message = data["choices"][0]["message"]
            answer = (message.get("content") or "").strip()

            # If thinking ate the whole token budget, content comes back
            # EMPTY while the real text sits in reasoning_content. An
            # empty answer is useless, so surface whatever the model
            # actually produced rather than returning nothing at all.
            if not answer:
                reasoning = (message.get("reasoning_content") or "").strip()
                if reasoning:
                    print("[Core 23] ⚠️ content was empty — thinking consumed the token "
                          "budget. Using reasoning text instead. Fix the jinja template "
                          "in LM Studio to stop this properly.")
                    answer = reasoning

            # Real token counts, straight from the server — this is what
            # tells you WHY something was slow instead of guessing.
            usage = data.get("usage", {}) or {}
            completion_tokens = usage.get("completion_tokens")
            prompt_tokens = usage.get("prompt_tokens")

            speed = ""
            if completion_tokens and elapsed > 0:
                speed = f" | {completion_tokens} tokens @ {completion_tokens / elapsed:.1f} tok/s"
            print(f"[Core 23] {model} answered in {elapsed:.1f}s{speed}")

            return {
                "success": True, "answer": answer, "model_used": model,
                "elapsed_seconds": round(elapsed, 2), "fell_back": False,
                "fallback_reason": None, "timed_out": False, "error": None,
                "completion_tokens": completion_tokens,
                "prompt_tokens": prompt_tokens,
            }

        except requests.exceptions.Timeout:
            elapsed = time.time() - start
            print(f"[Core 23] {model} timed out after {elapsed:.1f}s")
            return {
                "success": False, "answer": None, "model_used": model,
                "elapsed_seconds": round(elapsed, 2), "fell_back": False,
                "fallback_reason": None, "timed_out": True,
                "error": f"Timed out after {self.timeout_seconds}s",
            }

        except requests.exceptions.ConnectionError:
            return self._failure(
                "Could not reach LM Studio — is it running with the server started?",
                model=model,
            )

        except Exception as e:
            return self._failure(str(e), model=model)

    # ==========================
    # HELPERS
    # ==========================
    def _sounds_uncertain(self, answer: str) -> bool:
        if not answer:
            return True
        lowered = answer.lower()
        return any(marker in lowered for marker in UNCERTAINTY_MARKERS)

    def _failure(self, error: str, model: str = None) -> dict:
        return {
            "success": False, "answer": None, "model_used": model,
            "elapsed_seconds": 0.0, "fell_back": False,
            "fallback_reason": None, "timed_out": False, "error": error,
        }


# --------------------------------------------------
# Example usage — run this file directly to test Core 23 by itself.
# Requires LM Studio running with a model loaded.
# --------------------------------------------------
if __name__ == "__main__":
    engine = Core23LLMEngine(
        primary_model="qwen/qwen3.5-4b",   # replace with YOUR exact model id
        fallback_model=None,
        timeout_seconds=60,
    )

    print("\n--- Is LM Studio running? ---")
    available = engine.is_available()
    print(f"Available: {available}")

    if not available:
        print("\n❌ LM Studio isn't reachable.")
        print("   1. Open LM Studio")
        print("   2. Go to the Developer tab")
        print("   3. Load your model and start the server")
        print("   4. Run this file again")
        raise SystemExit(0)

    print("\n--- What models does LM Studio report? ---")
    models = engine.list_models()
    for m in models:
        print(f"  {m}")
    print("\n⚠️  Use one of the EXACT strings above as primary_model.")

    print("\n--- Simple question ---")
    result = engine.ask("What is 2 + 2? Answer in one short sentence.")
    print(f"Success: {result['success']}")
    print(f"Answer: {result['answer']}")
    print(f"Took: {result['elapsed_seconds']}s")

    print("\n--- With a system prompt (assistant personality) ---")
    result = engine.ask(
        "Who are you?",
        system_prompt="You are Zephyr, a concise personal assistant. Answer in one sentence.",
    )
    print(f"Answer: {result['answer']}")
    print(f"Took: {result['elapsed_seconds']}s | tokens: {result.get('completion_tokens')}")

    # ---- Direct comparison: thinking ON vs OFF ----
    # If the two timings differ a lot, reasoning tokens were the cause
    # of the slowness. If they're similar, something else is going on
    # and we look elsewhere.
    print("\n--- SPEED TEST: thinking OFF (default) ---")
    fast = Core23LLMEngine(primary_model=engine.primary_model, enable_thinking=False)
    r1 = fast.ask("What is the capital of France? One short sentence.")
    print(f"Answer: {r1['answer']}")
    print(f"Took: {r1['elapsed_seconds']}s | tokens: {r1.get('completion_tokens')}")

    print("\n--- SPEED TEST: thinking ON ---")
    slow = Core23LLMEngine(primary_model=engine.primary_model, enable_thinking=True,
                            timeout_seconds=120)
    r2 = slow.ask("What is the capital of France? One short sentence.")
    print(f"Answer: {r2['answer']}")
    print(f"Took: {r2['elapsed_seconds']}s | tokens: {r2.get('completion_tokens')}")

    print("\n--- VERDICT ---")
    if r1.get("completion_tokens") and r2.get("completion_tokens"):
        print(f"Thinking OFF: {r1['completion_tokens']} tokens in {r1['elapsed_seconds']}s")
        print(f"Thinking ON:  {r2['completion_tokens']} tokens in {r2['elapsed_seconds']}s")
    else:
        print("Server didn't report token counts — compare the times above instead.")