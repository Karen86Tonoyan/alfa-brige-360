"""
ALFA_CORE_KERNEL v3.0 — BASE PROVIDER
Abstrakcyjna klasa bazowa dla wszystkich providerów AI.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class ProviderStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass
class ProviderResponse:
    """Ujednolicona odpowiedź od providera."""
    text: str
    provider: str
    model: str
    success: bool = True
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseProvider(ABC):
    """
    Abstrakcyjna klasa bazowa dla providerów AI.
    Każdy provider (Gemini, DeepSeek, Local) musi ją implementować.
    """
    
    name: str = "base"
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generuje odpowiedź tekstową."""
        raise NotImplementedError
    
    @abstractmethod
    def health(self) -> bool:
        """Sprawdza czy provider jest dostępny."""
        raise NotImplementedError
    
    def status(self) -> ProviderStatus:
        """Zwraca status providera."""
        try:
            if self.health():
                return ProviderStatus.ONLINE
            return ProviderStatus.OFFLINE
        except Exception:
            return ProviderStatus.ERROR
    
    def to_response(self, text: str, success: bool = True, error: str = None) -> ProviderResponse:
        """Konwertuje tekst do ustandaryzowanej odpowiedzi."""
        return ProviderResponse(
            text=text,
            provider=self.name,
            model=getattr(self, 'model', 'unknown'),
            success=success,
            error=error
        )
