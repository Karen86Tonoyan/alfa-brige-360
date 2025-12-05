"""
ALFA_CORE / EXTENSIONS / CODING
================================
Code execution sandbox with security validation.
"""

from .code_executor import CodeExecutor, detect_language, strip_fences

DESCRIPTION = "Secure code execution sandbox for Python, PowerShell, and Bash"
COMMANDS = ["run", "validate", "execute"]

__all__ = ["CodeExecutor", "detect_language", "strip_fences"]
