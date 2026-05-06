import time
import hmac
import hashlib

SECRET = b"zephyr_secret_key"
VALIDITY_SECONDS = 120


def generate_signature(command, timestamp, device_id):
    message = f"{command}:{timestamp}:{device_id}".encode()
    return hmac.new(SECRET, message, hashlib.sha256).hexdigest()


def verify_request(command, timestamp, device_id, signature):
    try:
        timestamp = int(timestamp)
    except:
        return False, "invalid timestamp"

    # 1. Check time validity (120 sec)
    current_time = int(time.time())
    if abs(current_time - timestamp) > VALIDITY_SECONDS:
        return False, "expired (over 120s)"

    # 2. Recreate signature
    expected = generate_signature(command, timestamp, device_id)

    if not hmac.compare_digest(signature, expected):
        return False, "invalid signature"

    return True, "valid"