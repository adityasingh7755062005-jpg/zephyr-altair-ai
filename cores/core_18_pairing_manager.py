# cores/core_18_pairing_manager.py
# NEW FILE — real pairing, replacing the old missing /pair endpoint

import secrets
import time
import uuid


class PairingManager:
    """
    Real device pairing, requiring PHYSICAL PROXIMITY to the laptop.

    How it works (like pairing a Bluetooth speaker or a smart TV remote):
    1. You trigger pairing mode on the laptop (voice command or hotkey,
       wired in later via Core 4). A 6-digit PIN is generated and shown
       ONLY on the laptop's own screen/console — never sent anywhere.
    2. On your phone, within 2 minutes, you enter that PIN into the app.
    3. The app sends the PIN to the laptop over your LOCAL Wi-Fi only
       (never over the internet/cloud path).
    4. If it matches, the laptop generates a brand new random device_id
       and a cryptographically random secret_key, saves them, and sends
       them back to the phone ONCE, over the same local connection.

    From that point on, the phone proves it's really your phone by using
    that secret to sign every request — not by simply stating an ID.
    """

    PIN_VALIDITY_SECONDS = 120
    MAX_FAILED_ATTEMPTS = 5

    def __init__(self, trusted_device_manager):
        self.trusted_device_manager = trusted_device_manager
        self._pending_pin = None
        self._pin_expires_at = None
        self._failed_attempts = 0

    def start_pairing(self) -> str:
        """Call this to begin pairing. Returns the PIN to display locally."""
        pin = f"{secrets.randbelow(1_000_000):06d}"
        self._pending_pin = pin
        self._pin_expires_at = time.time() + self.PIN_VALIDITY_SECONDS
        self._failed_attempts = 0  # fresh attempt count for this pairing session

        print("=" * 40)
        print(f"  ZEPHYR PAIRING PIN: {pin}")
        print(f"  Valid for {self.PIN_VALIDITY_SECONDS} seconds")
        print("  Enter this in the phone app now.")
        print("=" * 40)

        return pin

    def confirm_pairing(self, submitted_pin: str, device_name: str = "Unknown Device") -> dict:
        """Call this when the phone submits a PIN. Returns the new
        credentials on success — this is the ONLY time the secret is
        ever transmitted anywhere."""
        if not self._pending_pin or not self._pin_expires_at:
            return {"success": False, "error": "No pairing in progress"}

        if time.time() > self._pin_expires_at:
            self._pending_pin = None
            return {"success": False, "error": "Pairing PIN expired, start again"}

        if submitted_pin != self._pending_pin:
            self._failed_attempts += 1
            print(f"[Pairing] Wrong PIN attempt ({self._failed_attempts}/{self.MAX_FAILED_ATTEMPTS})")

            if self._failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                # Too many wrong guesses — cancel this pairing session
                # entirely rather than allow continued guessing. The
                # owner has to press "start pairing" again for a new PIN.
                self._pending_pin = None
                self._pin_expires_at = None
                print("[Pairing] Too many failed attempts — pairing cancelled, start again")
                return {"success": False, "error": "Too many incorrect attempts. Start pairing again."}

            return {"success": False, "error": "Incorrect PIN"}

        # Generate brand new, cryptographically random credentials —
        # never reused, never predictable, never hardcoded.
        device_id = uuid.uuid4().hex
        secret_key = secrets.token_hex(32)  # 256-bit random secret

        self.trusted_device_manager.save({
            "device_id": device_id,
            "secret_key": secret_key,
            "device_name": device_name,
        })

        self._pending_pin = None
        self._pin_expires_at = None

        print(f"[Pairing] New device paired: {device_name} ({device_id})")

        return {"success": True, "device_id": device_id, "secret_key": secret_key}

    def cancel_pairing(self):
        self._pending_pin = None
        self._pin_expires_at = None