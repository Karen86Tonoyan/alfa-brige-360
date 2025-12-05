#!/usr/bin/env python3
"""
ALFA Forensics Module

Moduł do odzyskiwania danych i analizy forensycznej:
- Integracja z RecoverPy (Linux block scanner)
- Skanowanie nadpisanych plików
- Odzyskiwanie seedów i kluczy
- Bezpieczne logowanie operacji

Author: ALFA System / Karen86Tonoyan
Version: 1.0.0
"""

from .forensics_engine import (
    ForensicsEngine,
    RecoverPyWrapper,
    ForensicsScanResult,
    BlockMatch,
)

from .disk_scanner import (
    DiskScanner,
    PartitionInfo,
    list_partitions,
)

__all__ = [
    "ForensicsEngine",
    "RecoverPyWrapper", 
    "ForensicsScanResult",
    "BlockMatch",
    "DiskScanner",
    "PartitionInfo",
    "list_partitions",
]
