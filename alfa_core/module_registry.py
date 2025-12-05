"""
ALFA v1.2 — Module Registry
Rejestr modułów dostępnych w systemie.
"""

from __future__ import annotations

from typing import Dict, Optional, Type

from .kernel_contract import BaseModule, BaseModuleConfig, ModuleHealth


class ModuleRegistry:
    """
    Rejestr klas modułów (nie instancji!).
    Kernel tworzy instancje dopiero przy load().
    """

    def __init__(self) -> None:
        self._registered: Dict[str, Type[BaseModule]] = {}
        self._instances: Dict[str, BaseModule] = {}

    # --- Rejestracja klas modułów ---

    def register(self, module_cls: Type[BaseModule]) -> None:
        """Rejestruje klasę modułu."""
        if module_cls.id in self._registered:
            raise ValueError(f"Module ID '{module_cls.id}' already registered")
        self._registered[module_cls.id] = module_cls

    def get_class(self, module_id: str) -> Optional[Type[BaseModule]]:
        return self._registered.get(module_id)

    def get_registered(self) -> Dict[str, Type[BaseModule]]:
        """Zwraca wszystkie zarejestrowane klasy modułów."""
        return dict(self._registered)

    # --- Instancje (żywe moduły) ---

    def create_instance(
        self,
        module_id: str,
        config: Optional[BaseModuleConfig] = None,
        *,
        kernel_context: Optional[dict] = None,
    ) -> BaseModule:

        module_cls = self._registered.get(module_id)
        if not module_cls:
            raise KeyError(f"Module '{module_id}' nie jest zarejestrowany.")

        instance = module_cls(config=config, kernel_context=kernel_context)
        self._instances[module_id] = instance
        return instance

    def get_instance(self, module_id: str) -> Optional[BaseModule]:
        return self._instances.get(module_id)

    def all_instances(self) -> Dict[str, BaseModule]:
        return dict(self._instances)

    # --- Cykl życia modułów ---

    def load_all(self) -> None:
        for module_id, instance in self._instances.items():
            instance.load()

    def unload_all(self) -> None:
        for module_id, instance in self._instances.items():
            instance.unload()

    # --- Health-check ---

    def health(self) -> Dict[str, ModuleHealth]:
        return {mid: inst.health_check() for mid, inst in self._instances.items()}
