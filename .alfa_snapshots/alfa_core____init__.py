# ═══════════════════════════════════════════════════════════════════════════
# ALFA_CORE — Unified Module Exports v1.2
# ═══════════════════════════════════════════════════════════════════════════
"""
ALFA_CORE: Central module for ALFA ecosystem.

Main exports:
  - AlfaKernel: Main kernel with dispatch, health, restart
  - executor: Unified async-safe executor (v2.0)
  - SecurityWatchdog: 8-layer security monitoring

Usage:
    from alfa_core import AlfaKernel
    from modules import SecurityWatchdog
    
    kernel = AlfaKernel()
    kernel.register_module(SecurityWatchdog)
    kernel.start()
    
    result = kernel.dispatch("security.watchdog", "status")
"""

from .executor import (
    # Main executor
    UnifiedExecutor,
    executor,
    get_executor,
    
    # Result types
    ExecutionResult,
    ResultStatus,
    
    # Quick functions
    safe_exec,
    safe_run,
    safe_code,
    run_code,
    
    # Constants
    SAFE_BUILTINS,
    DEFAULT_TIMEOUT,
)

# Kernel v1.2
from .kernel_contract import (
    BaseModule,
    BaseModuleConfig,
    CommandResult,
    ModuleHealth,
    ExampleEchoModule,
    ExampleEchoConfig,
)
from .module_registry import ModuleRegistry
from .loader import KernelLoader
from .kernel import AlfaKernel

__version__ = "2.1.0"

__all__ = [
    # Classes
    "UnifiedExecutor",
    "ExecutionResult", 
    "ResultStatus",
    
    # Singleton
    "executor",
    
    # Factory
    "get_executor",
    
    # Quick functions
    "safe_exec",
    "safe_run",
    "safe_code",
    "run_code",
    
    # Constants
    "SAFE_BUILTINS",
    "DEFAULT_TIMEOUT",
    
    # Kernel v1.2
    "AlfaKernel",
    "ModuleRegistry",
    "KernelLoader",
    "BaseModule",
    "BaseModuleConfig",
    "CommandResult",
    "ModuleHealth",
    "ExampleEchoModule",
    "ExampleEchoConfig",
    
    # Version
    "__version__",
]
