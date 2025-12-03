#!/usr/bin/env python3
"""
===============================================
ALFA_CORE v2.0 - BOJOWA KONFIGURACJA
===============================================
Centrum Dowodzenia systemu ALFA.

Sekcje:
- Ollama (lokalne modele AI)
- DeepSeek API (zewnętrzne AI)
- Profile modeli (fast/balanced/creative/security)
- MCP Servers (integracje zewnętrzne)
- Security (Cerber)
- Network

Author: ALFA System / Karen86Tonoyan
"""

import os
import httpx
from pathlib import Path

# =============================================================================
# PATHS
# =============================================================================

ALFA_ROOT = Path(__file__).parent
CONFIG_DIR = ALFA_ROOT / "config"
LOGS_DIR = ALFA_ROOT / "logs"
DATA_DIR = ALFA_ROOT / "data"

# Create directories if needed
for d in [CONFIG_DIR, LOGS_DIR, DATA_DIR]:
    d.mkdir(exist_ok=True)

# =============================================================================
# OLLAMA (LOCAL AI)
# =============================================================================

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_DEFAULT_MODEL = "deepseek-r1:7b"

# =============================================================================
# DEEPSEEK API (EXTERNAL AI)
# =============================================================================

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"

# =============================================================================
# MODEL PROFILES (AMUNICJA)
# =============================================================================

MODELS = {
    "fast": {
        "name": "gemma:2b",
        "temperature": 0.3,
        "max_tokens": 4096,
        "role": "Zwiadowca. Szybkie odpowiedzi, niskie zużycie zasobów.",
        "backend": "ollama"
    },
    "balanced": {
        "name": "deepseek-r1:7b",
        "temperature": 0.6,
        "max_tokens": 8192,
        "role": "Główny oficer operacyjny. Balans między logiką a kreatywnością.",
        "backend": "ollama"
    },
    "creative": {
        "name": "mistral",
        "temperature": 0.9,
        "max_tokens": 12000,
        "role": "Analityk kreatywny. Burza mózgów i nieszablonowe rozwiązania.",
        "backend": "ollama"
    },
    "security": {
        "name": "llama3",
        "temperature": 0.1,
        "max_tokens": 4096,
        "role": "Strażnik Cerber. Analiza bezpieczeństwa, sucha logika, zero emocji.",
        "backend": "ollama"
    },
    "deepseek": {
        "name": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 16000,
        "role": "Zewnętrzny analityk. Pełna moc DeepSeek API.",
        "backend": "deepseek"
    }
}

DEFAULT_PROFILE = "balanced"

# Kolejność awaryjna (Failover)
FALLBACK_CHAIN = ["balanced", "fast", "security"]

# =============================================================================
# MCP SERVERS
# =============================================================================

MCP_CONFIG_PATH = CONFIG_DIR / "mcp_servers.json"

MCP_LAYERS = {
    "creative": ["figma", "webflow"],
    "knowledge": ["deepwiki", "microsoft-docs"],
    "automation": ["apify", "markitdown"],
    "dev": ["idl-vscode", "pylance"]
}

# =============================================================================
# NETWORK PARAMS
# =============================================================================

# Timeouty HTTP (sekundy)
TIMEOUT = 600

HTTP_TIMEOUT = httpx.Timeout(
    600.0,
    read=600.0,
    write=600.0,
    connect=30.0
)

# =============================================================================
# SECURITY (CERBER)
# =============================================================================

# Lista dozwolonych IP
ALLOWED_IPS = ["127.0.0.1", "::1", "192.168.1.0/24"]

# Cerber mode
CERBER_ENABLED = True
CERBER_LOG_PATH = LOGS_DIR / "cerber.log"

# =============================================================================
# DATABASE
# =============================================================================

DB_PATH = DATA_DIR / "alfa_memory.db"
DB_ENCRYPTION_KEY = os.environ.get("ALFA_DB_KEY", "")

# =============================================================================
# MODES
# =============================================================================

# Tryb bojowy - ignoruje limity, pełna moc
BATTLE_MODE = os.environ.get("ALFA_BATTLE_MODE", "false").lower() == "true"

# Tryb cichy - wycisza logi
SILENT_MODE = os.environ.get("ALFA_SILENT_MODE", "false").lower() == "true"

# Tryb deweloperski
DEV_MODE = os.environ.get("ALFA_DEV_MODE", "true").lower() == "true"

# =============================================================================
# VERSION
# =============================================================================

VERSION = "2.0.0"
CODENAME = "CERBER"


def get_model_config(profile: str = None) -> dict:
    """Get model configuration for given profile."""
    profile = profile or DEFAULT_PROFILE
    if profile not in MODELS:
        profile = DEFAULT_PROFILE
    return MODELS[profile]


def get_ollama_url(endpoint: str = "/api/chat") -> str:
    """Get full Ollama API URL."""
    return f"{OLLAMA_BASE_URL}{endpoint}"


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

# Stare nazwy dla kompatybilności wstecznej
CHAT_MODEL = OLLAMA_DEFAULT_MODEL
