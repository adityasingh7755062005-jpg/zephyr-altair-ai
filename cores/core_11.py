import time
from collections import deque


class Core11NoiseConfidenceEngine:
    """
    Phase 2 – Core 11
    -----------------
    Responsibilities:
    - Track background noise floor
    - Auto-adapt to loud / quiet environments
    - Decide if audio is valid
    - Attach confidence metadata
    """

    def __init__(
        self,
        window_size: int = 20,
        min_confidence: float = 1.3,
        floor_decay: float = 0.95
    ):
        self.window_size = window_size
        self.min_confidence = min_confidence
        self.floor_decay = floor_decay

        self.energy_window = deque(maxlen=window_size)
        self.noise_floor = None

        print("[Core 11] Initialized (Phase 2 – adaptive mode)")

    # --------------------------------------------------
    # Main public method
    # --------------------------------------------------
    def process(self, packet: dict) -> dict:
        """
        Takes Core 1 packet and returns enriched packet
        """

        energy = float(packet.get("energy", 0.0))

        # ---- Update rolling noise floor ----
        self._update_noise_floor(energy)

        # ---- Compute confidence ----
        confidence = (
            energy / self.noise_floor
            if self.noise_floor and self.noise_floor > 0
            else 0.0
        )

        # ---- Decide validity ----
        is_valid = confidence >= self.min_confidence

        # ---- Enrich packet ----
        packet.update({
            "is_valid": is_valid,
            "confidence": round(confidence, 3),
            "noise_floor": round(self.noise_floor, 6)
        })

        # ---- Minimal logging ----
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
        Adaptive noise estimation.
        Quiet places -> floor goes down
        Loud places  -> floor goes up
        """

        if self.noise_floor is None:
            self.noise_floor = max(energy, 1e-6)
            return

        # Add to rolling window
        self.energy_window.append(energy)

        avg_energy = sum(self.energy_window) / len(self.energy_window)

        # Smooth adaptation
        self.noise_floor = (
            self.noise_floor * self.floor_decay
            + avg_energy * (1 - self.floor_decay)
        )

        # Safety clamp
        if self.noise_floor < 1e-6:
            self.noise_floor = 1e-6