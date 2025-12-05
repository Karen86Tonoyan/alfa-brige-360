# ═══════════════════════════════════════════════════════════════════════════
# ALFA SECURE EXECUTOR v2.0 — UNIFIED ASYNC-SAFE EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════
"""
Unified executor for the entire ALFA ecosystem.

Replaces the need for both:
  - core/secure_executor.py (full sandbox)
  - alfa_brain/core/secure_exec.py (lightweight)

Features:
  ✅ Async-safe execution (no coroutine leaks)
  ✅ Sync function support
  ✅ Sandbox mode with restricted builtins
  ✅ Timeout protection
  ✅ Thread-safe execution
  ✅ Plugin engine compatible
  ✅ Zero deadlocks

Usage:
    from alfa_core.executor import executor
    
    # Execute async function
    result = await executor.execute_func(my_async_func, arg1, arg2)
    
    # Execute code string
    result = await executor.execute_code("print('hello')")
    
    # Sync wrapper (for non-async contexts)
    result = executor.run(my_func, arg1, arg2)

Author: ALFA System / Karen86Tonoyan
Version: 2.0.0
"""

import asyncio
import inspect
import io
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_TIMEOUT = 30  # seconds
MAX_OUTPUT_SIZE = 100_000  # characters
THREAD_POOL_SIZE = 4

# Safe builtins for sandbox mode
SAFE_BUILTINS = {
    # Types
    "bool": bool,
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "frozenset": frozenset,
    "bytes": bytes,
    "bytearray": bytearray,
    
    # Functions
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "callable": callable,
    "chr": chr,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "format": format,
    "hash": hash,
    "hex": hex,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "slice": slice,
    "sorted": sorted,
    "sum": sum,
    "type": type,
    "zip": zip,
    
    # Constants
    "True": True,
    "False": False,
    "None": None,
    
    # Exceptions (read-only)
    "Exception": Exception,
    "TypeError": TypeError,
    "ValueError": ValueError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
    "RuntimeError": RuntimeError,
    "StopIteration": StopIteration,
}

# ═══════════════════════════════════════════════════════════════════════════
# RESULT TYPES
# ═══════════════════════════════════════════════════════════════════════════

class ResultStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


@dataclass
class ExecutionResult:
    """Unified result type for all executions."""
    status: ResultStatus
    value: Any = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    traceback: Optional[str] = None
    execution_time: float = 0.0
    
    @property
    def success(self) -> bool:
        return self.status == ResultStatus.SUCCESS
    
    @property
    def ok(self) -> bool:
        return self.success
    
    def __bool__(self) -> bool:
        return self.success


# ═══════════════════════════════════════════════════════════════════════════
# UNIFIED EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════

class UnifiedExecutor:
    """
    Unified async-safe executor for ALFA ecosystem.
    
    Handles:
      - async def functions
      - sync functions
      - sync functions returning coroutines
      - code strings (sandbox)
      - timeout protection
      - proper cleanup
    """
    
    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        sandbox: bool = True,
        max_output: int = MAX_OUTPUT_SIZE
    ):
        self.timeout = timeout
        self.sandbox = sandbox
        self.max_output = max_output
        self._thread_pool = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)
        self._lock = threading.Lock()
    
    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC: Execute function (async-safe)
    # ─────────────────────────────────────────────────────────────────────
    
    async def execute_func(
        self,
        func: Callable,
        *args,
        timeout: Optional[float] = None,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a function, handling both sync and async transparently.
        
        Args:
            func: Function to execute (sync or async)
            *args: Positional arguments
            timeout: Override default timeout
            **kwargs: Keyword arguments
            
        Returns:
            ExecutionResult with value or error
        """
        timeout = timeout or self.timeout
        start_time = time.time()
        
        try:
            # Case 1: async function
            if inspect.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout
                )
                return ExecutionResult(
                    status=ResultStatus.SUCCESS,
                    value=result,
                    execution_time=time.time() - start_time
                )
            
            # Case 2: sync function (run in thread pool)
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    self._thread_pool,
                    lambda: func(*args, **kwargs)
                ),
                timeout=timeout
            )
            
            # Case 3: sync returned a coroutine
            if inspect.iscoroutine(result):
                result = await asyncio.wait_for(result, timeout=timeout)
            
            return ExecutionResult(
                status=ResultStatus.SUCCESS,
                value=result,
                execution_time=time.time() - start_time
            )
            
        except asyncio.TimeoutError:
            return ExecutionResult(
                status=ResultStatus.TIMEOUT,
                error=f"Execution timeout after {timeout}s",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ExecutionResult(
                status=ResultStatus.ERROR,
                error=str(e),
                traceback=traceback.format_exc(),
                execution_time=time.time() - start_time
            )
    
    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC: Execute code string (sandbox)
    # ─────────────────────────────────────────────────────────────────────
    
    async def execute_code(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        sandbox: Optional[bool] = None,
        timeout: Optional[float] = None
    ) -> ExecutionResult:
        """
        Execute Python code string in sandbox.
        
        Args:
            code: Python code to execute
            context: Variables to inject
            sandbox: Override default sandbox mode
            timeout: Override default timeout
            
        Returns:
            ExecutionResult with output or error
        """
        timeout = timeout or self.timeout
        sandbox = sandbox if sandbox is not None else self.sandbox
        start_time = time.time()
        
        # Prepare execution environment
        if sandbox:
            exec_globals = {"__builtins__": SAFE_BUILTINS.copy()}
        else:
            exec_globals = {"__builtins__": __builtins__}
        
        if context:
            exec_globals.update(context)
        
        exec_locals: Dict[str, Any] = {}
        
        # Capture stdout/stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        def run_code():
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            try:
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture
                compiled = compile(code, "<sandbox>", "exec")
                exec(compiled, exec_globals, exec_locals)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
        
        try:
            loop = asyncio.get_running_loop()
            await asyncio.wait_for(
                loop.run_in_executor(self._thread_pool, run_code),
                timeout=timeout
            )
            
            # Check for return value
            return_value = exec_locals.get("_result_") or exec_locals.get("result")
            
            # Check for async result (plugin pattern)
            if "_alfa" in exec_locals:
                alfa_result = exec_locals["_alfa"]
                if inspect.iscoroutine(alfa_result):
                    return_value = await asyncio.wait_for(alfa_result, timeout=timeout)
                elif inspect.iscoroutinefunction(alfa_result):
                    return_value = await asyncio.wait_for(alfa_result(), timeout=timeout)
                elif callable(alfa_result):
                    return_value = alfa_result()
                else:
                    return_value = alfa_result
            
            stdout = stdout_capture.getvalue()[:self.max_output]
            stderr = stderr_capture.getvalue()[:self.max_output]
            
            return ExecutionResult(
                status=ResultStatus.SUCCESS,
                value=return_value,
                stdout=stdout,
                stderr=stderr,
                execution_time=time.time() - start_time
            )
            
        except asyncio.TimeoutError:
            return ExecutionResult(
                status=ResultStatus.TIMEOUT,
                error=f"Code execution timeout after {timeout}s",
                stdout=stdout_capture.getvalue()[:self.max_output],
                stderr=stderr_capture.getvalue()[:self.max_output],
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ExecutionResult(
                status=ResultStatus.ERROR,
                error=str(e),
                traceback=traceback.format_exc(),
                stdout=stdout_capture.getvalue()[:self.max_output],
                stderr=stderr_capture.getvalue()[:self.max_output],
                execution_time=time.time() - start_time
            )
    
    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC: Sync wrapper (for non-async contexts)
    # ─────────────────────────────────────────────────────────────────────
    
    def run(
        self,
        func: Callable,
        *args,
        timeout: Optional[float] = None,
        **kwargs
    ) -> ExecutionResult:
        """
        Sync wrapper for execute_func.
        
        Use when not in async context.
        Creates new event loop if needed.
        """
        timeout = timeout or self.timeout
        
        # Check if we're in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in async context - use thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.execute_func(func, *args, timeout=timeout, **kwargs)
                )
                return future.result(timeout=timeout + 5)
        except RuntimeError:
            # No running loop - create one
            return asyncio.run(
                self.execute_func(func, *args, timeout=timeout, **kwargs)
            )
    
    def run_code(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        sandbox: Optional[bool] = None,
        timeout: Optional[float] = None
    ) -> ExecutionResult:
        """Sync wrapper for execute_code."""
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.execute_code(code, context, sandbox, timeout)
                )
                return future.result(timeout=(timeout or self.timeout) + 5)
        except RuntimeError:
            return asyncio.run(
                self.execute_code(code, context, sandbox, timeout)
            )
    
    # ─────────────────────────────────────────────────────────────────────
    # LEGACY COMPATIBILITY
    # ─────────────────────────────────────────────────────────────────────
    
    def execute(self, code: str, context: Dict[str, Any] = None) -> ExecutionResult:
        """Legacy interface - sync code execution."""
        return self.run_code(code, context)
    
    async def execute_async(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> ExecutionResult:
        """Legacy interface - async function execution."""
        return await self.execute_func(func, *args, **kwargs)
    
    # ─────────────────────────────────────────────────────────────────────
    # CLEANUP
    # ─────────────────────────────────────────────────────────────────────
    
    def shutdown(self):
        """Cleanup thread pool."""
        self._thread_pool.shutdown(wait=False)
    
    def __del__(self):
        try:
            self.shutdown()
        except:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON & CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

# Global singleton
executor = UnifiedExecutor()


def get_executor(
    timeout: float = DEFAULT_TIMEOUT,
    sandbox: bool = True
) -> UnifiedExecutor:
    """Get or create executor instance."""
    return UnifiedExecutor(timeout=timeout, sandbox=sandbox)


async def safe_exec(func: Callable, *args, **kwargs) -> ExecutionResult:
    """Quick async execution."""
    return await executor.execute_func(func, *args, **kwargs)


def safe_run(func: Callable, *args, **kwargs) -> ExecutionResult:
    """Quick sync execution."""
    return executor.run(func, *args, **kwargs)


async def safe_code(code: str, **kwargs) -> ExecutionResult:
    """Quick async code execution."""
    return await executor.execute_code(code, **kwargs)


def run_code(code: str, **kwargs) -> ExecutionResult:
    """Quick sync code execution."""
    return executor.run_code(code, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

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
]
