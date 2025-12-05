"""
ALFA Delta Bridge Plugin v1.0
Komunikacja przez Delta Chat (IMAP/SMTP)
"""

from .delta_listener import DeltaListener
from .delta_sender import DeltaSender
from .delta_router import DeltaRouter

__version__ = "1.0.0"
__all__ = ["DeltaListener", "DeltaSender", "DeltaRouter"]
