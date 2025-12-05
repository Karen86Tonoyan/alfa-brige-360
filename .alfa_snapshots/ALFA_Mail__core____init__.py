"""
ALFA Mail - Core Module
=======================
Core components for ALFA Mail system.

Modules:
- database: SQLCipher encrypted storage
- imap_engine: IMAP sync with retry logic
- cerber: Background service for Android

Author: ALFA System / Karen86Tonoyan
"""

from .database import MagestikDatabase, MailRecord
from .imap_engine import IMAPEngine, IMAPConfig
from .cerber import CerberService, CerberConfig

__all__ = [
    # Database
    "MagestikDatabase",
    "MailRecord",
    # IMAP
    "IMAPEngine", 
    "IMAPConfig",
    # Cerber
    "CerberService",
    "CerberConfig",
]
