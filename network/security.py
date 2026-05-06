import time
import hmac
import hashlib

SECRET = b"zephyr_secret_key"
VALIDITY_SECONDS = 120


def generate_signature(command, timestamp, device_id):
    message = f"{command}:{timestamp}:{device_id}".encode()
    return hmac.new(SECRET, message, hashlib.sha256).hexdigest()


def verify_request(command, timestamp, device_id, signature):

    print("\n🔐 ===== SECURITY CHECK =====")
    print(f"CMD: {command}")
    print(f"TS: {timestamp}")
    print(f"DEVICE: {device_id}")
    print(f"SIG (received): {signature}")

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

    # 🔐 SIGNATURE CHECK
    expected = generate_signature(command, timestamp, device_id)

    print(f"SIG (expected): {expected}")

    if not hmac.compare_digest(signature, expected):
        print("❌ SIGNATURE MISMATCH")
        return False, "invalid signature"

    print("✅ VALID REQUEST")
    print("🔐 ==========================\n")

    return True, "valid"