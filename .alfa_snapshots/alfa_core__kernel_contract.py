"""
ALFA v1.2 — Kernel Contract
Bazowe klasy i interfejsy dla modułów systemu.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime


# =============================================================================
# COMMAND RESULT
# =============================================================================

@dataclass
class CommandResult:
    """Wynik wykonania komendy przez moduł."""
    ok: bool
    data: Any = None
    error: Optional[str] = None
    module: Optional[str] = None
    command: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    def success(cls, data: Any = None, **kwargs) -> "CommandResult":
        return cls(ok=True, data=data, **kwargs)

    @classmethod
    def failure(cls, error: str, **kwargs) -> "CommandResult":
        return cls(ok=False, error=error, **kwargs)

    def __repr__(self) -> str:
        if self.ok:
            return f"CommandResult(ok=True, data={self.data!r})"
        return f"CommandResult(ok=False, error={self.error!r})"


# =============================================================================
# MODULE HEALTH
# =============================================================================

@dataclass
class ModuleHealth:
    """Stan zdrowia modułu."""
    healthy: bool
    status: str  # "running", "stopped", "error", "degraded"
    details: Dict[str, Any] = field(default_factory=dict)
    last_check: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    def ok(cls, details: Optional[Dict] = None) -> "ModuleHealth":
        return cls(healthy=True, status="running", details=details or {})

    @classmethod
    def error(cls, reason: str) -> "ModuleHealth":
        return cls(healthy=False, status="error", details={"reason": reason})


# =============================================================================
# BASE MODULE CONFIG
# =============================================================================

@dataclass
class BaseModuleConfig:
    """Bazowa konfiguracja modułu. Moduły dziedziczą i rozszerzają."""
    enabled: bool = True
    log_level: str = "INFO"
    timeout: int = 30
    
    def __init__(self, **kwargs):
        """Pozwala na dowolne parametry w podklasach."""
        for key, value in kwargs.items():
            setattr(self, key, value)
        # Ustaw domyślne wartości jeśli nie podano
        if not hasattr(self, 'enabled'):
            self.enabled = True
        if not hasattr(self, 'log_level'):
            self.log_level = "INFO"
        if not hasattr(self, 'timeout'):
            self.timeout = 30


# =============================================================================
# BASE MODULE
# =============================================================================

class BaseModule(ABC):
    """
    Bazowa klasa modułu ALFA.
    Każdy moduł musi:
    - mieć unikalne `id`
    - implementować `execute()`
    - opcjonalnie: load(), unload(), health_check()
    """

    id: str = "base.module"  # Override w podklasie
    version: str = "1.0.0"

    def __init__(
        self,
        config: Optional[BaseModuleConfig] = None,
        kernel_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.config = config or BaseModuleConfig()
        self.kernel_context = kernel_context or {}
        self._loaded = False

    @property
    def kernel(self):
        """Dostęp do kernela (jeśli przekazany w kontekście)."""
        return self.kernel_context.get("kernel")

    # --- Lifecycle ---

    def load(self) -> None:
        """Inicjalizacja modułu. Wywoływane przez kernel."""
        self._loaded = True

    def unload(self) -> None:
        """Zamknięcie modułu. Wywoływane przy shutdown."""
        self._loaded = False

    # --- Execution ---

    @abstractmethod
    def execute(self, command: str, **kwargs: Any) -> CommandResult:
        """
        Wykonaj komendę. Każdy moduł implementuje własną logikę.
        """
        pass

    # --- Health ---

    def health_check(self) -> ModuleHealth:
        """Domyślny health-check. Moduły mogą nadpisać."""
        if self._loaded:
            return ModuleHealth.ok({"loaded": True})
        return ModuleHealth.error("Module not loaded")


# =============================================================================
# EXAMPLE MODULE (do testów)
# =============================================================================

@dataclass
class ExampleEchoConfig(BaseModuleConfig):
    """Konfiguracja modułu Echo."""
    prefix: str = "[ECHO]"


class ExampleEchoModule(BaseModule):
    """Prosty moduł do testowania kernela."""

    id = "example.echo"
    version = "1.0.0"

    def __init__(
        self,
        config: Optional[ExampleEchoConfig] = None,
        kernel_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(config or ExampleEchoConfig(), kernel_context)
        self.config: ExampleEchoConfig

    def execute(self, command: str, **kwargs: Any) -> CommandResult:
        if command == "echo":
            return CommandResult.success({
                "received": kwargs,
                "prefix": self.config.prefix,
            })
        elif command == "ping":
            return CommandResult.success("pong")
        else:
            return CommandResult.failure(f"Unknown command: {command}")

    def health_check(self) -> ModuleHealth:
        return ModuleHealth.ok({
            "loaded": self._loaded,
            "prefix": self.config.prefix,
        })
