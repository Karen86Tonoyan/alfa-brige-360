# ═══════════════════════════════════════════════════════════════════════════
# CERBER v7 - CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════
"""
Cerber v7 CLI Entry Point

Usage:
    python -m alfa_cloud.security.cerber_v7 status
    python -m alfa_cloud.security.cerber_v7 start
    python -m alfa_cloud.security.cerber_v7 scan
"""

from .cli import main

if __name__ == "__main__":
    main()
