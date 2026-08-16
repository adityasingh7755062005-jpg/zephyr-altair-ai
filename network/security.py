# network/security.py
# HARDENED — real per-device secrets instead of one hardcoded string

import time
import hmac
import hashlib
import threading

VALIDITY_SECONDS = 180
NONCE_EXPIRY = 300
CLEANUP_INTERVAL = 30

used_nonces = {}
nonce_lock = threading.Lock()
_last_cleanup = 0


def generate_signature(command, timestamp, device_id, nonce, secret: bytes) -> str:
    """secret is now passed in per-call — the CALLER looks up the real
    device-specific secret (from trusted_device.json) instead of this
    file holding one hardcoded value for everyone."""
    message = f"{command}:{timestamp}:{device_id}:{nonce}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def cleanup_nonces():
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < CLEANUP_INTERVAL:
        return
    with nonce_lock:
        expired = [n for n, ts in used_nonces.items() if now - ts > NONCE_EXPIRY]
        for n in expired:
            used_nonces.pop(n, None)
    _last_cleanup = now


def verify_request(command, timestamp, device_id, signature, nonce, secret: bytes):
    """Same nonce/timestamp/HMAC protections as before, but now verified
    against a REAL secret unique to the paired device, not a hardcoded
    string anyone reading the source code already knows."""
    try:
        if not all([command, timestamp, device_id, signature, nonce, secret]):
            return False, "missing fields"

        try:
            timestamp = int(timestamp)
        except (ValueError, TypeError):
            return False, "invalid timestamp"

        if abs(int(time.time()) - timestamp) > VALIDITY_SECONDS:
            return False, "expired request"

        cleanup_nonces()

        expected = generate_signature(command, timestamp, device_id, nonce, secret)
        if not hmac.compare_digest(signature, expected):
            return False, "invalid signature"

        with nonce_lock:
            existing = used_nonces.get(nonce)
            if existing:
                if time.time() - existing < 2:
                    return True, "retry accepted"
                return False, "replay detected"
            used_nonces[nonce] = time.time()

        return True, "valid"

    except Exception as e:
        return False, f"security exception: {e}"