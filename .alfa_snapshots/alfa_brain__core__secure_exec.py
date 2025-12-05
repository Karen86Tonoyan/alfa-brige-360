# ═══════════════════════════════════════════════════════════════════════════
# ALFA_BRAIN v2.0 — SECURE EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════
"""
Sandbox code execution with AST validation and timeout protection.

Usage:
    from core.secure_exec import SecureExecutor
    
    executor = SecureExecutor()
    result = executor.execute("print('Hello')")
    
    # Async execution
    result = await executor.execute_async(some_async_func, arg1, arg2)
"""

import ast
import asyncio
import inspect
import logging
import sys
import io
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set

LOG = logging.getLogger("alfa.executor")

# Forbidden imports and calls
FORBIDDEN_MODULES = {
    "os", "subprocess", "shutil", "sys", "importlib",
    "ctypes", "socket", "http", "urllib", "requests",
    "pickle", "marshal", "builtins", "__builtins__"
}

FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "open", "input",
    "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "hasattr"
}

# ═══════════════════════════════════════════════════════════════════════════
# RESULT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ExecutionResult:
    success: bool
    output: str = ""
    error: Optional[str] = None
    return_value: Any = None
    execution_time_ms: float = 0.0

# ═══════════════════════════════════════════════════════════════════════════
# AST VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

class ASTValidator(ast.NodeVisitor):
    """Validate AST for dangerous constructs."""
    
    def __init__(self):
        self.violations: List[str] = []
    
    def visit_Import(self, node):
        for alias in node.names:
            module = alias.name.split(".")[0]
            if module in FORBIDDEN_MODULES:
                self.violations.append(f"Forbidden import: {alias.name}")
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        if node.module:
            module = node.module.split(".")[0]
            if module in FORBIDDEN_MODULES:
                self.violations.append(f"Forbidden import from: {node.module}")
        self.generic_visit(node)
    
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                self.violations.append(f"Forbidden call: {node.func.id}")
        self.generic_visit(node)
    
    def validate(self, code: str) -> List[str]:
        """Validate code and return list of violations."""
        try:
            tree = ast.parse(code)
            self.visit(tree)
            return self.violations
        except SyntaxError as e:
            return [f"Syntax error: {e}"]

# ═══════════════════════════════════════════════════════════════════════════
# SECURE EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════

class SecureExecutor:
    """Sandbox code executor with safety checks."""
    
    def __init__(self, timeout: float = 5.0, max_output: int = 10000):
        self.timeout = timeout
        self.max_output = max_output
        self.validator = ASTValidator()
    
    def validate(self, code: str) -> List[str]:
        """Validate code without executing."""
        return self.validator.validate(code)
    
    def execute(self, code: str, context: Dict[str, Any] = None) -> ExecutionResult:
        """Execute code in sandbox."""
        start_time = time.time()
        
        # Validate first
        violations = self.validate(code)
        if violations:
            return ExecutionResult(
                success=False,
                error=f"Security violations: {'; '.join(violations)}"
            )
        
        # Prepare safe globals
        safe_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "range": range,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "sorted": sorted,
                "reversed": reversed,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "any": any,
                "all": all,
                "isinstance": isinstance,
                "type": type,
                "True": True,
                "False": False,
                "None": None,
            }
        }
        
        if context:
            safe_globals.update(context)
        
        # Capture output
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        
        result = {"value": None, "error": None}
        
        def run():
            try:
                sys.stdout = stdout_capture
                exec(compile(code, "<sandbox>", "exec"), safe_globals)
                result["value"] = safe_globals.get("_result_")
            except Exception as e:
                result["error"] = str(e)
            finally:
                sys.stdout = old_stdout
        
        # Run with timeout
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(timeout=self.timeout)
        
        if thread.is_alive():
            return ExecutionResult(
                success=False,
                error=f"Timeout after {self.timeout}s",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        output = stdout_capture.getvalue()
        if len(output) > self.max_output:
            output = output[:self.max_output] + "\n... [truncated]"
        
        return ExecutionResult(
            success=result["error"] is None,
            output=output,
            error=result["error"],
            return_value=result["value"],
            execution_time_ms=(time.time() - start_time) * 1000
        )
    
    def execute_func(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a function safely, handling both sync and async.
        
        🔥 ASYNC FIX: Properly awaits coroutines instead of returning them.
        
        Args:
            func: Function to execute (can be sync or async)
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            ExecutionResult with the actual result (not a coroutine)
        """
        start_time = time.time()
        
        try:
            # 🔥 Case 1: Function is async (defined with async def)
            if inspect.iscoroutinefunction(func):
                # Get or create event loop
                try:
                    loop = asyncio.get_running_loop()
                    # Already in async context - schedule and run
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, func(*args, **kwargs))
                        result = future.result(timeout=self.timeout)
                except RuntimeError:
                    # No running loop - create one
                    result = asyncio.run(func(*args, **kwargs))
            else:
                # 🔥 Case 2: Regular sync function
                result = func(*args, **kwargs)
                
                # 🔥 Case 3: Sync function that returns a coroutine
                if inspect.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(asyncio.run, result)
                            result = future.result(timeout=self.timeout)
                    except RuntimeError:
                        result = asyncio.run(result)
            
            return ExecutionResult(
                success=True,
                return_value=result,
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                error=f"Async timeout after {self.timeout}s",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    async def execute_async(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute async function with proper await.
        
        Use this when you're already in an async context.
        """
        start_time = time.time()
        
        try:
            if inspect.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.timeout
                )
            else:
                result = func(*args, **kwargs)
                if inspect.iscoroutine(result):
                    result = await asyncio.wait_for(result, timeout=self.timeout)
            
            return ExecutionResult(
                success=True,
                return_value=result,
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                error=f"Async timeout after {self.timeout}s",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                execution_time_ms=(time.time() - start_time) * 1000
            )

# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE
# ═══════════════════════════════════════════════════════════════════════════

_executor: Optional[SecureExecutor] = None

def get_executor() -> SecureExecutor:
    global _executor
    if _executor is None:
        _executor = SecureExecutor()
    return _executor

def safe_exec(code: str, **kwargs) -> ExecutionResult:
    return get_executor().execute(code, **kwargs)

__all__ = ["SecureExecutor", "ExecutionResult", "ASTValidator", "get_executor", "safe_exec"]
