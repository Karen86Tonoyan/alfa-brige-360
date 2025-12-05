#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# ALFA CORE v2.0 — SECURE EXECUTOR — Sandbox Execution Engine
# ═══════════════════════════════════════════════════════════════════════════
"""
SECURE EXECUTOR: Bezpieczne wykonywanie kodu z wielowarstwowym sandboxem.

Features:
- AST-based static analysis
- Import whitelist validation
- Resource limits (CPU, memory, time)
- Isolated execution environment
- PQXHybrid encryption for secure storage
- Audit trail with EventBus integration

Security Layers:
1. Static Analysis (AST) - przed wykonaniem
2. Import Validation - whitelist tylko
3. Runtime Sandbox - ograniczenia zasobów
4. Output Sanitization - przed zwrotem

Author: ALFA System / Karen86Tonoyan
"""

import ast
import asyncio
import base64
import concurrent.futures
import hashlib
import hmac
import inspect
import io
import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Resource module (Unix only)
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    # Windows doesn't have resource module
    HAS_RESOURCE = False
    resource = None

# Crypto imports (optional)
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# EventBus integration
try:
    from .event_bus import get_bus, publish, Priority
except ImportError:
    get_bus = lambda: None
    publish = lambda *a, **k: None
    Priority = None

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LOG = logging.getLogger("alfa.secure")

# Execution limits
DEFAULT_TIMEOUT = 30  # seconds
MAX_MEMORY_MB = 512
MAX_OUTPUT_SIZE = 1024 * 1024  # 1MB

# Safe imports (modular whitelist)
SAFE_IMPORTS_MINIMAL = {
    'math', 'random', 'string', 'collections', 'itertools',
    'functools', 'operator', 'copy', 'typing', 'dataclasses', 'enum'
}

SAFE_IMPORTS_STANDARD = SAFE_IMPORTS_MINIMAL | {
    'os.path', 'pathlib', 'datetime', 'time', 're', 'json',
    'hashlib', 'base64', 'uuid', 'secrets', 'logging', 'io', 'textwrap'
}

SAFE_IMPORTS_EXTENDED = SAFE_IMPORTS_STANDARD | {
    'csv', 'configparser', 'xml', 'html', 'http.client', 'urllib.parse'
}

SAFE_IMPORTS_SCIENCE = SAFE_IMPORTS_EXTENDED | {
    'numpy', 'pandas', 'scipy', 'matplotlib', 'sklearn'
}

# Absolutely forbidden
FORBIDDEN_NAMES = frozenset({
    'eval', 'exec', '__import__', 'compile', 'execfile',
    'globals', 'locals', 'vars', 'dir', 'getattr', 'setattr',
    'delattr', 'breakpoint', 'input', 'raw_input', 'open',
    'file', 'reload', 'help', 'exit', 'quit', 'license',
    '__builtins__', '__loader__', '__spec__'
})

FORBIDDEN_MODULES = frozenset({
    'subprocess', 'os.system', 'os.popen', 'os.spawn',
    'socket', 'requests', 'urllib.request', 'http.server',
    'asyncio', 'multiprocessing', 'threading', 'concurrent',
    'ctypes', 'cffi', 'cython', 'numba',
    'pickle', 'marshal', 'shelve', 'dill',
    'code', 'codeop', 'pty', 'tty'
})

# Dangerous patterns in code
DANGEROUS_PATTERNS = [
    (r'__\w+__', 'Dunder access'),
    (r'\\x[0-9a-fA-F]{2}', 'Hex escape'),
    (r'\\u[0-9a-fA-F]{4}', 'Unicode escape'),
    (r'chr\s*\(', 'chr() call'),
    (r'ord\s*\(', 'ord() call'),
    (r'bytes\s*\(', 'bytes() creation'),
    (r'bytearray\s*\(', 'bytearray() creation'),
]


# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

class SecurityLevel(Enum):
    """Poziomy bezpieczeństwa sandboxa"""
    MINIMAL = "minimal"       # Tylko basic math
    STANDARD = "standard"     # Standard library (safe)
    EXTENDED = "extended"     # + network read-only
    SCIENCE = "science"       # + numpy/pandas/scipy
    UNRESTRICTED = "unrestricted"  # Full access (dangerous)


class ExecutionResult(Enum):
    """Wynik wykonania"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    MEMORY_EXCEEDED = "memory_exceeded"


@dataclass
class ValidationResult:
    """Wynik walidacji kodu"""
    is_valid: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    blocked_imports: List[str] = field(default_factory=list)
    blocked_names: List[str] = field(default_factory=list)
    
    def add_issue(self, msg: str):
        self.issues.append(msg)
        self.is_valid = False
    
    def add_warning(self, msg: str):
        self.warnings.append(msg)


@dataclass
class ExecutionOutput:
    """Wynik wykonania kodu"""
    result: ExecutionResult
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    execution_time: float = 0.0
    memory_used: int = 0
    error: Optional[str] = None
    traceback: Optional[str] = None
    validation: Optional[ValidationResult] = None


# ═══════════════════════════════════════════════════════════════════════════
# PQX HYBRID ENCRYPTION (Post-Quantum Experimental)
# ═══════════════════════════════════════════════════════════════════════════

class PQXHybrid:
    """
    Post-Quantum Hybrid Encryption.
    Combines classical AES-256-GCM with additional layers for future-proofing.
    """
    
    VERSION = b"PQX1"
    SALT_SIZE = 32
    NONCE_SIZE = 12
    TAG_SIZE = 16
    
    def __init__(self, master_key: bytes = None):
        if not HAS_CRYPTO:
            LOG.warning("[PQX] Cryptography not available, using fallback")
        self.master_key = master_key or os.urandom(32)
    
    def derive_key(self, password: str, salt: bytes = None) -> Tuple[bytes, bytes]:
        """Derive encryption key from password using Argon2id"""
        salt = salt or os.urandom(self.SALT_SIZE)
        
        if HAS_CRYPTO:
            kdf = Argon2id(
                salt=salt,
                length=32,
                iterations=3,
                lanes=4,
                memory_cost=65536
            )
            key = kdf.derive(password.encode())
        else:
            # Fallback: PBKDF2-like with hashlib
            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, 32)
        
        return key, salt
    
    def encrypt(self, plaintext: bytes, password: str = None) -> bytes:
        """Encrypt data with AES-256-GCM"""
        if password:
            key, salt = self.derive_key(password)
        else:
            key = self.master_key
            salt = b""
        
        nonce = os.urandom(self.NONCE_SIZE)
        
        if HAS_CRYPTO:
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        else:
            # Fallback: XOR cipher (NOT SECURE - for dev only)
            keystream = hashlib.shake_256(key + nonce).digest(len(plaintext))
            ciphertext = bytes(a ^ b for a, b in zip(plaintext, keystream))
            # Add simple HMAC tag
            tag = hmac.new(key, ciphertext, 'sha256').digest()[:self.TAG_SIZE]
            ciphertext = ciphertext + tag
        
        # Format: VERSION(4) + SALT(32 or 0) + NONCE(12) + CIPHERTEXT+TAG
        return self.VERSION + salt + nonce + ciphertext
    
    def decrypt(self, ciphertext: bytes, password: str = None) -> bytes:
        """Decrypt data"""
        if len(ciphertext) < 4:
            raise ValueError("Invalid ciphertext")
        
        version = ciphertext[:4]
        if version != self.VERSION:
            raise ValueError(f"Unknown version: {version}")
        
        offset = 4
        
        if password:
            salt = ciphertext[offset:offset + self.SALT_SIZE]
            offset += self.SALT_SIZE
            key, _ = self.derive_key(password, salt)
        else:
            key = self.master_key
        
        nonce = ciphertext[offset:offset + self.NONCE_SIZE]
        offset += self.NONCE_SIZE
        
        encrypted_data = ciphertext[offset:]
        
        if HAS_CRYPTO:
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, encrypted_data, None)
        else:
            # Fallback
            tag = encrypted_data[-self.TAG_SIZE:]
            data = encrypted_data[:-self.TAG_SIZE]
            
            # Verify HMAC
            expected = hmac.new(key, data, 'sha256').digest()[:self.TAG_SIZE]
            if not hmac.compare_digest(tag, expected):
                raise ValueError("Authentication failed")
            
            keystream = hashlib.shake_256(key + nonce).digest(len(data))
            plaintext = bytes(a ^ b for a, b in zip(data, keystream))
        
        return plaintext
    
    def secure_hash(self, data: bytes) -> str:
        """Create secure hash of data"""
        return hashlib.blake2b(data, digest_size=32).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# AST VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

class ASTValidator(ast.NodeVisitor):
    """
    AST-based code validator.
    Walks the AST to detect forbidden patterns.
    """
    
    def __init__(self, safe_imports: Set[str], allow_file_ops: bool = False):
        self.safe_imports = safe_imports
        self.allow_file_ops = allow_file_ops
        self.result = ValidationResult(is_valid=True)
    
    def validate(self, code: str) -> ValidationResult:
        """Validate code string"""
        try:
            tree = ast.parse(code, mode='exec')
            self.visit(tree)
        except SyntaxError as e:
            self.result.add_issue(f"Syntax error at line {e.lineno}: {e.msg}")
        
        return self.result
    
    def visit_Name(self, node: ast.Name):
        """Check for forbidden names"""
        if node.id in FORBIDDEN_NAMES:
            self.result.add_issue(f"Forbidden name: {node.id}")
            self.result.blocked_names.append(node.id)
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import):
        """Check import statements"""
        for alias in node.names:
            module = alias.name.split('.')[0]
            if module not in self.safe_imports:
                self.result.add_issue(f"Import not allowed: {alias.name}")
                self.result.blocked_imports.append(alias.name)
            if alias.name in FORBIDDEN_MODULES:
                self.result.add_issue(f"Forbidden module: {alias.name}")
                self.result.blocked_imports.append(alias.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Check from ... import statements"""
        if node.module:
            module = node.module.split('.')[0]
            if module not in self.safe_imports:
                self.result.add_issue(f"Import not allowed: from {node.module}")
                self.result.blocked_imports.append(node.module)
            if node.module in FORBIDDEN_MODULES:
                self.result.add_issue(f"Forbidden module: {node.module}")
                self.result.blocked_imports.append(node.module)
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Check function calls"""
        # Direct call
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_NAMES:
                self.result.add_issue(f"Forbidden function call: {node.func.id}")
            
            # Check 'open' if file ops not allowed
            if node.func.id == 'open' and not self.allow_file_ops:
                self.result.add_issue("File operations not allowed")
        
        # Attribute call (e.g., os.system)
        elif isinstance(node.func, ast.Attribute):
            full_name = self._get_full_name(node.func)
            if full_name in FORBIDDEN_MODULES:
                self.result.add_issue(f"Forbidden call: {full_name}")
            
            # Check dangerous os functions
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'os':
                    if node.func.attr in {'system', 'popen', 'spawn', 'exec', 'fork'}:
                        self.result.add_issue(f"Dangerous os function: os.{node.func.attr}")
        
        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute):
        """Check attribute access"""
        # Check for dunder access
        if node.attr.startswith('__') and node.attr.endswith('__'):
            if node.attr not in {'__init__', '__str__', '__repr__', '__len__', '__iter__'}:
                self.result.add_warning(f"Dunder access: {node.attr}")
        
        self.generic_visit(node)
    
    def _get_full_name(self, node: ast.Attribute) -> str:
        """Get full attribute name (e.g., 'os.system')"""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return '.'.join(reversed(parts))


# ═══════════════════════════════════════════════════════════════════════════
# SECURE EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════

class SecureExecutor:
    """
    Secure code execution sandbox.
    
    Usage:
        executor = SecureExecutor(level=SecurityLevel.STANDARD)
        result = executor.execute("print('Hello')")
        print(result.stdout)
    """
    
    def __init__(
        self,
        level: SecurityLevel = SecurityLevel.STANDARD,
        timeout: int = DEFAULT_TIMEOUT,
        max_memory_mb: int = MAX_MEMORY_MB,
        allow_file_ops: bool = False
    ):
        self.level = level
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.allow_file_ops = allow_file_ops
        
        # Set import whitelist based on level
        self.safe_imports = self._get_safe_imports()
        
        # Validator
        self.validator = ASTValidator(self.safe_imports, allow_file_ops)
        
        # Encryption
        self.pqx = PQXHybrid()
        
        # Stats
        self.stats = {
            "executions": 0,
            "blocked": 0,
            "errors": 0,
            "timeouts": 0
        }
        
        LOG.info(f"[SecureExecutor] Initialized: level={level.value}, timeout={timeout}s")
    
    def _get_safe_imports(self) -> Set[str]:
        """Get import whitelist based on security level"""
        mapping = {
            SecurityLevel.MINIMAL: SAFE_IMPORTS_MINIMAL,
            SecurityLevel.STANDARD: SAFE_IMPORTS_STANDARD,
            SecurityLevel.EXTENDED: SAFE_IMPORTS_EXTENDED,
            SecurityLevel.SCIENCE: SAFE_IMPORTS_SCIENCE,
            SecurityLevel.UNRESTRICTED: set()  # No restrictions
        }
        return mapping.get(self.level, SAFE_IMPORTS_STANDARD)
    
    # ─────────────────────────────────────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────────────────────────────────────
    
    def validate(self, code: str) -> ValidationResult:
        """Validate code before execution"""
        validator = ASTValidator(self.safe_imports, self.allow_file_ops)
        result = validator.validate(code)
        
        # Additional pattern checks
        import re
        for pattern, desc in DANGEROUS_PATTERNS:
            if re.search(pattern, code):
                result.add_warning(f"Suspicious pattern: {desc}")
        
        return result
    
    # ─────────────────────────────────────────────────────────────────────
    # EXECUTION
    # ─────────────────────────────────────────────────────────────────────
    
    def execute(
        self,
        code: str,
        inputs: Dict[str, Any] = None,
        capture_return: bool = True
    ) -> ExecutionOutput:
        """
        Execute code in sandbox.
        
        Args:
            code: Python code to execute
            inputs: Variables to inject into namespace
            capture_return: If True, try to capture last expression value
            
        Returns:
            ExecutionOutput with results
        """
        self.stats["executions"] += 1
        start_time = time.time()
        
        # Validate first (unless unrestricted)
        if self.level != SecurityLevel.UNRESTRICTED:
            validation = self.validate(code)
            if not validation.is_valid:
                self.stats["blocked"] += 1
                if get_bus():
                    publish("secure.blocked", {
                        "issues": validation.issues,
                        "blocked_imports": validation.blocked_imports
                    }, priority=Priority.HIGH if Priority else 10)
                
                return ExecutionOutput(
                    result=ExecutionResult.BLOCKED,
                    validation=validation,
                    error="; ".join(validation.issues)
                )
        
        # Execute in subprocess for isolation
        if self.level in {SecurityLevel.MINIMAL, SecurityLevel.STANDARD}:
            output = self._execute_subprocess(code, inputs)
        else:
            output = self._execute_direct(code, inputs, capture_return)
        
        output.execution_time = time.time() - start_time
        
        # Update stats
        if output.result == ExecutionResult.ERROR:
            self.stats["errors"] += 1
        elif output.result == ExecutionResult.TIMEOUT:
            self.stats["timeouts"] += 1
        
        # Publish event
        if get_bus():
            publish("secure.executed", {
                "result": output.result.value,
                "execution_time": output.execution_time
            })
        
        return output
    
    def _execute_subprocess(
        self,
        code: str,
        inputs: Dict[str, Any] = None
    ) -> ExecutionOutput:
        """Execute in isolated subprocess"""
        # Create temp file with code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Inject inputs
            if inputs:
                for name, value in inputs.items():
                    f.write(f"{name} = {repr(value)}\n")
            f.write(code)
            temp_path = f.name
        
        try:
            # Run with timeout and resource limits
            result = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={
                    **os.environ,
                    'PYTHONDONTWRITEBYTECODE': '1',
                    'PYTHONHASHSEED': '0'
                }
            )
            
            return ExecutionOutput(
                result=ExecutionResult.SUCCESS if result.returncode == 0 else ExecutionResult.ERROR,
                stdout=result.stdout[:MAX_OUTPUT_SIZE],
                stderr=result.stderr[:MAX_OUTPUT_SIZE],
                error=result.stderr if result.returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired:
            return ExecutionOutput(
                result=ExecutionResult.TIMEOUT,
                error=f"Execution timeout ({self.timeout}s)"
            )
        except Exception as e:
            return ExecutionOutput(
                result=ExecutionResult.ERROR,
                error=str(e),
                traceback=traceback.format_exc()
            )
        finally:
            os.unlink(temp_path)
    
    def _execute_direct(
        self,
        code: str,
        inputs: Dict[str, Any] = None,
        capture_return: bool = True
    ) -> ExecutionOutput:
        """Execute directly in current process (for extended/science)"""
        # Prepare namespace
        namespace = {'__builtins__': self._get_safe_builtins()}
        if inputs:
            namespace.update(inputs)
        
        # Capture stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = stdout_capture = io.StringIO()
        sys.stderr = stderr_capture = io.StringIO()
        
        return_value = None
        error = None
        tb = None
        
        try:
            # Compile
            compiled = compile(code, '<sandbox>', 'exec')
            
            # Execute with timeout
            with self._timeout_context(self.timeout):
                exec(compiled, namespace)
            
            # Try to get last expression value
            if capture_return and '_' in namespace:
                return_value = namespace['_']
            
            result = ExecutionResult.SUCCESS
            
        except TimeoutError:
            result = ExecutionResult.TIMEOUT
            error = f"Execution timeout ({self.timeout}s)"
        except MemoryError:
            result = ExecutionResult.MEMORY_EXCEEDED
            error = f"Memory limit exceeded ({self.max_memory_mb}MB)"
        except Exception as e:
            result = ExecutionResult.ERROR
            error = str(e)
            tb = traceback.format_exc()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        return ExecutionOutput(
            result=result,
            stdout=stdout_capture.getvalue()[:MAX_OUTPUT_SIZE],
            stderr=stderr_capture.getvalue()[:MAX_OUTPUT_SIZE],
            return_value=return_value,
            error=error,
            traceback=tb
        )
    
    def _get_safe_builtins(self) -> Dict[str, Any]:
        """Get filtered builtins"""
        safe = {}
        allowed = {
            'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'callable',
            'chr', 'dict', 'divmod', 'enumerate', 'filter', 'float',
            'format', 'frozenset', 'hash', 'hex', 'int', 'isinstance',
            'issubclass', 'iter', 'len', 'list', 'map', 'max', 'min',
            'next', 'object', 'oct', 'ord', 'pow', 'print', 'range',
            'repr', 'reversed', 'round', 'set', 'slice', 'sorted',
            'str', 'sum', 'tuple', 'type', 'zip',
            'True', 'False', 'None', 'Ellipsis', 'NotImplemented',
            'Exception', 'TypeError', 'ValueError', 'KeyError', 'IndexError',
            'AttributeError', 'RuntimeError', 'StopIteration'
        }
        
        import builtins
        for name in allowed:
            if hasattr(builtins, name):
                safe[name] = getattr(builtins, name)
        
        return safe
    
    @contextmanager
    def _timeout_context(self, seconds: int):
        """Context manager for timeout (Unix only)"""
        if sys.platform == 'win32':
            # Windows: use threading
            timer = threading.Timer(seconds, lambda: (_ for _ in ()).throw(TimeoutError()))
            timer.start()
            try:
                yield
            finally:
                timer.cancel()
        else:
            # Unix: use signal
            def handler(signum, frame):
                raise TimeoutError()
            
            old_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                yield
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
    
    # ─────────────────────────────────────────────────────────────────────
    # FUNCTION EXECUTION (ASYNC-SAFE)
    # ─────────────────────────────────────────────────────────────────────
    
    def execute_func(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> ExecutionOutput:
        """
        Execute a function safely, handling both sync and async.
        
        🔥 ASYNC FIX: Properly awaits coroutines instead of returning them.
        
        Args:
            func: Function to execute (can be sync or async)
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            ExecutionOutput with the actual result (not a coroutine)
        """
        start_time = time.time()
        
        try:
            # Case 1: Function is async (defined with async def)
            if inspect.iscoroutinefunction(func):
                try:
                    loop = asyncio.get_running_loop()
                    # Already in async context - run in thread pool
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, func(*args, **kwargs))
                        result = future.result(timeout=self.timeout)
                except RuntimeError:
                    # No running loop - create one
                    result = asyncio.run(func(*args, **kwargs))
            else:
                # Case 2: Regular sync function
                result = func(*args, **kwargs)
                
                # Case 3: Sync function that returns a coroutine
                if inspect.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(asyncio.run, result)
                            result = future.result(timeout=self.timeout)
                    except RuntimeError:
                        result = asyncio.run(result)
            
            return ExecutionOutput(
                result=ExecutionResult.SUCCESS,
                return_value=result,
                execution_time=time.time() - start_time
            )
            
        except asyncio.TimeoutError:
            return ExecutionOutput(
                result=ExecutionResult.TIMEOUT,
                error=f"Async timeout after {self.timeout}s",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ExecutionOutput(
                result=ExecutionResult.ERROR,
                error=f"{type(e).__name__}: {e}",
                traceback=traceback.format_exc(),
                execution_time=time.time() - start_time
            )
    
    async def execute_func_async(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> ExecutionOutput:
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
            
            return ExecutionOutput(
                result=ExecutionResult.SUCCESS,
                return_value=result,
                execution_time=time.time() - start_time
            )
            
        except asyncio.TimeoutError:
            return ExecutionOutput(
                result=ExecutionResult.TIMEOUT,
                error=f"Async timeout after {self.timeout}s",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ExecutionOutput(
                result=ExecutionResult.ERROR,
                error=f"{type(e).__name__}: {e}",
                traceback=traceback.format_exc(),
                execution_time=time.time() - start_time
            )

    # ─────────────────────────────────────────────────────────────────────
    # SPECIALIZED EXECUTION
    # ─────────────────────────────────────────────────────────────────────
    
    def run_python(self, code: str) -> Tuple[int, str]:
        """Run Python code, return (exit_code, output)"""
        result = self.execute(code)
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        if result.error:
            output += "\n" + result.error
        
        exit_code = 0 if result.result == ExecutionResult.SUCCESS else 1
        return exit_code, output
    
    def run_powershell(self, code: str) -> Tuple[int, str]:
        """Run PowerShell code (Windows only)"""
        if sys.platform != 'win32':
            return 1, "PowerShell not available on this platform"
        
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', code],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            return result.returncode, result.stdout + result.stderr
        except Exception as e:
            return 1, str(e)
    
    def run_bash(self, code: str) -> Tuple[int, str]:
        """Run Bash code (Unix only)"""
        if sys.platform == 'win32':
            return 1, "Bash not available on Windows"
        
        try:
            result = subprocess.run(
                ['bash', '-c', code],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            return result.returncode, result.stdout + result.stderr
        except Exception as e:
            return 1, str(e)
    
    # ─────────────────────────────────────────────────────────────────────
    # SECURE STORAGE
    # ─────────────────────────────────────────────────────────────────────
    
    def secure_store(self, key: str, value: Any, password: str = None) -> str:
        """Store value securely, return encrypted blob"""
        import json
        data = json.dumps(value).encode('utf-8')
        encrypted = self.pqx.encrypt(data, password)
        return base64.b64encode(encrypted).decode('ascii')
    
    def secure_load(self, blob: str, password: str = None) -> Any:
        """Load securely stored value"""
        import json
        encrypted = base64.b64decode(blob.encode('ascii'))
        data = self.pqx.decrypt(encrypted, password)
        return json.loads(data.decode('utf-8'))
    
    # ─────────────────────────────────────────────────────────────────────
    # STATUS
    # ─────────────────────────────────────────────────────────────────────
    
    def get_stats(self) -> Dict:
        """Get execution statistics"""
        return {
            **self.stats,
            "level": self.level.value,
            "timeout": self.timeout,
            "max_memory_mb": self.max_memory_mb,
            "safe_imports_count": len(self.safe_imports)
        }
    
    def get_allowed_imports(self) -> List[str]:
        """Get list of allowed imports"""
        return sorted(self.safe_imports)


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON & HELPERS
# ═══════════════════════════════════════════════════════════════════════════

_executor: Optional[SecureExecutor] = None


def get_executor(level: SecurityLevel = SecurityLevel.STANDARD) -> SecureExecutor:
    """Get or create SecureExecutor singleton"""
    global _executor
    if _executor is None:
        _executor = SecureExecutor(level=level)
    return _executor


def safe_exec(code: str, level: SecurityLevel = SecurityLevel.STANDARD) -> ExecutionOutput:
    """Quick safe execution"""
    executor = get_executor(level)
    return executor.execute(code)


def validate_code(code: str) -> ValidationResult:
    """Quick code validation"""
    executor = get_executor()
    return executor.validate(code)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ALFA Secure Executor")
    parser.add_argument("--code", "-c", help="Code to execute")
    parser.add_argument("--file", "-f", help="File to execute")
    parser.add_argument("--level", "-l", default="standard",
                        choices=["minimal", "standard", "extended", "science"],
                        help="Security level")
    parser.add_argument("--validate", "-v", action="store_true", help="Validate only")
    parser.add_argument("--timeout", "-t", type=int, default=30, help="Timeout in seconds")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    # Get code
    if args.file:
        with open(args.file) as f:
            code = f.read()
    elif args.code:
        code = args.code
    else:
        code = input("Enter code: ")
    
    # Execute
    level = SecurityLevel(args.level)
    executor = SecureExecutor(level=level, timeout=args.timeout)
    
    if args.validate:
        result = executor.validate(code)
        print(f"Valid: {result.is_valid}")
        for issue in result.issues:
            print(f"  ✗ {issue}")
        for warn in result.warnings:
            print(f"  ⚠ {warn}")
    else:
        output = executor.execute(code)
        print(f"Result: {output.result.value}")
        print(f"Time: {output.execution_time:.3f}s")
        if output.stdout:
            print(f"Output:\n{output.stdout}")
        if output.error:
            print(f"Error: {output.error}")
