# diagnose_thinking.py
#
# Dumps the RAW response from LM Studio so we can see exactly where
# those tokens are going, instead of guessing. Run this from your
# project root with LM Studio's server running.

import json
import requests

BASE_URL = "http://localhost:1234/v1"
MODEL = "qwen/qwen3.5-4b"   # change if your model id differs


def probe(label, payload_extra=None):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "What is the capital of France? One short sentence."}
        ],
        "max_tokens": 800,
        "temperature": 0.7,
        "stream": False,
    }
    if payload_extra:
        payload.update(payload_extra)

    print("=" * 65)
    print(f"  {label}")
    print("=" * 65)

    try:
        r = requests.post(f"{BASE_URL}/chat/completions", json=payload, timeout=120)
    except Exception as e:
        print(f"Request failed: {e}")
        return

    if r.status_code != 200:
        print(f"HTTP {r.status_code}: {r.text[:300]}")
        return

    data = r.json()
    message = data["choices"][0]["message"]
    usage = data.get("usage", {}) or {}

    print(f"\nFields present in message: {list(message.keys())}")

    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or ""

    print(f"\ncontent           : {len(content)} chars")
    print(f"reasoning_content : {len(reasoning)} chars")
    print(f"completion_tokens : {usage.get('completion_tokens')}")

    print(f"\n--- content ---\n{content[:400]}")

    if reasoning:
        print(f"\n--- reasoning_content (first 400 chars) ---\n{reasoning[:400]}")
        print("\n>>> THINKING IS STILL HAPPENING. The template fix didn't take effect.")
    else:
        print("\n>>> No reasoning_content — thinking is genuinely OFF. ✅")

    print()


if __name__ == "__main__":
    print("\nChecking what LM Studio actually returns...\n")

    # 1. Exactly what Core 23 sends today
    probe("A: chat_template_kwargs enable_thinking=False (what Core 23 sends)",
          {"chat_template_kwargs": {"enable_thinking": False}})

    # 2. Nothing at all — relies purely on your edited template
    probe("B: nothing passed (relies only on the edited jinja template)")

    # 3. Explicitly asking it TO think, for comparison
    probe("C: enable_thinking=True (should clearly show thinking)",
          {"chat_template_kwargs": {"enable_thinking": True}})

    print("=" * 65)
    print("  WHAT THIS TELLS US")
    print("=" * 65)
    print("If A and B show NO reasoning_content -> template fix worked,")
    print("   and the leftover tokens are just the model being verbose.")
    print("If A and B DO show reasoning_content -> the edited template")
    print("   isn't being used. Likely it didn't save, or the model")
    print("   needs a full unload + reload rather than just a restart.")
    print("If C looks identical to A and B -> LM Studio is ignoring the")
    print("   template entirely and we need a different approach.")