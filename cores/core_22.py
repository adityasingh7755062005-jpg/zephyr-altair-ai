# cores/core_22.py
# Core 22 - Threat Correlation & Auto-Defense Layer
#
# Doesn't replace any existing security mechanism — correlates
# signals FROM them (signature failures, pairing lockouts, intruder
# detector triggers, self-upgrade denials) across 4 layers, and
# blocks a source instantly the moment a threshold is crossed.
#
# Design choice, deliberately: blocks are SILENT (no live
# notification interrupting you) but ALWAYS fully logged — you can
# review the record whenever you choose, but nothing ever happens
# with zero trace. This mirrors how the existing intruder response
# already works (acts immediately, explains afterward via logs/
# photos) — just without the live push, per your preference.
#
# Same dependency-injection pattern as Core 21: the actual "block
# this source" action (revoke a session, add to a blocklist, lock
# the laptop) is injected at wiring time, not hardcoded here — keeps
# this fully testable standalone.

import time
import json
import os
from collections import defaultdict, deque


class Layer:
    REQUEST_INTEGRITY = "layer1_request_integrity"
    ACCESS_PATTERN = "layer2_access_pattern"
    PHYSICAL_PRESENCE = "layer3_physical_presence"
    TRUST_BOUNDARY = "layer4_trust_boundary"


class Core22ThreatCorrelation:
    """
    Phase 2 - Core 22
    -------------------
    Responsibility:
    - Receive signal reports from other cores/routes (signature
      failures, pairing lockouts, intruder triggers, upgrade denials)
    - Track a rolling window of recent signals per source
    - Cross a per-layer threshold -> block instantly + log in detail
    - Never notify live (by design) — always fully recorded for
      later review via get_records()
    """

    # (max_signals, window_seconds) per layer — crossing this many
    # signals from the SAME source within this window triggers a block.
    THRESHOLDS = {
        Layer.REQUEST_INTEGRITY: (3, 60),     # 3 forged/bad signatures in 60s
        Layer.ACCESS_PATTERN: (5, 120),       # 5 failed pairing/rate anomalies in 2min
        Layer.PHYSICAL_PRESENCE: (3, 30),     # 3 intruder-detector triggers in 30s
        Layer.TRUST_BOUNDARY: (2, 300),       # 2 denied/repeated upgrade attempts in 5min
    }

    def __init__(self, log_file="data/security/threat_log.json"):
        print("[Core 22] Threat correlation layer initialized")
        self.log_file = log_file
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # source -> layer -> deque of timestamps
        self._signal_history = defaultdict(lambda: defaultdict(deque))
        self._blocked_sources = set()
        self._block_handler = None  # injected — actually performs the block

    def register_block_handler(self, handler_fn):
        """Lets the real orchestrator wire in the actual block action
        (revoke session, add to relay blocklist, lock the laptop)
        without Core 22 needing to import those systems directly."""
        self._block_handler = handler_fn
        print("[Core 22] Block handler registered")

    def is_blocked(self, source: str) -> bool:
        return source in self._blocked_sources

    def report_signal(self, layer: str, source: str, detail: str) -> dict:
        """Call this whenever something suspicious happens anywhere
        in the system. source is whatever identifies who/where it
        came from — a device_id, an IP, a session id. Returns whether
        this signal caused a block."""
        if layer not in self.THRESHOLDS:
            return {"success": False, "message": f"Unknown layer '{layer}'"}

        now = time.time()
        max_signals, window_seconds = self.THRESHOLDS[layer]

        history = self._signal_history[source][layer]
        history.append(now)

        # Drop anything outside the window
        while history and now - history[0] > window_seconds:
            history.popleft()

        crossed = len(history) >= max_signals
        self._write_log_entry(layer, source, detail, blocked=crossed, signal_count=len(history))

        if crossed and source not in self._blocked_sources:
            self._block_source(source, layer, detail)

        return {"success": True, "blocked": crossed, "signal_count": len(history)}

    def _block_source(self, source: str, layer: str, triggering_detail: str):
        self._blocked_sources.add(source)
        print(f"[Core 22] 🔒 BLOCKED source '{source}' — {layer} threshold crossed ({triggering_detail})")

        if self._block_handler:
            try:
                self._block_handler(source, layer, triggering_detail)
            except Exception as e:
                print(f"[Core 22] Block handler failed: {e}")
        else:
            print("[Core 22] ⚠️ No block handler registered — logged only, no actual block performed")

    def unblock_source(self, source: str):
        """Manual release — e.g. you confirm it was a false positive
        after reviewing the log."""
        self._blocked_sources.discard(source)
        for layer_history in self._signal_history[source].values():
            layer_history.clear()
        print(f"[Core 22] Source '{source}' manually unblocked")

    # ==========================
    # LOGGING — always recorded, never live-notified
    # ==========================
    def _write_log_entry(self, layer: str, source: str, detail: str, blocked: bool, signal_count: int):
        entry = {
            "timestamp": int(time.time()),
            "date": time.strftime("%d/%m/%Y"),
            "time": time.strftime("%H:%M:%S"),
            "layer": layer,
            "source": source,
            "detail": detail,
            "signal_count_in_window": signal_count,
            "blocked": blocked,
        }
        entries = self._read_log()
        entries.insert(0, entry)
        entries = entries[:500]
        self._write_log(entries)

    def _read_log(self):
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[Core 22] Log read error: {e}")
        return []

    def _write_log(self, entries):
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)
        except Exception as e:
            print(f"[Core 22] Log write error: {e}")

    def get_records(self, source: str = None, blocked_only: bool = False) -> list:
        """Full review, on your own schedule — nothing about this
        system is hidden, it's just never pushed at you live."""
        entries = self._read_log()
        if source:
            entries = [e for e in entries if e["source"] == source]
        if blocked_only:
            entries = [e for e in entries if e["blocked"]]
        return entries


# --------------------------------------------------
# Example usage — run this file directly to test Core 22 by itself.
# --------------------------------------------------
if __name__ == "__main__":
    import tempfile

    core22 = Core22ThreatCorrelation(log_file=os.path.join(tempfile.gettempdir(), "core22_demo_log.json"))

    blocked_sources_seen = []

    def fake_block_handler(source, layer, detail):
        blocked_sources_seen.append((source, layer, detail))
        print(f"    🚫 [FAKE BLOCK ACTION] Revoking access for '{source}'")

    core22.register_block_handler(fake_block_handler)

    print("\n--- Layer 1: below threshold, should NOT block ---")
    print(core22.report_signal(Layer.REQUEST_INTEGRITY, "device-abc", "bad signature #1"))
    print(core22.report_signal(Layer.REQUEST_INTEGRITY, "device-abc", "bad signature #2"))
    print("Blocked?", core22.is_blocked("device-abc"))

    print("\n--- Layer 1: crossing the threshold (3 in 60s) ---")
    print(core22.report_signal(Layer.REQUEST_INTEGRITY, "device-abc", "bad signature #3"))
    print("Blocked?", core22.is_blocked("device-abc"))
    print("Block handler saw:", blocked_sources_seen)

    print("\n--- Layer 4: different source, different layer, own threshold (2 in 300s) ---")
    print(core22.report_signal(Layer.TRUST_BOUNDARY, "device-xyz", "denied upgrade attempt #1"))
    print(core22.report_signal(Layer.TRUST_BOUNDARY, "device-xyz", "denied upgrade attempt #2"))
    print("Blocked?", core22.is_blocked("device-xyz"))

    print("\n--- Manual unblock (false positive reviewed) ---")
    core22.unblock_source("device-abc")
    print("Blocked after manual unblock?", core22.is_blocked("device-abc"))

    print("\n--- Full records, on-demand review ---")
    for entry in core22.get_records()[:5]:
        print(" ", entry)

    print("\n--- Blocked-only records ---")
    for entry in core22.get_records(blocked_only=True):
        print(" ", entry)

    print("\nDemo complete.")