"""
ALFA_SEAT v1.0 — Centrum Dowodzenia AI
======================================
Multi-model orchestration with role-based pipeline.

Components:
- registry: Model registry with adapters
- roles: Role assignments (architect, coder, tester, etc.)
- cerber: Security layer for validation
- executor: Pipeline engine
- logs: WebSocket LogBus
- router: FastAPI endpoints
"""

from .router import router as alfa_seat_router

__version__ = "1.0.0"
__all__ = ["alfa_seat_router"]
