import time
import hmac
import hashlib

SECRET = b"zephyr_secret_key"
VALIDITY_SECONDS = 120

# ✅ STORE USED NONCES (nonce → timestamp)
used_nonces = {}

# ✅ CLEANUP INTERVAL CONTROL (avoid cleaning every request heavily)
_last_cleanup = 0
CLEANUP_INTERVAL = 10  # seconds


def generate_signature(command, timestamp, device_id, nonce):
    message = f"{command}:{timestamp}:{device_id}:{nonce}".encode()
    return hmac.new(SECRET, message, hashlib.sha256).hexdigest()


def cleanup_nonces():
    """Remove expired nonces to prevent memory growth"""
    global _last_cleanup

    now = time.time()

    # 🔥 Run cleanup only every few seconds (performance optimization)
    if now - _last_cleanup < CLEANUP_INTERVAL:
        return

    expired = [n for n, t in used_nonces.items() if now - t > VALIDITY_SECONDS]

    for n in expired:
        del used_nonces[n]

    _last_cleanup = now

    if expired:
        print(f"🧹 Cleaned {len(expired)} expired nonces")


def verify_request(command, timestamp, device_id, signature, nonce):

    print("\n🔐 ===== SECURITY CHECK =====")
    print(f"CMD: {command}")
    print(f"TS: {timestamp}")
    print(f"DEVICE: {device_id}")
    print(f"NONCE: {nonce}")
    print(f"SIG (received): {signature}")

    # ❌ Missing values check
    if not all([command, timestamp, device_id, signature, nonce]):
        print("❌ Missing fields")
        return False, "missing fields"

    try:
        timestamp = int(timestamp)
    except:
        print("❌ Invalid timestamp format")
        return False, "invalid timestamp"

    current_time = int(time.time())
    diff = current_time - timestamp

    print(f"⏱ Current: {current_time}")
    print(f"⏱ Diff: {diff} sec")

    # ⏱ TIME CHECK
    if abs(diff) > VALIDITY_SECONDS:
        print("❌ EXPIRED (>120s)")
        return False, "expired (over 120s)"

    # 🧹 CLEAN OLD NONCES (OPTIMIZED)
    cleanup_nonces()

    # 🔁 NONCE REPLAY CHECK
    if nonce in used_nonces:
        print("❌ REPLAY ATTACK (NONCE USED)")
        return False, "replay detected"

    # 🔐 SIGNATURE CHECK (BEFORE STORING NONCE)
    expected = generate_signature(command, timestamp, device_id, nonce)

    print(f"SIG (expected): {expected}")

    if not hmac.compare_digest(signature, expected):
        print("❌ SIGNATURE MISMATCH")
        return False, "invalid signature"

    # ✅ STORE NONCE ONLY AFTER FULL VALIDATION
    used_nonces[nonce] = time.time()

    print("✅ VALID REQUEST")
    print("🔐 ==========================\n")

    return True, "valid"