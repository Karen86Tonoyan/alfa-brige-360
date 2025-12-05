# ═══════════════════════════════════════════════════════════════════════════
# ALFA CLOUD OFFLINE - Master Package
# Complete Private Cloud Ecosystem
# ═══════════════════════════════════════════════════════════════════════════
"""
ALFA CLOUD OFFLINE - Complete Private Cloud System

Filar I: OFFLINE INFRASTRUCTURE
- Local storage with AES-256-GCM encryption
- Distributed LAN sync (UDP multicast + TCP)
- ZeroTrust architecture

Filar II: SECURITY (Cerber v7)
- PQXHybrid post-quantum cryptography
- Guardian 360° monitoring
- Łasuch honeypot/deception layer
- Living Code adaptive rules
- Evidence forensic capture

Filar III: AI STACK
- Ollama local models (llama3, llava, nomic-embed-text)
- Multi-modal AI agents
- RAG pipeline

Filar IV: API LAYER
- FastAPI REST + WebSocket
- JWT authentication
- Rate limiting

Filar V: DASHBOARD
- Real-time monitoring
- Security center
- AI chat interface

Usage:
    # Import core components
    from alfa_cloud import CloudEngine, CloudConfig
    from alfa_cloud.security import SecurityManager
    from alfa_cloud.ai import AIBridge
    
    # Start cloud
    engine = CloudEngine()
    await engine.start()
    
    # Start security
    security = SecurityManager()
    security.start()
"""

# Version
__version__ = "1.0.0"
__author__ = "ALFA Team"
__codename__ = "ALFA CLOUD OFFLINE"

# Core imports
try:
    from .core import CloudEngine, CloudState, CloudFile, CloudStats
    from .core import EncryptionEngine, SecureVault
    from .core import SyncEngine
except ImportError as e:
    CloudEngine = None
    CloudState = None
    CloudFile = None
    CloudStats = None
    EncryptionEngine = None
    SecureVault = None
    SyncEngine = None

# Security imports
try:
    from .security import (
        SecurityManager,
        Guardian,
        Lasuch,
        LivingCodeEngine,
        EvidenceCollector,
        generate_keypair,
        PQKeyPair,
    )
except ImportError:
    SecurityManager = None
    Guardian = None
    Lasuch = None
    LivingCodeEngine = None
    EvidenceCollector = None
    generate_keypair = None
    PQKeyPair = None

# AI imports
try:
    from .ai import LocalLLM, Analyzer
except ImportError:
    LocalLLM = None
    Analyzer = None

# Agent imports
try:
    from .agents import FileAgent, BackupAgent, AIAgent
except ImportError:
    FileAgent = None
    BackupAgent = None
    AIAgent = None

__all__ = [
    # Version
    "__version__",
    "__author__",
    "__codename__",
    # Core
    "CloudEngine",
    "CloudState",
    "CloudFile",
    "CloudStats",
    "EncryptionEngine",
    "SecureVault",
    "SyncEngine",
    # Security
    "SecurityManager",
    "Guardian",
    "Lasuch",
    "LivingCodeEngine",
    "EvidenceCollector",
    "generate_keypair",
    "PQKeyPair",
    # AI
    "LocalLLM",
    "Analyzer",
    # Agents
    "FileAgent",
    "BackupAgent",
    "AIAgent",
]
