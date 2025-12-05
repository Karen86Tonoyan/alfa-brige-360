"""
ALFA v1.2 — Loader
Ładowanie modułów i konfiguracji według kontraktu.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, List, Type
import importlib
import pkgutil

from .kernel_contract import BaseModule, BaseModuleConfig
from .module_registry import ModuleRegistry


class KernelLoader:
    """
    Loader odpowiedzialny za:
    - wykrywanie modułów
    - ładowanie konfiguracji
    - tworzenie instancji modułów
    """

    def __init__(
        self,
        registry: ModuleRegistry,
        *,
        config_map: Optional[Dict[str, BaseModuleConfig]] = None,
        kernel_context: Optional[dict] = None,
        module_paths: Optional[List[str]] = None,
    ) -> None:
        self.registry = registry
        self.config_map = config_map or {}
        self.kernel_context = kernel_context or {}
        self.module_paths = module_paths or ["alfa_core.modules"]

    # --- Discovery modułów ---

    def discover(self) -> List[Type[BaseModule]]:
        """
        Automatyczne skanowanie pakietów w poszukiwaniu modułów.
        Szuka klas dziedziczących po BaseModule.
        """
        discovered: List[Type[BaseModule]] = []

        for package_path in self.module_paths:
            try:
                package = importlib.import_module(package_path)
                if hasattr(package, "__path__"):
                    for importer, modname, ispkg in pkgutil.walk_packages(
                        package.__path__, prefix=package.__name__ + "."
                    ):
                        try:
                            module = importlib.import_module(modname)
                            for attr_name in dir(module):
                                attr = getattr(module, attr_name)
                                if (
                                    isinstance(attr, type)
                                    and issubclass(attr, BaseModule)
                                    and attr is not BaseModule
                                    and hasattr(attr, "id")
                                ):
                                    if attr.id not in [c.id for c in discovered]:
                                        discovered.append(attr)
                        except Exception:
                            pass  # Skip broken modules
            except ImportError:
                pass  # Package not found

        return discovered

    def auto_register(self) -> int:
        """Odkryj i zarejestruj wszystkie moduły."""
        modules = self.discover()
        count = 0
        for module_cls in modules:
            try:
                self.registry.register(module_cls)
                count += 1
            except ValueError:
                pass  # Already registered
        return count

    # --- Tworzenie instancji ---

    def instantiate_all(self) -> None:
        """Tworzy instancje wszystkich zarejestrowanych modułów."""
        for module_id in self.registry.get_registered():
            cfg = self.config_map.get(module_id)
            instance = self.registry.create_instance(
                module_id,
                config=cfg,
                kernel_context=self.kernel_context,
            )
            instance.load()

    def instantiate_one(self, module_id: str) -> Optional[BaseModule]:
        """Tworzy instancję konkretnego modułu."""
        if module_id not in self.registry.get_registered():
            return None
        
        cfg = self.config_map.get(module_id)
        instance = self.registry.create_instance(
            module_id,
            config=cfg,
            kernel_context=self.kernel_context,
        )
        instance.load()
        return instance

    # --- Zamknięcie ---

    def shutdown(self) -> None:
        """Zamyka wszystkie moduły."""
        self.registry.unload_all()
