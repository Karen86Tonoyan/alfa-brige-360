"""
ALFA_CORE_KERNEL v3.0 — AUTOSWITCH
Automatyczne przełączanie między providerami z fallback.
"""

from typing import Optional, List, Callable
import logging
import time

logger = logging.getLogger("ALFA.AutoSwitch")


class AutoSwitch:
    """
    Automatyczne przełączanie providerów.
    Gemini → DeepSeek → Local → Error
    """
    
    def __init__(self, providers: List[object], max_retries: int = 2):
        """
        Args:
            providers: Lista providerów w kolejności preferencji
            max_retries: Maksymalna liczba prób na providera
        """
        self.providers = providers
        self.max_retries = max_retries
        self.current_index = 0
        self._failure_counts = {i: 0 for i in range(len(providers))}
        self._last_success = {i: 0 for i in range(len(providers))}
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generuje odpowiedź z automatycznym fallback.
        """
        errors = []
        
        for i, provider in enumerate(self.providers):
            provider_name = getattr(provider, 'name', f'provider_{i}')
            
            for retry in range(self.max_retries):
                try:
                    logger.debug(f"Trying {provider_name} (attempt {retry + 1})")
                    
                    # Wywołaj generate
                    if system_prompt and hasattr(provider, 'generate'):
                        result = provider.generate(prompt, system_prompt)
                    else:
                        result = provider.generate(prompt)
                    
                    # Sprawdź czy to nie jest błąd
                    if result and not result.startswith("[ERROR]") and not result.startswith("[GEMINI ERROR]"):
                        self._failure_counts[i] = 0
                        self._last_success[i] = time.time()
                        self.current_index = i
                        logger.info(f"Success with {provider_name}")
                        return result
                    
                    # To jest błąd w odpowiedzi
                    errors.append(f"{provider_name}: {result[:100]}")
                    
                except Exception as e:
                    self._failure_counts[i] += 1
                    errors.append(f"{provider_name}: {str(e)[:100]}")
                    logger.warning(f"{provider_name} failed: {e}")
            
            # Ten provider zawiódł, idziemy do następnego
            logger.warning(f"Provider {provider_name} exhausted, trying next...")
        
        # Wszystkie providery zawiodły
        error_summary = " | ".join(errors[-3:])  # Ostatnie 3 błędy
        return f"[ALL_PROVIDERS_FAILED] {error_summary}"
    
    def get_current_provider(self) -> Optional[object]:
        """Zwraca aktualnie używanego providera."""
        if 0 <= self.current_index < len(self.providers):
            return self.providers[self.current_index]
        return None
    
    def reset(self) -> None:
        """Resetuje stan autoswitch."""
        self.current_index = 0
        self._failure_counts = {i: 0 for i in range(len(self.providers))}
    
    def status(self) -> dict:
        """Zwraca status autoswitch."""
        return {
            "current_index": self.current_index,
            "total_providers": len(self.providers),
            "failure_counts": self._failure_counts,
            "providers": [
                getattr(p, 'name', f'provider_{i}')
                for i, p in enumerate(self.providers)
            ]
        }
