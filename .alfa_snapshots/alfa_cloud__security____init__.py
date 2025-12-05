# ═══════════════════════════════════════════════════════════════════════════
# ALFA CLOUD SECURITY MODULE
# Cerber v7 Integration Layer
# ═══════════════════════════════════════════════════════════════════════════
"""
ALFA CLOUD Security - Zero-Trust Offline Security Stack

Components:
- PQXHybrid: Post-quantum cryptography (Falcon, SPHINCS+, Dilithium)
- Guardian: 360° system monitor
- Łasuch: Honeypot/deception layer
- Living Code Engine: Self-healing adaptive rules
- Evidence Collector: Forensic artifact capture

Usage:
    from alfa_cloud.security import SecurityManager
    
    security = SecurityManager()
    security.start()
    
    # Get status
    status = security.get_status()
    
    # Capture evidence
    bundle = security.capture_evidence()
"""

from .cerber_v7 import (
    # Main manager
    SecurityManager,
    # Guardian
    Guardian,
    GuardianAlert,
    # Lasuch
    Lasuch,
    CapturedPayload,
    # Living Code
    LivingCodeEngine,
    TelemetryEvent,
    # Evidence
    EvidenceCollector,
    EvidenceBundle,
    # PQXHybrid
    PQKeyPair,
    generate_keypair,
    sign_frame,
    verify_frame,
    PlaceholderProvider,
)

__all__ = [
    # Main manager
    "SecurityManager",
    # Guardian
    "Guardian",
    "GuardianAlert",
    # Lasuch
    "Lasuch",
    "CapturedPayload",
    # Living Code
    "LivingCodeEngine",
    "TelemetryEvent",
    # Evidence
    "EvidenceCollector",
    "EvidenceBundle",
    # PQXHybrid
    "PQKeyPair",
    "generate_keypair",
    "sign_frame",
    "verify_frame",
    "PlaceholderProvider",
]

__version__ = "7.0.0"
