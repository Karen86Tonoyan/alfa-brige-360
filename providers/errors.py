"""
ALFA_CORE_KERNEL v3.0 — PROVIDER ERRORS
Wyjątki dla providerów AI.
"""


class ProviderError(Exception):
    """Bazowy błąd providera."""
    pass


class ProviderConnectionError(ProviderError):
    """Błąd połączenia z API."""
    pass


class ProviderAuthError(ProviderError):
    """Błąd autoryzacji (zły klucz)."""
    pass


class ProviderRateLimitError(ProviderError):
    """Przekroczono limit zapytań."""
    pass


class ProviderResponseError(ProviderError):
    """Błąd w odpowiedzi API."""
    pass


class NoProviderAvailableError(ProviderError):
    """Żaden provider nie jest dostępny."""
    pass
