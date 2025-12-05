"""
ALFA PROVIDERS — BASE & ERRORS
Bazowe klasy i błędy dla providerów.
"""

from __future__ import annotations

from typing import Protocol, Literal, runtime_checkable


ModeType = Literal["fast", "balanced", "creative", "secure"]


@runtime_checkable
class BaseProvider(Protocol):
    """
    Protokół dla wszystkich providerów ALFA.
    Każdy provider musi implementować generate().
    """
    
    name: str
    
    def generate(self, prompt: str, system_prompt: str | None = None, mode: ModeType = "balanced") -> str:
        """
        Generuje odpowiedź.
        
        Args:
            prompt: Tekst promptu
            system_prompt: System prompt (opcjonalny)
            mode: Tryb generowania
            
        Returns:
            Odpowiedź od modelu
        """
        ...
    
    def health(self) -> bool:
        """
        Sprawdza dostępność providera.
        
        Returns:
            True jeśli provider działa
        """
        ...


class ProviderError(Exception):
    """Bazowy błąd providera."""
    
    def __init__(self, message: str, provider: str = "unknown"):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")


class ConnectionError(ProviderError):
    """Błąd połączenia z providerem."""
    pass


class AuthenticationError(ProviderError):
    """Błąd autentykacji (nieprawidłowy klucz)."""
    pass


class RateLimitError(ProviderError):
    """Przekroczono limit zapytań."""
    pass


class ContentBlockedError(ProviderError):
    """Treść zablokowana przez filtry bezpieczeństwa."""
    pass


class ModelNotFoundError(ProviderError):
    """Model nie znaleziony."""
    pass


class TimeoutError(ProviderError):
    """Timeout zapytania."""
    pass
