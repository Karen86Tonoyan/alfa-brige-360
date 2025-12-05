"""
ALFA_CORE / EXTENSIONS / CODING / CODE EXECUTOR
================================================
Secure sandbox for executing code with validation.

Features:
- AST-based Python validation
- Sandboxed imports (whitelist)
- Timeout protection
- Multi-language support (Python, PowerShell, Bash)

Author: ALFA System / Karen86Tonoyan
"""

import argparse
import subprocess
import sys
import tempfile
import textwrap
import ast
import logging
from typing import Tuple, Set, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [EXECUTOR] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Safe imports whitelist (expandable)
SAFE_IMPORTS: Set[str] = {
    # Standard library - safe
    'os', 'sys', 'json', 'math', 'datetime', 'time', 'random', 'collections',
    're', 'string', 'itertools', 'functools', 'operator', 'copy',
    'pathlib', 'typing', 'dataclasses', 'enum', 'abc',
    'hashlib', 'base64', 'uuid', 'secrets',
    'logging', 'warnings', 'traceback',
    'io', 'contextlib', 'textwrap',
    
    # Data processing
    'csv', 'configparser', 'xml', 'html',
    
    # Math/Science (if installed)
    'numpy', 'pandas', 'scipy', 'matplotlib',
    
    # HTTP (read-only operations)
    'urllib', 'http',
}

# Forbidden names (always blocked)
FORBIDDEN_NAMES: Set[str] = {
    'eval', 'exec', '__import__', 'compile',
    'globals', 'locals', 'vars', 'dir',
    'getattr', 'setattr', 'delattr',
    'breakpoint', 'input',
}

# Restricted names (blocked in sandbox mode only)
RESTRICTED_NAMES: Set[str] = {
    'open', 'file',
    'subprocess', 'os.system', 'os.popen',
    'socket', 'requests', 'urllib.request',
}


# =============================================================================
# CODE EXECUTOR
# =============================================================================

class CodeExecutor:
    """
    Secure code execution sandbox.
    Validates and runs code with safety checks.
    """
    
    def __init__(
        self,
        sandbox: bool = True,
        timeout: int = 30,
        safe_imports: Optional[Set[str]] = None,
        allow_file_ops: bool = False
    ):
        """
        Initialize CodeExecutor.
        
        Args:
            sandbox: Enable security validation
            timeout: Execution timeout in seconds
            safe_imports: Custom whitelist of allowed imports
            allow_file_ops: Allow file operations (open, read, write)
        """
        self.sandbox = sandbox
        self.timeout = timeout
        self.safe_imports = safe_imports or SAFE_IMPORTS
        self.allow_file_ops = allow_file_ops
        
        # Build forbidden set based on settings
        self.forbidden = FORBIDDEN_NAMES.copy()
        if not allow_file_ops:
            self.forbidden.update(RESTRICTED_NAMES)
    
    # -------------------------------------------------------------------------
    # VALIDATION
    # -------------------------------------------------------------------------
    
    def _validate_python(self, code: str) -> Tuple[bool, str]:
        """
        Validate Python code for safety.
        
        Returns:
            Tuple of (is_valid, message)
        """
        # Parse AST
        try:
            tree = ast.parse(code, mode='exec')
        except SyntaxError as e:
            return False, f'SyntaxError at line {e.lineno}: {e.msg}'
        
        # Walk AST and check for forbidden patterns
        for node in ast.walk(tree):
            # Check forbidden names
            if isinstance(node, ast.Name) and node.id in self.forbidden:
                return False, f'Forbidden name: {node.id}'
            
            # Check function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.forbidden:
                        return False, f'Forbidden function: {node.func.id}'
                elif isinstance(node.func, ast.Attribute):
                    full_name = self._get_attribute_name(node.func)
                    if full_name in self.forbidden:
                        return False, f'Forbidden call: {full_name}'
            
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if module not in self.safe_imports:
                        return False, f'Import not allowed: {alias.name}'
            
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split('.')[0]
                    if module not in self.safe_imports:
                        return False, f'Import not allowed: {node.module}'
            
            # Check attribute access on dangerous modules
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    if node.value.id == 'os' and node.attr in ['system', 'popen', 'spawn']:
                        return False, f'Dangerous os function: os.{node.attr}'
                    if node.value.id == 'subprocess':
                        return False, 'subprocess module not allowed in sandbox'
        
        return True, 'OK'
    
    def _get_attribute_name(self, node: ast.Attribute) -> str:
        """Get full attribute name (e.g., 'os.system')."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return '.'.join(reversed(parts))
    
    def validate(self, code: str, language: str = 'python') -> Tuple[bool, str]:
        """
        Validate code for the specified language.
        
        Args:
            code: Source code to validate
            language: Programming language
            
        Returns:
            Tuple of (is_valid, message)
        """
        if language == 'python':
            return self._validate_python(code)
        
        # For other languages, basic checks only
        dangerous_patterns = [
            'rm -rf', 'del /f', 'format c:',
            'shutdown', 'reboot',
            '> /dev/', 'dd if=',
        ]
        
        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern in code_lower:
                return False, f'Dangerous pattern detected: {pattern}'
        
        return True, 'OK'
    
    # -------------------------------------------------------------------------
    # EXECUTION
    # -------------------------------------------------------------------------
    
    def run_python(self, code: str) -> Tuple[int, str]:
        """
        Execute Python code.
        
        Args:
            code: Python code to execute
            
        Returns:
            Tuple of (return_code, output)
        """
        # Validate in sandbox mode
        if self.sandbox:
            ok, msg = self._validate_python(code)
            if not ok:
                logger.warning(f"Validation failed: {msg}")
                return 1, f"VALIDATION ERROR: {msg}"
        
        # Write to temp file
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            path = f.name
        
        try:
            # Execute with timeout
            proc = subprocess.run(
                [sys.executable, path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=tempfile.gettempdir()
            )
            
            output = proc.stdout
            if proc.stderr:
                output += f"\n[STDERR]\n{proc.stderr}"
            
            logger.info(f"Python execution completed: rc={proc.returncode}")
            return proc.returncode, output.strip()
            
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout exceeded ({self.timeout}s)")
            return 1, f'TIMEOUT: Execution exceeded {self.timeout} seconds'
        except Exception as e:
            logger.error(f"Execution error: {e}")
            return 1, f'EXECUTION ERROR: {str(e)}'
        finally:
            # Clean up temp file
            try:
                Path(path).unlink()
            except Exception:
                pass
    
    def run_powershell(self, script: str) -> Tuple[int, str]:
        """
        Execute PowerShell script.
        
        Args:
            script: PowerShell script to execute
            
        Returns:
            Tuple of (return_code, output)
        """
        # Validate in sandbox mode
        if self.sandbox:
            ok, msg = self.validate(script, 'powershell')
            if not ok:
                return 1, f"VALIDATION ERROR: {msg}"
        
        try:
            proc = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            output = proc.stdout
            if proc.stderr:
                output += f"\n[STDERR]\n{proc.stderr}"
            
            logger.info(f"PowerShell execution completed: rc={proc.returncode}")
            return proc.returncode, output.strip()
            
        except subprocess.TimeoutExpired:
            return 1, f'TIMEOUT: Execution exceeded {self.timeout} seconds'
        except FileNotFoundError:
            return 1, 'PowerShell not available on this system'
        except Exception as e:
            return 1, f'EXECUTION ERROR: {str(e)}'
    
    def run_bash(self, script: str) -> Tuple[int, str]:
        """
        Execute Bash script.
        
        Args:
            script: Bash script to execute
            
        Returns:
            Tuple of (return_code, output)
        """
        # Validate in sandbox mode
        if self.sandbox:
            ok, msg = self.validate(script, 'bash')
            if not ok:
                return 1, f"VALIDATION ERROR: {msg}"
        
        try:
            proc = subprocess.run(
                ['bash', '-c', script],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            output = proc.stdout
            if proc.stderr:
                output += f"\n[STDERR]\n{proc.stderr}"
            
            logger.info(f"Bash execution completed: rc={proc.returncode}")
            return proc.returncode, output.strip()
            
        except subprocess.TimeoutExpired:
            return 1, f'TIMEOUT: Execution exceeded {self.timeout} seconds'
        except FileNotFoundError:
            return 1, 'Bash not available on this system'
        except Exception as e:
            return 1, f'EXECUTION ERROR: {str(e)}'
    
    def run(self, code: str, language: str = 'python') -> Tuple[int, str]:
        """
        Execute code in the specified language.
        
        Args:
            code: Source code to execute
            language: Programming language
            
        Returns:
            Tuple of (return_code, output)
        """
        language = language.lower()
        
        if language == 'python':
            return self.run_python(code)
        elif language == 'powershell':
            return self.run_powershell(code)
        elif language in ('bash', 'sh', 'shell'):
            return self.run_bash(code)
        else:
            return 1, f'Unsupported language: {language}'


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def detect_language(block: str) -> str:
    """
    Detect programming language from code block.
    
    Args:
        block: Code block (possibly with markdown fences)
        
    Returns:
        Detected language ('python', 'powershell', 'bash', or 'text')
    """
    first_line = block.strip().split('\n', 1)[0].lower()
    
    if first_line.startswith('```python'):
        return 'python'
    if first_line.startswith('```powershell') or first_line.startswith('```ps1'):
        return 'powershell'
    if first_line.startswith('```bash') or first_line.startswith('```sh'):
        return 'bash'
    if first_line.startswith('```javascript') or first_line.startswith('```js'):
        return 'javascript'
    if first_line.startswith('```'):
        # Generic code block
        return 'text'
    
    # Try to detect from content
    if 'import ' in block or 'def ' in block or 'class ' in block:
        return 'python'
    if '$' in block and ('Get-' in block or 'Set-' in block):
        return 'powershell'
    if block.strip().startswith('#!') or 'echo ' in block:
        return 'bash'
    
    return 'text'


def strip_fences(block: str) -> str:
    """
    Remove markdown code fences from a code block.
    
    Args:
        block: Code block with possible fences
        
    Returns:
        Code without fences
    """
    lines = block.strip().splitlines()
    
    # Remove opening fence
    if lines and lines[0].startswith('```'):
        lines = lines[1:]
    
    # Remove closing fence
    if lines and lines[-1].strip() == '```':
        lines = lines[:-1]
    
    return '\n'.join(lines)


# =============================================================================
# CLI
# =============================================================================

def cli_test():
    """Run CLI tests."""
    print("=" * 50)
    print("ALFA_CORE CodeExecutor Test Suite")
    print("=" * 50)
    
    executor = CodeExecutor(sandbox=True, timeout=5)
    
    # Test 1: Valid Python
    print("\n[TEST 1] Valid Python code:")
    code = textwrap.dedent('''
    import math
    for i in range(3):
        print(f"{i}: sqrt = {math.sqrt(i):.2f}")
    ''')
    rc, out = executor.run_python(code)
    print(f"  Return code: {rc}")
    print(f"  Output:\n{textwrap.indent(out, '    ')}")
    
    # Test 2: Forbidden import
    print("\n[TEST 2] Forbidden import (should fail):")
    code = "import socket\nprint('hello')"
    rc, out = executor.run_python(code)
    print(f"  Return code: {rc}")
    print(f"  Output: {out}")
    
    # Test 3: Forbidden function
    print("\n[TEST 3] Forbidden function (should fail):")
    code = "exec('print(1)')"
    rc, out = executor.run_python(code)
    print(f"  Return code: {rc}")
    print(f"  Output: {out}")
    
    # Test 4: Language detection
    print("\n[TEST 4] Language detection:")
    samples = [
        "```python\nimport os\n```",
        "```powershell\nGet-Process\n```",
        "```bash\necho hello\n```",
        "def foo(): pass",
    ]
    for sample in samples:
        lang = detect_language(sample)
        print(f"  '{sample[:30]}...' -> {lang}")
    
    print("\n" + "=" * 50)
    print("Tests completed!")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ALFA_CORE Code Executor - Secure sandbox for code execution"
    )
    parser.add_argument('--test', action='store_true', help='Run tests')
    parser.add_argument('--file', '-f', help='Execute code from file')
    parser.add_argument('--lang', '-l', default='python', help='Language (python/powershell/bash)')
    parser.add_argument('--no-sandbox', action='store_true', help='Disable sandbox')
    parser.add_argument('--timeout', '-t', type=int, default=30, help='Timeout in seconds')
    
    args = parser.parse_args()
    
    if args.test:
        cli_test()
    elif args.file:
        code = Path(args.file).read_text(encoding='utf-8')
        executor = CodeExecutor(sandbox=not args.no_sandbox, timeout=args.timeout)
        rc, out = executor.run(code, args.lang)
        print(out)
        sys.exit(rc)
    else:
        print("Use --test to run tests or --file to execute code.")
        print("Example: python code_executor.py --test")


if __name__ == '__main__':
    main()
