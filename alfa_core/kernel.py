"""
ALFA v1.2 — Kernel
Centralny router komend, delegacja do modułów, context manager.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .kernel_contract import CommandResult, BaseModule
from .module_registry import ModuleRegistry
from .loader import KernelLoader


class AlfaKernel:
    """
    Serce systemu. Umożliwia:
    - rejestrowanie modułów
    - ładowanie modułów
    - dispatch komend
    - health-checki
    - restart modułów
    - blokowanie przez watchdog
    """

    def __init__(self, *, config_map: Dict[str, Any] | None = None) -> None:
        self.registry = ModuleRegistry()
        self.config_map = config_map or {}
        self.loader = KernelLoader(
            registry=self.registry,
            config_map=self.config_map,
            kernel_context={"kernel": self},
        )
        self._ready = False

    # --- Rejestracja modułów ---

    def register_module(self, module_cls) -> None:
        """Rejestruje klasę modułu."""
        self.registry.register(module_cls)

    # --- Start kernela ---

    def start(self) -> None:
        """
        Tworzy instancje, ładuje moduły i przygotowuje kernel do pracy.
        """
        # Auto-discovery (opcjonalnie)
        self.loader.discover()
        
        # Tworzenie instancji wszystkich zarejestrowanych modułów
        self.loader.instantiate_all()
        
        self._ready = True

        # Pierwszy heartbeat do watchdog'a (jeśli istnieje)
        if self.registry.get_instance("security.watchdog"):
            self.dispatch("security.watchdog", "heartbeat")

    # --- Zatrzymanie kernela ---

    def stop(self) -> None:
        """Zatrzymuje kernel i zamyka wszystkie moduły."""
        self.loader.shutdown()
        self._ready = False

    # --- Heartbeat ---

    def heartbeat(self) -> None:
        """
        Wysyła heartbeat do watchdog'a.
        Wołaj z głównej pętli aplikacji.
        """
        if not self._ready:
            return
        if self.registry.get_instance("security.watchdog"):
            self.dispatch("security.watchdog", "heartbeat")

    # --- Blokada modułów (Predator Mode) ---

    def _is_module_blocked(self, module_id: str) -> bool:
        """
        Sprawdza, czy moduł jest zablokowany przez watchdog.
        """
        wd = self.registry.get_instance("security.watchdog")
        if not wd:
            return False
        blocked = getattr(wd, "blocked_modules", set())
        return module_id in blocked

    # --- Restart modułu ---

    def restart_module(self, module_id: str) -> bool:
        """
        Restartuje instancję modułu:
        1. wywołuje unload()
        2. tworzy nową instancję
        3. wywołuje load()
        """
        instance = self.registry.get_instance(module_id)
        if not instance:
            return False

        try:
            # Zamknij stary
            instance.unload()

            # Pobierz klasę modułu
            module_cls = self.registry.get_class(module_id)
            if not module_cls:
                return False

            # Stwórz nowy
            new_instance = module_cls(
                config=self.config_map.get(module_id),
                kernel_context={"kernel": self},
            )

            # Nadpisz instancję
            self.registry._instances[module_id] = new_instance

            # Załaduj nowy
            new_instance.load()

            return True

        except Exception as e:
            print(f"[KERNEL] restart_module error: {e}")
            return False

    # --- Dispatch komend ---

    def dispatch(self, module_id: str, command: str, **kwargs: Any) -> CommandResult:
        """
        Wywołuje moduł wykonujący komendę.
        """
        if not self._ready:
            return CommandResult.failure("Kernel is not started")

        # Sprawdź blokadę przez watchdog
        if self._is_module_blocked(module_id):
            return CommandResult.failure(
                f"Module '{module_id}' is blocked by security watchdog",
                module=module_id,
                command=command,
            )

        instance = self.registry.get_instance(module_id)
        if not instance:
            return CommandResult.failure(f"Module '{module_id}' not loaded")

        try:
            return instance.execute(command, **kwargs)
        except Exception as e:
            # Informujemy watchdog o błędzie modułu
            if self.registry.get_instance("security.watchdog"):
                self.dispatch(
                    "security.watchdog",
                    "module_error",
                    failed_module_id=module_id,
                    error=str(e),
                )
            return CommandResult.failure(str(e), module=module_id, command=command)

    # --- Health check ---

    def health(self) -> Dict[str, Any]:
        """Zwraca status zdrowia kernela i wszystkich modułów."""
        return {
            "ready": self._ready,
            "modules": {
                mid: h.details for mid, h in self.registry.health().items()
            },
        }

    # --- Info ---

    def info(self) -> Dict[str, Any]:
        """Zwraca informacje o kernelu."""
        return {
            "ready": self._ready,
            "registered_modules": list(self.registry.get_registered().keys()),
            "loaded_modules": list(self.registry.all_instances().keys()),
        }
