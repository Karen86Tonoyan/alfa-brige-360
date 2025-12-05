# ═══════════════════════════════════════════════════════════════════════════
# SECURITY MANAGER - Unified Security Control Center
# ═══════════════════════════════════════════════════════════════════════════
"""
Security Manager: Central coordinator for all Cerber v7 components.

Integrates:
- Guardian (monitoring)
- Łasuch (deception)
- Living Code Engine (adaptive rules)
- Evidence Collector (forensics)
- PQXHybrid (cryptography)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .guardian import Guardian, GuardianAlert
from .lasuch import Lasuch, CapturedPayload
from .living_code_engine import LivingCodeEngine, TelemetryEvent
from .evidence import EvidenceCollector, EvidenceBundle
from .pqxhybrid import generate_keypair, PQKeyPair

logger = logging.getLogger("cerber.manager")


class SecurityManager:
    """
    🛡️ ALFA CLOUD Security Manager
    
    Central coordinator for the Cerber v7 security stack.
    
    Usage:
        security = SecurityManager()
        security.start()
        
        # Check status
        status = security.get_status()
        
        # Get alerts
        alerts = security.get_alerts()
        
        # Quick evidence capture
        bundle = security.capture_evidence()
    """
    
    def __init__(
        self,
        base_dir: Optional[Path] = None,
        pq_scheme: str = "falcon",
        auto_start: bool = False,
    ):
        self.base_dir = base_dir or Path.home() / ".cerber"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize keypair for signing
        self._keypair: Optional[PQKeyPair] = None
        self._pq_scheme = pq_scheme
        self._init_keypair()
        
        # Initialize components
        self.guardian = Guardian(
            alert_callback=self._on_alert,
            evidence_dir=self.base_dir / "evidence" / "guardian",
        )
        
        self.lasuch = Lasuch(
            decoy_dir=self.base_dir / "decoys",
            evidence_dir=self.base_dir / "evidence" / "lasuch",
            capture_callback=self._on_capture,
        )
        
        self.living_engine = LivingCodeEngine(
            base_dir=self.base_dir / "living_code",
        )
        
        self.evidence_collector = EvidenceCollector(
            evidence_dir=self.base_dir / "evidence",
            keypair=self._keypair,
        )
        
        # State
        self._running = False
        self._alerts: List[GuardianAlert] = []
        self._captures: List[CapturedPayload] = []
        self._telemetry: List[TelemetryEvent] = []
        
        # Callbacks
        self._alert_callbacks: List[Callable[[GuardianAlert], None]] = []
        self._capture_callbacks: List[Callable[[CapturedPayload], None]] = []
        
        if auto_start:
            self.start()
    
    def _init_keypair(self) -> None:
        """Initialize or load PQ keypair."""
        keyfile = self.base_dir / "security_key.json"
        
        if keyfile.exists():
            try:
                data = json.loads(keyfile.read_text())
                import base64
                self._keypair = PQKeyPair(
                    scheme=data["scheme"],
                    public_key=base64.b64decode(data["public_key"]),
                    secret_key=base64.b64decode(data["secret_key"]),
                )
                logger.info(f"🔑 Loaded existing {data['scheme']} keypair")
                return
            except Exception as e:
                logger.warning(f"Failed to load keypair: {e}")
        
        # Generate new keypair
        self._keypair = generate_keypair(self._pq_scheme)
        
        # Save keypair
        keyfile.write_text(json.dumps(self._keypair.to_dict(), indent=2))
        logger.info(f"🔑 Generated new {self._pq_scheme} keypair")
    
    def start(self) -> None:
        """Start all security components."""
        if self._running:
            return
        
        logger.info("🛡️ CERBER SECURITY STARTING...")
        
        # Start Guardian
        self.guardian.start()
        
        # Start Łasuch
        self.lasuch.start()
        
        # Initialize living code if needed
        try:
            self.living_engine.self_heal()
        except FileNotFoundError:
            # Train with default events
            self._train_default_rules()
        
        self._running = True
        logger.info("🛡️ CERBER SECURITY ACTIVE")
    
    def stop(self) -> None:
        """Stop all security components."""
        if not self._running:
            return
        
        logger.info("🛡️ CERBER SECURITY STOPPING...")
        
        self.guardian.stop()
        self.lasuch.stop()
        
        self._running = False
        logger.info("🛡️ CERBER SECURITY STOPPED")
    
    def _train_default_rules(self) -> None:
        """Train living engine with default data."""
        default_events = [
            TelemetryEvent(0.1, 1, 0, 0, label="benign"),
            TelemetryEvent(0.15, 2, 0, 1, label="benign"),
            TelemetryEvent(0.2, 2, 0, 0, label="benign"),
            TelemetryEvent(0.85, 6, 2, 3, label="malicious"),
            TelemetryEvent(0.9, 8, 3, 5, label="malicious"),
        ]
        self.living_engine.update_rules(default_events)
    
    def _on_alert(self, alert: GuardianAlert) -> None:
        """Handle Guardian alerts."""
        self._alerts.append(alert)
        
        # Feed to living engine
        event = TelemetryEvent(
            anomaly_score=0.8 if alert.severity == "critical" else 0.5,
            novel_processes=1 if alert.category == "process" else 0,
            privilege_escalations=1 if alert.category == "injection" else 0,
            network_beacons=1 if alert.category == "network" else 0,
            label="malicious",
        )
        self._telemetry.append(event)
        
        # Notify callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def _on_capture(self, payload: CapturedPayload) -> None:
        """Handle Łasuch captures."""
        self._captures.append(payload)
        
        # Feed to living engine
        event = TelemetryEvent(
            anomaly_score=0.9,
            novel_processes=0,
            privilege_escalations=0,
            network_beacons=1 if payload.payload_type == "network" else 0,
            label="malicious",
        )
        self._telemetry.append(event)
        
        # Notify callbacks
        for callback in self._capture_callbacks:
            try:
                callback(payload)
            except Exception as e:
                logger.error(f"Capture callback failed: {e}")
    
    def on_alert(self, callback: Callable[[GuardianAlert], None]) -> None:
        """Register alert callback."""
        self._alert_callbacks.append(callback)
    
    def on_capture(self, callback: Callable[[CapturedPayload], None]) -> None:
        """Register capture callback."""
        self._capture_callbacks.append(callback)
    
    def get_alerts(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get alerts as dictionaries."""
        alerts = self._alerts
        if since:
            alerts = [a for a in alerts if a.timestamp >= since]
        return [a.to_dict() for a in alerts]
    
    def get_captures(self) -> List[Dict[str, Any]]:
        """Get captures as dictionaries."""
        return [c.to_dict() for c in self._captures]
    
    def capture_evidence(self) -> EvidenceBundle:
        """Quick capture of all evidence."""
        return self.evidence_collector.quick_capture()
    
    def update_rules(self) -> Path:
        """Update living code rules from telemetry."""
        if not self._telemetry:
            raise ValueError("No telemetry data available")
        
        return self.living_engine.update_rules(self._telemetry)
    
    def start_honeypot(self, port: int = 4040) -> None:
        """Start a network honeypot on the specified port."""
        self.lasuch.start_honeypot(port=port)
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive security status."""
        return {
            "running": self._running,
            "timestamp": datetime.now().isoformat(),
            "components": {
                "guardian": {
                    "active": self.guardian._running,
                    "alert_count": len(self._alerts),
                },
                "lasuch": {
                    "active": self.lasuch._running,
                    "decoy_count": len(self.lasuch._decoys),
                    "capture_count": len(self._captures),
                },
                "living_code": {
                    "version": self.living_engine.get_version(),
                    "telemetry_count": len(self._telemetry),
                },
                "crypto": {
                    "scheme": self._pq_scheme,
                    "keypair_loaded": self._keypair is not None,
                },
            },
            "recent_alerts": self.get_alerts()[-5:],
            "recent_captures": self.get_captures()[-5:],
        }
    
    def get_decoy_status(self) -> List[Dict[str, Any]]:
        """Get status of all honeypot decoys."""
        return self.lasuch.get_decoy_status()
    
    def export_security_report(self, output_path: Optional[Path] = None) -> Path:
        """Export full security report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "status": self.get_status(),
            "all_alerts": self.get_alerts(),
            "all_captures": self.get_captures(),
            "decoys": self.get_decoy_status(),
            "living_code_version": self.living_engine.get_version(),
        }
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.base_dir / f"security_report_{timestamp}.json"
        
        output_path.write_text(json.dumps(report, indent=2))
        logger.info(f"📄 Security report exported: {output_path}")
        
        return output_path
