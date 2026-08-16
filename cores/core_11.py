# cores/core_11.py
# Core 11 – Noise & Confidence Engine — Hardened

import time
from collections import deque


class Core11NoiseConfidenceEngine:
    """
    Phase 2 – Core 11 (Hardened)
    ------------------------------
    Responsibilities:
    - Track background noise floor
    - Auto-adapt to loud / quiet environments
    - Decide if audio is valid
    - Attach confidence metadata

    Fixes two real bugs from the original:
    1. First recording after startup no longer auto-rejected
       (floor is now seeded conservatively, not from the first
       energy sample itself).
    2. Noise floor no longer contaminated by accepted speech —
       only readings classified as background get folded into
       the rolling estimate, so using the assistant a lot no
       longer degrades detection accuracy over time.
    """

    def __init__(
        self,
        window_size: int = 20,
        min_confidence: float = 1.3,
        floor_decay: float = 0.95,
        initial_floor_seed: float = 1e-4,
        min_absolute_energy: float = 1e-5,
    ):
        self.window_size = window_size
        self.min_confidence = min_confidence
        self.floor_decay = floor_decay
        self.min_absolute_energy = min_absolute_energy

        self.energy_window = deque(maxlen=window_size)

        # Seeded with a small constant instead of the first sample's own
        # energy — avoids the "first speech = floor = confidence 1.0"
        # bug where the very first recording was always rejected.
        self.noise_floor = initial_floor_seed

        print("[Core 11] Initialized (Phase 2 – adaptive mode, Hardened)")

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def process(self, packet: dict) -> dict:
        """
        Takes Core 1's packet and returns an enriched packet.
        """
        energy = float(packet.get("energy", 0.0))

        # ---- Compute confidence FIRST, using the floor as it
        # currently stands (before this sample can influence it) ----
        confidence = (
            energy / self.noise_floor
            if self.noise_floor and self.noise_floor > 0
            else 0.0
        )

        # ---- Decide validity (ratio-based AND absolute minimum) ----
        is_valid = (
            confidence >= self.min_confidence
            and energy >= self.min_absolute_energy
        )

        # ---- Only update the noise floor with BACKGROUND samples.
        # Accepted speech is deliberately excluded so real commands
        # don't drag the floor upward over time. ----
        if not is_valid:
            self._update_noise_floor(energy)

        # ---- Enrich packet ----
        # NOTE: named "audio_confidence" (not "confidence") deliberately.
        # Core 3 also writes packet["confidence"] for INTENT-match
        # confidence (0.0-1.0 scale) — using the same key here would
        # silently collide/overwrite depending on pipeline order.
        packet.update({
            "is_valid": is_valid,
            "audio_confidence": round(confidence, 3),
            "noise_floor": round(self.noise_floor, 6),
        })

        status = "ACCEPTED" if is_valid else "REJECTED"
        print(
            f"[Core 11] {status} | "
            f"energy={energy:.5f} | "
            f"noise={self.noise_floor:.5f} | "
            f"conf={confidence:.2f}"
        )

        return packet

    # --------------------------------------------------
    # Internal helpers
    # --------------------------------------------------
    def _update_noise_floor(self, energy: float):
        """
        Adaptive noise estimation using ONLY background/rejected
        samples. Quiet places -> floor goes down. Loud (but
        non-speech) places -> floor goes up.
        """
        self.energy_window.append(energy)

        avg_energy = sum(self.energy_window) / len(self.energy_window)

        self.noise_floor = (
            self.noise_floor * self.floor_decay
            + avg_energy * (1 - self.floor_decay)
        )

        # Safety clamp — never let the floor hit zero
        if self.noise_floor < 1e-6:
            self.noise_floor = 1e-6


# --------------------------------------------------
# Example usage
# --------------------------------------------------
if __name__ == "__main__":
    engine = Core11NoiseConfidenceEngine()

    # Simulating: first call is REAL SPEECH right at startup.
    # With the old code this would always be rejected (confidence
    # exactly 1.0). With the fix, it correctly passes.
    print(engine.process({"energy": 0.05}))

    # Simulating quiet background between commands
    print(engine.process({"energy": 0.0008}))
    print(engine.process({"energy": 0.0009}))

    # Another real command — floor should NOT have drifted up
    # because of the first accepted speech sample
    print(engine.process({"energy": 0.048}))