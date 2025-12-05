"""
ALFA Watchdog Module - FREE Secure SMS Remote Control

8-Layer Security:
1. Whitelist enforcement
2. Rate limiting
3. Token authentication
4. Replay attack prevention
5. Command sanitization
6. Command whitelist
7. Secure execution (NO shell!)
8. Audit logging
"""

from .processor import WatchdogProcessor
from .security import WatchdogSecurity
from .commands import WatchdogCommands

__all__ = ["WatchdogProcessor", "WatchdogSecurity", "WatchdogCommands"]
__version__ = "1.0.0"
