"""
ALFA Security Watchdog v1.2
Monitoruje kernel, moduły i anomalie.
Reaguje automatycznie na błędy i stany nieprawidłowe.
Obsługuje PREDATOR MODE - blokowanie niestabilnych modułów.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from alfa_core.kernel_contract import BaseModule, BaseModuleConfig, CommandResult, ModuleHealth


class SecurityWatchdogConfig(BaseModuleConfig):
    """Konfiguracja Security Watchdog."""
    def __init__(
        self,
        heartbeat_interval: float = 3.0,
        restart_limit: int = 3,
        predator_mode: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.heartbeat_interval = heartbeat_interval
        self.restart_limit = restart_limit
        self.predator_mode = predator_mode


class SecurityWatchdog(BaseModule):
    """
    Security Watchdog - 8-Layer Defense System
    
    Warstwy ochrony:
    1. Heartbeat monitoring
    2. Module health tracking
    3. Anomaly logging
    4. Auto-restart modułów
    5. Predator Mode (blokowanie)
    6. Rate limiting
    7. Audit trail
    8. Kernel protection
    """

    id = "security.watchdog"
    version = "1.2.0"

    def __init__(
        self,
        config: Optional[SecurityWatchdogConfig] = None,
        kernel_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(config or SecurityWatchdogConfig(), kernel_context)
        self.config: SecurityWatchdogConfig
        
        # Heartbeat tracking
        self.last_heartbeat: float = time.time()
        self.heartbeat_interval: float = getattr(self.config, 'heartbeat_interval', 3.0)
        
        # Anomaly tracking
        self.anomaly_log: List[Dict[str, Any]] = []
        
        # Module stability tracking
        self.unstable_modules: Dict[str, int] = {}  # module_id -> error count
        self.restart_limit: int = getattr(self.config, 'restart_limit', 3)
        
        # Predator Mode
        self.predator_mode: bool = getattr(self.config, 'predator_mode', True)
        self.blocked_modules: Set[str] = set()
        
        # Rate limiting
        self.command_timestamps: Dict[str, List[float]] = {}
        self.rate_limit_window: float = 60.0  # 1 minute
        self.rate_limit_max: int = 100  # max commands per window

    # -------------------------
    #  LIFECYCLE
    # -------------------------

    def load(self) -> None:
        """Inicjalizacja watchdog'a."""
        self._loaded = True
        self._log("Watchdog loaded and active.")
        self._log(f"Predator Mode: {'ENABLED' if self.predator_mode else 'DISABLED'}")

    def unload(self) -> None:
        """Zamknięcie watchdog'a."""
        self._log("Watchdog shutting down.")
        self._loaded = False

    # -------------------------
    #  HEALTH CHECK
    # -------------------------

    def health_check(self) -> ModuleHealth:
        """Sprawdza zdrowie watchdog'a."""
        now = time.time()
        delta = now - self.last_heartbeat

        if delta > self.heartbeat_interval * 3:
            return ModuleHealth(
                healthy=False,
                status="error",
                details={
                    "error": "Kernel heartbeat lost",
                    "last_seen_sec": round(delta, 2),
                    "events": len(self.anomaly_log),
                    "blocked": len(self.blocked_modules),
                },
            )

        return ModuleHealth(
            healthy=True,
            status="running",
            details={
                "last_heartbeat_sec": round(delta, 2),
                "events": len(self.anomaly_log),
                "unstable_modules": len(self.unstable_modules),
                "blocked_modules": len(self.blocked_modules),
                "predator_mode": self.predator_mode,
            },
        )

    # -------------------------
    #  EXECUTE (Command Router)
    # -------------------------

    def execute(self, command: str, **kwargs: Any) -> CommandResult:
        """Wykonuje komendę watchdog'a."""
        
        # === HEARTBEAT ===
        if command == "heartbeat":
            self.last_heartbeat = time.time()
            return CommandResult.success({"watchdog": "alive", "timestamp": self.last_heartbeat})

        # === STATUS ===
        if command == "status":
            health = self.health_check()
            return CommandResult.success({
                "healthy": health.healthy,
                "status": health.status,
                "details": health.details,
            })

        # === ANOMALIES ===
        if command == "anomalies":
            limit = kwargs.get("limit", 50)
            return CommandResult.success({
                "total": len(self.anomaly_log),
                "anomalies": self.anomaly_log[-limit:],
            })

        # === LOG ANOMALY ===
        if command == "log":
            entry = kwargs.get("entry", {})
            entry["timestamp"] = datetime.utcnow().isoformat()
            self.anomaly_log.append(entry)
            self._log(f"Anomaly logged: {entry}")
            return CommandResult.success({"logged": entry})

        # === MODULE ERROR (auto-restart/block) ===
        if command == "module_error":
            return self._handle_module_error(**kwargs)

        # === PREDATOR MODE CONTROL ===
        if command == "predator_on":
            self.predator_mode = True
            self._log("Predator Mode ENABLED")
            return CommandResult.success({"predator_mode": True})

        if command == "predator_off":
            self.predator_mode = False
            self._log("Predator Mode DISABLED")
            return CommandResult.success({"predator_mode": False})

        # === POLICY ===
        if command == "policy":
            return CommandResult.success({
                "predator_mode": self.predator_mode,
                "restart_limit": self.restart_limit,
                "rate_limit_max": self.rate_limit_max,
                "unstable": dict(self.unstable_modules),
                "blocked": list(self.blocked_modules),
            })

        # === UNBLOCK MODULE ===
        if command == "unblock":
            module_id = kwargs.get("target_module_id") or kwargs.get("module_id")
            if not module_id:
                return CommandResult.failure("No module_id provided")
            
            if module_id in self.blocked_modules:
                self.blocked_modules.remove(module_id)
                self.unstable_modules.pop(module_id, None)
                self._log(f"Module '{module_id}' UNBLOCKED by operator.")
                return CommandResult.success({"unblocked": module_id})
            
            return CommandResult.failure(f"Module '{module_id}' is not blocked")

        # === RESET STATS ===
        if command == "reset":
            self.unstable_modules.clear()
            self.blocked_modules.clear()
            self.anomaly_log.clear()
            self._log("Watchdog stats reset")
            return CommandResult.success({"reset": True})

        return CommandResult.failure(f"Unknown command: {command}")

    # -------------------------
    #  MODULE ERROR HANDLING
    # -------------------------

    def _handle_module_error(self, **kwargs) -> CommandResult:
        """Obsługuje błąd modułu - restart lub blokada."""
        module_id = kwargs.get("failed_module_id") or kwargs.get("module_id")
        error = kwargs.get("error", "Unknown error")

        if not module_id:
            return CommandResult.failure("No module_id provided")

        # Skip self-errors
        if module_id == self.id:
            return CommandResult.success({"skipped": "self"})

        # Log anomaly
        entry = {
            "module": module_id,
            "error": str(error),
            "type": "module_crash",
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.anomaly_log.append(entry)
        self._log(f"ANOMALY: module '{module_id}' crashed → {error}")

        # Count errors
        self.unstable_modules[module_id] = self.unstable_modules.get(module_id, 0) + 1
        attempts = self.unstable_modules[module_id]

        # If Predator OFF -> only log
        if not self.predator_mode:
            return CommandResult.success({
                "mode": "log_only",
                "attempts": attempts,
                "restart": False,
            })

        # Try restart if under limit
        if attempts <= self.restart_limit:
            self._log(f"Restarting module '{module_id}' (attempt {attempts}/{self.restart_limit})")
            
            kernel = self.kernel
            if kernel and hasattr(kernel, 'restart_module'):
                ok = kernel.restart_module(module_id)
                return CommandResult.success({
                    "mode": "restart",
                    "attempts": attempts,
                    "restart_ok": ok,
                })
            
            return CommandResult.success({
                "mode": "restart_requested",
                "attempts": attempts,
                "note": "No kernel access for restart",
            })

        # Over limit -> BLOCK
        self._log(f"Module '{module_id}' BLOCKED (attempts={attempts}, predator_mode=ON)")
        self.blocked_modules.add(module_id)
        
        return CommandResult.failure(
            f"Module '{module_id}' blocked by watchdog",
            module=module_id,
        )

    # -------------------------
    #  RATE LIMITING
    # -------------------------

    def check_rate_limit(self, identifier: str) -> bool:
        """
        Sprawdza rate limit dla identyfikatora.
        Returns True jeśli w limicie, False jeśli przekroczony.
        """
        now = time.time()
        
        if identifier not in self.command_timestamps:
            self.command_timestamps[identifier] = []
        
        # Usuń stare timestampy
        self.command_timestamps[identifier] = [
            ts for ts in self.command_timestamps[identifier]
            if now - ts < self.rate_limit_window
        ]
        
        # Sprawdź limit
        if len(self.command_timestamps[identifier]) >= self.rate_limit_max:
            self._log(f"Rate limit exceeded for '{identifier}'")
            return False
        
        # Dodaj nowy timestamp
        self.command_timestamps[identifier].append(now)
        return True

    # -------------------------
    #  INTERNAL LOGGING
    # -------------------------

    def _log(self, msg: str) -> None:
        """Wewnętrzny logger."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[WATCHDOG {timestamp}] {msg}")
