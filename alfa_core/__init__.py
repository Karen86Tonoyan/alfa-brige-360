# ═══════════════════════════════════════════════════════════════════════════
# ALFA_CORE — Unified Module Exports
# ═══════════════════════════════════════════════════════════════════════════
"""
ALFA_CORE: Central module for ALFA ecosystem.

Main exports:
  - executor: Unified async-safe executor (v2.0)
  - ExecutionResult: Result type for executions
  - safe_exec, safe_run: Quick execution helpers

Usage:
    from alfa_core import executor
    
    # Async
    result = await executor.execute_func(my_func, arg1)
    
    # Sync
    result = executor.run(my_func, arg1)
    
    # Code
    result = await executor.execute_code("print('hello')")
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

__version__ = "2.0.0"

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
    
    # Version
    "__version__",
]
