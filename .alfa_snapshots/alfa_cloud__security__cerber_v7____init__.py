# ═══════════════════════════════════════════════════════════════════════════
# CERBER v7 - Core Security Module
# ═══════════════════════════════════════════════════════════════════════════
"""
Cerber v7 Security Stack for ALFA CLOUD OFFLINE

Architecture:
- Guardian: Process/network monitoring
- Łasuch: Deception/honeypot layer
- PQXHybrid: Post-quantum signatures
- Living Code: Adaptive rule engine
- Evidence: Forensic capture
- Manager: Unified security controller
"""

from .guardian import Guardian, GuardianAlert
from .lasuch import Lasuch, CapturedPayload
from .living_code_engine import LivingCodeEngine, TelemetryEvent
from .evidence import EvidenceCollector, EvidenceBundle
from .manager import SecurityManager
from .pqxhybrid import (
    PQKeyPair,
    generate_keypair,
    sign_frame,
    verify_frame,
    PlaceholderProvider,
)

__all__ = [
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
    # Manager
    "SecurityManager",
    # PQXHybrid
    "PQKeyPair",
    "generate_keypair",
    "sign_frame",
    "verify_frame",
    "PlaceholderProvider",
]

# Version
__version__ = "7.0.0"
