# ═══════════════════════════════════════════════════════════════════════════
# LIVING CODE ENGINE - Adaptive Rule System
# ═══════════════════════════════════════════════════════════════════════════
"""
Living Code Engine: Self-healing adaptive security rules.

Features:
- Telemetry-driven rule updates
- Heuristic threshold computation
- Self-regenerating rule modules
- Masked backup for self-healing
- Version tracking and rollback
"""

from __future__ import annotations

import hashlib
import json
import secrets
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
import logging

logger = logging.getLogger("cerber.living_code")


@dataclass(frozen=True)
class TelemetryEvent:
    """Minimal telemetry sample for rule training."""
    anomaly_score: float
    novel_processes: int
    privilege_escalations: int
    network_beacons: int
    label: str = "benign"

    def to_payload(self) -> dict:
        return asdict(self)


@dataclass
class RuleThresholds:
    """Computed thresholds for decision logic."""
    anomaly_score: float = 0.5
    novel_processes: float = 5.0
    privilege_escalations: float = 1.0
    network_beacons: float = 3.0
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RuleWeights:
    """Weights for scoring events."""
    anomaly_score: float = 0.4
    novel_processes: float = 0.2
    privilege_escalations: float = 0.25
    network_beacons: float = 0.15
    
    def to_dict(self) -> dict:
        return asdict(self)


class LivingCodeEngine:
    """
    Adaptive rule engine that retrains from telemetry.
    
    The engine:
    1. Ingests tagged telemetry events (benign/malicious)
    2. Computes new thresholds and weights
    3. Generates a Python rule module
    4. Keeps masked backups for self-healing
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.home() / ".cerber" / "living_code"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.state_path = self.base_dir / "state.json"
        self.history_path = self.base_dir / "telemetry.jsonl"
        self.module_path = self.base_dir / "living_rules.py"
        self.mask_dir = self.base_dir / "masked"
        self.mask_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.base_dir / "mask_manifest.json"
        
        self._current_thresholds: Optional[RuleThresholds] = None
        self._current_weights: Optional[RuleWeights] = None

    def update_rules(self, events: Iterable[TelemetryEvent]) -> Path:
        """Update rules from telemetry events."""
        samples = list(events)
        if not samples:
            raise ValueError("At least one telemetry event required")

        state = self._load_state()
        state["version"] = state.get("version", 0) + 1
        state["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        
        self._append_history(samples)
        history = self._load_history()
        
        thresholds = self._derive_thresholds(history)
        weights = self._derive_weights(history)
        
        self._current_thresholds = RuleThresholds(**thresholds)
        self._current_weights = RuleWeights(**weights)
        
        module_bytes = self._write_module(thresholds, weights, state)
        mask_info = self._mask_module(module_bytes, state["version"])
        
        self._persist_manifest(mask_info)
        self._persist_state(state)
        
        logger.info(f"📜 Living rules updated to v{state['version']}")
        return self.module_path

    def self_heal(self) -> Path:
        """Restore rules from masked backup if corrupted."""
        manifest = self._load_manifest()
        current = manifest.get("current")
        
        if not current:
            raise FileNotFoundError("No mask manifest found")

        expected_hash = current["hash"]
        
        # Check if current module is valid
        if self.module_path.exists():
            if self._hash_bytes(self.module_path.read_bytes()) == expected_hash:
                return self.module_path

        # Restore from masked copy
        masked_path = Path(current["masked_path"])
        if masked_path.exists():
            masked_bytes = masked_path.read_bytes()
            if self._hash_bytes(masked_bytes) != expected_hash:
                raise FileNotFoundError("Masked copy corrupted")
            
            self.module_path.write_bytes(masked_bytes)
            logger.warning("🔧 Living rules restored from masked backup")
            return self.module_path

        raise FileNotFoundError("No valid backup available")

    def score_event(self, event: Dict[str, Any]) -> float:
        """Score an event using current thresholds."""
        if not self._current_thresholds or not self._current_weights:
            # Load from state or use defaults
            self._current_thresholds = RuleThresholds()
            self._current_weights = RuleWeights()
        
        t = self._current_thresholds
        w = self._current_weights
        
        score = 0.0
        if event.get("anomaly_score", 0) >= t.anomaly_score:
            score += w.anomaly_score
        if event.get("novel_processes", 0) >= t.novel_processes:
            score += w.novel_processes
        if event.get("privilege_escalations", 0) >= t.privilege_escalations:
            score += w.privilege_escalations
        if event.get("network_beacons", 0) >= t.network_beacons:
            score += w.network_beacons
            
        return min(score, 1.0)

    def decide_action(self, event: Dict[str, Any]) -> str:
        """Decide action based on event score."""
        score = self.score_event(event)
        
        if score >= 0.75:
            return "block"
        if score >= 0.5:
            return "quarantine"
        return "observe"

    def get_version(self) -> int:
        """Get current rule version."""
        state = self._load_state()
        return state.get("version", 0)

    def _load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {"version": 0, "updated_at": None}

    def _persist_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=2))

    def _append_history(self, samples: Sequence[TelemetryEvent]) -> None:
        with self.history_path.open("a", encoding="utf-8") as handle:
            for event in samples:
                handle.write(json.dumps(event.to_payload()) + "\n")

    def _load_history(self) -> List[TelemetryEvent]:
        if not self.history_path.exists():
            return []
        events: List[TelemetryEvent] = []
        for line in self.history_path.read_text().splitlines():
            payload = json.loads(line)
            events.append(TelemetryEvent(**payload))
        return events

    def _persist_manifest(self, current: dict) -> None:
        manifest = {"current": current, "history": []}
        if self.manifest_path.exists():
            existing = json.loads(self.manifest_path.read_text())
            history = existing.get("history", [])
            if existing.get("current"):
                history.append(existing["current"])
            manifest["history"] = history[-10:]  # Keep last 10
        self.manifest_path.write_text(json.dumps(manifest, indent=2))

    def _load_manifest(self) -> dict:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return {}

    def _derive_thresholds(self, events: Sequence[TelemetryEvent]) -> dict:
        benign = [e for e in events if e.label == "benign"]
        malicious = [e for e in events if e.label != "benign"]

        def _average(values: Sequence[float], default: float) -> float:
            return statistics.mean(values) if values else default

        def _midpoint(a: float, b: float) -> float:
            return (a + b) / 2

        benign_defaults = {
            "anomaly_score": 0.15,
            "novel_processes": 2.0,
            "privilege_escalations": 0.2,
            "network_beacons": 1.0,
        }

        malicious_defaults = {
            "anomaly_score": 0.8,
            "novel_processes": 6.0,
            "privilege_escalations": 2.0,
            "network_beacons": 4.0,
        }

        thresholds = {}
        for field in benign_defaults:
            benign_avg = _average([getattr(e, field) for e in benign], benign_defaults[field])
            malicious_avg = _average(
                [getattr(e, field) for e in malicious], malicious_defaults[field]
            )
            thresholds[field] = round(_midpoint(benign_avg, malicious_avg), 3)
        return thresholds

    def _derive_weights(self, events: Sequence[TelemetryEvent]) -> dict:
        malicious_count = len([e for e in events if e.label != "benign"])
        total = max(len(events), 1)
        
        base_weight = 0.25
        anomaly_weight = base_weight + (malicious_count / total) * 0.25
        
        return {
            "anomaly_score": round(min(anomaly_weight, 0.6), 3),
            "novel_processes": 0.25,
            "privilege_escalations": 0.25,
            "network_beacons": 0.25,
        }

    def _write_module(self, thresholds: dict, weights: dict, state: dict) -> bytes:
        generated_at = state["updated_at"]
        version = state["version"]
        
        module = f'''"""AUTO-GENERATED Cerber Living Rules.

Version: {version}
Generated: {generated_at}
DO NOT EDIT - This file is regenerated by LivingCodeEngine.
"""

from __future__ import annotations

VERSION = {version}
GENERATED_AT = "{generated_at}"

THRESHOLDS = {json.dumps(thresholds, indent=4)}
WEIGHTS = {json.dumps(weights, indent=4)}


def score_event(event: dict) -> float:
    """Compute suspicion score (0-1)."""
    anomaly = float(event.get("anomaly_score", 0.0))
    novel = float(event.get("novel_processes", 0.0))
    escalations = float(event.get("privilege_escalations", 0.0))
    beacons = float(event.get("network_beacons", 0.0))

    score = 0.0
    score += WEIGHTS["anomaly_score"] if anomaly >= THRESHOLDS["anomaly_score"] else 0.0
    score += WEIGHTS["novel_processes"] if novel >= THRESHOLDS["novel_processes"] else 0.0
    score += WEIGHTS["privilege_escalations"] if escalations >= THRESHOLDS["privilege_escalations"] else 0.0
    score += WEIGHTS["network_beacons"] if beacons >= THRESHOLDS["network_beacons"] else 0.0
    return min(score, 1.0)


def decide_action(event: dict) -> str:
    """Translate score to action."""
    score = score_event(event)
    if score >= 0.75:
        return "block"
    if score >= 0.5:
        return "quarantine"
    return "observe"
'''
        module += "\n"
        module_bytes = module.encode("utf-8")
        self.module_path.write_bytes(module_bytes)
        return module_bytes

    def _hash_bytes(self, payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def _mask_module(self, module_bytes: bytes, version: int) -> dict:
        digest = self._hash_bytes(module_bytes)
        masked_name = f"{digest[:12]}_{secrets.token_hex(4)}.py"
        masked_path = self.mask_dir / masked_name
        masked_path.write_bytes(module_bytes)
        
        return {
            "version": version,
            "hash": digest,
            "module_path": str(self.module_path),
            "masked_path": str(masked_path),
            "written_at": datetime.now(tz=timezone.utc).isoformat(),
        }
