"""
ALFA PROVIDERS — Package
Eksportuje wszystkie providery ALFA.
"""

# Bazowe klasy i błędy
from .base import (
    BaseProvider,
    ProviderError,
    ConnectionError,
    AuthenticationError,
    RateLimitError,
    ContentBlockedError,
    ModelNotFoundError,
    TimeoutError,
    ModeType
)

# Główne providery
from .gemini_provider import GeminiProvider
from .deepseek_provider import DeepSeekProvider
from .local_provider import LocalProvider

# AutoSwitch z failover
from .autoswitch import AutoSwitch

# Legacy API
from .api_gemini import GeminiAPI, get_gemini


__all__ = [
    # Bazowe
    "BaseProvider",
    "ProviderError",
    "ConnectionError",
    "AuthenticationError",
    "RateLimitError",
    "ContentBlockedError",
    "ModelNotFoundError",
    "TimeoutError",
    "ModeType",
    
    # Providery
    "GeminiProvider",
    "DeepSeekProvider",
    "LocalProvider",
    "AutoSwitch",
    
    # Legacy
    "GeminiAPI",
    "get_gemini",
]


# ═══════════════════════════════════════════════════════════════════════════
# QUICK ACCESS HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def create_autoswitch(
    use_gemini: bool = True,
    use_deepseek: bool = True,
    use_local: bool = True
) -> AutoSwitch:
    """
    Tworzy AutoSwitch z wybranymi providerami.
    
    Args:
        use_gemini: Czy używać Gemini
        use_deepseek: Czy używać DeepSeek
        use_local: Czy używać Local (Ollama)
        
    Returns:
        Skonfigurowany AutoSwitch
    """
    providers = []
    
    if use_gemini:
        try:
            providers.append(GeminiProvider())
        except Exception:
            pass
    
    if use_deepseek:
        try:
            providers.append(DeepSeekProvider())
        except Exception:
            pass
    
    if use_local:
        try:
            local = LocalProvider()
            if local.health():
                providers.append(local)
        except Exception:
            pass
    
    return AutoSwitch(providers)


def quick_generate(prompt: str, system_prompt: str | None = None) -> str:
    """
    Szybkie generowanie z AutoSwitch.
    
    Args:
        prompt: Tekst promptu
        system_prompt: System prompt (opcjonalny)
        
    Returns:
        Odpowiedź od modelu
    """
    auto = create_autoswitch()
    return auto.generate(prompt, system_prompt)
