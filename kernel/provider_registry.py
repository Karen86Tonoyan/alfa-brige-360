"""
ALFA_CORE_KERNEL v3.0 — PROVIDER REGISTRY
Rejestr i zarządzanie providerami AI.
"""

from typing import Dict, Optional, List, Type
from dataclasses import dataclass
import logging

logger = logging.getLogger("ALFA.ProviderRegistry")


@dataclass
class ProviderInfo:
    """Informacje o zarejestrowanym providerze."""
    name: str
    instance: object
    priority: int = 0
    enabled: bool = True
    healthy: bool = True


class ProviderRegistry:
    """
    Rejestr providerów AI.
    Zarządza cyklem życia i dostępnością providerów.
    """
    
    def __init__(self):
        self._providers: Dict[str, ProviderInfo] = {}
        self._order: List[str] = []  # Kolejność fallback
    
    def register(self, name: str, instance: object, priority: int = 0) -> None:
        """
        Rejestruje providera.
        
        Args:
            name: Unikalna nazwa providera
            instance: Instancja providera (musi mieć metodę generate)
            priority: Priorytet (wyższy = preferowany)
        """
        if not hasattr(instance, 'generate'):
            raise ValueError(f"Provider {name} must have 'generate' method")
        
        self._providers[name] = ProviderInfo(
            name=name,
            instance=instance,
            priority=priority,
            enabled=True,
            healthy=True
        )
        
        # Sortuj kolejność po priorytecie
        self._update_order()
        logger.info(f"Provider registered: {name} (priority={priority})")
    
    def unregister(self, name: str) -> None:
        """Wyrejestrowuje providera."""
        if name in self._providers:
            del self._providers[name]
            self._update_order()
            logger.info(f"Provider unregistered: {name}")
    
    def get(self, name: str) -> Optional[object]:
        """Pobiera instancję providera po nazwie."""
        info = self._providers.get(name)
        if info and info.enabled:
            return info.instance
        return None
    
    def get_info(self, name: str) -> Optional[ProviderInfo]:
        """Pobiera info o providerze."""
        return self._providers.get(name)
    
    def get_best(self) -> Optional[object]:
        """Zwraca najlepszego dostępnego providera."""
        for name in self._order:
            info = self._providers[name]
            if info.enabled and info.healthy:
                return info.instance
        return None
    
    def get_fallback_chain(self) -> List[object]:
        """Zwraca listę providerów w kolejności fallback."""
        chain = []
        for name in self._order:
            info = self._providers[name]
            if info.enabled:
                chain.append(info.instance)
        return chain
    
    def mark_unhealthy(self, name: str) -> None:
        """Oznacza providera jako niezdatnego."""
        if name in self._providers:
            self._providers[name].healthy = False
            logger.warning(f"Provider marked unhealthy: {name}")
    
    def mark_healthy(self, name: str) -> None:
        """Oznacza providera jako zdatnego."""
        if name in self._providers:
            self._providers[name].healthy = True
            logger.info(f"Provider marked healthy: {name}")
    
    def enable(self, name: str) -> None:
        """Włącza providera."""
        if name in self._providers:
            self._providers[name].enabled = True
    
    def disable(self, name: str) -> None:
        """Wyłącza providera."""
        if name in self._providers:
            self._providers[name].enabled = False
    
    def _update_order(self) -> None:
        """Aktualizuje kolejność providerów."""
        self._order = sorted(
            self._providers.keys(),
            key=lambda n: self._providers[n].priority,
            reverse=True
        )
    
    def list_providers(self) -> List[str]:
        """Lista nazw providerów."""
        return list(self._providers.keys())
    
    def status(self) -> Dict[str, Dict]:
        """Status wszystkich providerów."""
        return {
            name: {
                "enabled": info.enabled,
                "healthy": info.healthy,
                "priority": info.priority
            }
            for name, info in self._providers.items()
        }
    
    def __len__(self) -> int:
        return len(self._providers)
    
    def __contains__(self, name: str) -> bool:
        return name in self._providers
