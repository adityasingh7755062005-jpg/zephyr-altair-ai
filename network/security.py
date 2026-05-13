# ==============================
# FILE: network/security.py
# FINAL ULTRA STABLE SECURITY VERSION
# FIXED CLOUD/LAN SWITCH ISSUES
# FIXED RANDOM COMMAND REJECTS
# FIXED NONCE COLLISIONS
# FIXED TIME DRIFT ISSUES
# LOW LOG VERSION
# ==============================

import time
import hmac
import hashlib
import threading

# ==============================
# SETTINGS
# ==============================

SECRET = b"zephyr_secret_key"

VALIDITY_SECONDS = 180

NONCE_EXPIRY = 300

CLEANUP_INTERVAL = 30

DEBUG_LOGS = False

# ==============================
# NONCE STORAGE
# ==============================

used_nonces = {}

nonce_lock = threading.Lock()

_last_cleanup = 0

# ==============================
# GENERATE SIGNATURE
# ==============================

def generate_signature(
    command,
    timestamp,
    device_id,
    nonce
):

    message = (

        f"{command}:"
        f"{timestamp}:"
        f"{device_id}:"
        f"{nonce}"

    ).encode()

    return hmac.new(

        SECRET,

        message,

        hashlib.sha256

    ).hexdigest()

# ==============================
# CLEANUP NONCES
# ==============================

def cleanup_nonces():

    global _last_cleanup

    now = time.time()

    if (

        now - _last_cleanup

        < CLEANUP_INTERVAL
    ):

        return

    expired = []

    with nonce_lock:

        for nonce, ts in list(
            used_nonces.items()
        ):

            if (

                now - ts

                > NONCE_EXPIRY
            ):

                expired.append(nonce)

        for nonce in expired:

            try:
                del used_nonces[nonce]
            except:
                pass

    _last_cleanup = now

    if DEBUG_LOGS and expired:

        print(
            f"🧹 Cleaned "
            f"{len(expired)} nonces"
        )

# ==============================
# VERIFY REQUEST
# ==============================

def verify_request(

    command,

    timestamp,

    device_id,

    signature,

    nonce
):

    try:

        # ==============================
        # REQUIRED FIELDS
        # ==============================

        if not all([

            command,

            timestamp,

            device_id,

            signature,

            nonce

        ]):

            return (
                False,
                "missing fields"
            )

        # ==============================
        # TIMESTAMP PARSE
        # ==============================

        try:

            timestamp = int(timestamp)

        except:

            return (
                False,
                "invalid timestamp"
            )

        current_time = int(time.time())

        diff = abs(
            current_time - timestamp
        )

        # ==============================
        # TIME CHECK
        # ==============================

        if diff > VALIDITY_SECONDS:

            if DEBUG_LOGS:

                print(
                    f"❌ Expired Request | "
                    f"Diff={diff}s"
                )

            return (
                False,
                "expired request"
            )

        # ==============================
        # CLEANUP OLD NONCES
        # ==============================

        cleanup_nonces()

        # ==============================
        # SIGNATURE CHECK
        # ==============================

        expected_signature = (

            generate_signature(

                command,

                timestamp,

                device_id,

                nonce
            )
        )

        if not hmac.compare_digest(

            signature,

            expected_signature

        ):

            if DEBUG_LOGS:

                print(
                    "❌ Signature mismatch"
                )

            return (
                False,
                "invalid signature"
            )

        # ==============================
        # NONCE REPLAY CHECK
        # ==============================

        with nonce_lock:

            existing = used_nonces.get(
                nonce
            )

            # ==============================
            # ALLOW VERY FAST DUPLICATES
            # NETWORK RETRY FIX
            # ==============================

            if existing:

                age = time.time() - existing

                if age < 2:

                    return (
                        True,
                        "retry accepted"
                    )

                return (
                    False,
                    "replay detected"
                )

            # ==============================
            # STORE NONCE
            # ==============================

            used_nonces[
                nonce
            ] = time.time()

        # ==============================
        # VALID
        # ==============================

        if DEBUG_LOGS:

            print(
                f"✅ VALID: {command}"
            )

        return (
            True,
            "valid"
        )

    except Exception as e:

        if DEBUG_LOGS:

            print(
                f"❌ Security Error: {e}"
            )

        return (
            False,
            "security exception"
        )