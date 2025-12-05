"""
ALFA_SEAT — Cerber Security Layer
Validates role assignments and task requests.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Dict, Set, Optional

logger = logging.getLogger("ALFA.Seat.Cerber")


@dataclass
class CerberDecision:
    """Security decision result."""
    allowed: bool
    reason: str = ""
    
    def __bool__(self) -> bool:
        return self.allowed


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# Which models can perform which roles
ALLOWED_ROLE_MODELS: Dict[str, Set[str]] = {
    "architect": {"claude", "gpt", "gemini"},
    "integrator": {"gpt", "gemini", "deepseek"},
    "tester": {"gemini", "deepseek", "gpt"},
    "coder": {"gpt", "claude", "deepseek", "ollama_mistral", "ollama_codellama"},
    "analyst": {"deepseek", "gemini", "gpt", "claude"},
}

# Maximum task instruction length
MAX_TASK_LENGTH = 8000

# Valid execution modes
VALID_MODES = {"PLAN", "BUILD", "TEST"}

# Forbidden patterns in instructions
FORBIDDEN_PATTERNS = [
    "delete system",
    "rm -rf /",
    "format c:",
    "drop database",
    "shutdown",
]

# Enable/disable Cerber
CERBER_SEAT_ENABLED = os.getenv("CERBER_SEAT_ENABLED", "1") == "1"


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

async def cerber_check_roles(
    roles: Dict[str, str],
    model_registry: Dict[str, dict]
) -> CerberDecision:
    """
    Validate role assignments.
    
    Args:
        roles: Mapping of role -> model_id
        model_registry: Available models
        
    Returns:
        CerberDecision with allowed status and reason
    """
    if not CERBER_SEAT_ENABLED:
        return CerberDecision(True, "Cerber disabled")
    
    for role, model_id in roles.items():
        # Check if model exists
        if model_id not in model_registry:
            logger.warning(f"Cerber: Model '{model_id}' not registered")
            return CerberDecision(
                False, 
                f"Model '{model_id}' nie jest zarejestrowany"
            )
        
        # Check if model can perform role
        allowed_models = ALLOWED_ROLE_MODELS.get(role, set())
        if model_id not in allowed_models:
            logger.warning(f"Cerber: Model '{model_id}' cannot perform role '{role}'")
            return CerberDecision(
                False,
                f"Model '{model_id}' nie może pełnić roli '{role}'. "
                f"Dozwolone: {', '.join(allowed_models)}"
            )
    
    return CerberDecision(True, "OK")


async def cerber_check_task(
    instruction: str,
    mode: str
) -> CerberDecision:
    """
    Validate task request.
    
    Args:
        instruction: Task instruction
        mode: Execution mode (PLAN/BUILD/TEST)
        
    Returns:
        CerberDecision with allowed status and reason
    """
    if not CERBER_SEAT_ENABLED:
        return CerberDecision(True, "Cerber disabled")
    
    # Check instruction length
    if len(instruction) > MAX_TASK_LENGTH:
        return CerberDecision(
            False,
            f"Instrukcja zbyt długa ({len(instruction)} > {MAX_TASK_LENGTH})"
        )
    
    # Check mode
    if mode not in VALID_MODES:
        return CerberDecision(
            False,
            f"Nieznany tryb '{mode}'. Dozwolone: {', '.join(VALID_MODES)}"
        )
    
    # Check forbidden patterns
    instruction_lower = instruction.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in instruction_lower:
            logger.warning(f"Cerber: Forbidden pattern detected: {pattern}")
            return CerberDecision(
                False,
                f"Wykryto zabroniony wzorzec w instrukcji"
            )
    
    return CerberDecision(True, "OK")


async def cerber_check_model_switch(
    role: str,
    new_model_id: str,
    model_registry: Dict[str, dict]
) -> CerberDecision:
    """
    Validate single model switch for a role.
    """
    if not CERBER_SEAT_ENABLED:
        return CerberDecision(True, "Cerber disabled")
    
    # Check if model exists
    if new_model_id not in model_registry:
        return CerberDecision(
            False,
            f"Model '{new_model_id}' nie jest zarejestrowany"
        )
    
    # Check if model can perform role
    allowed_models = ALLOWED_ROLE_MODELS.get(role, set())
    if new_model_id not in allowed_models:
        return CerberDecision(
            False,
            f"Model '{new_model_id}' nie może pełnić roli '{role}'"
        )
    
    return CerberDecision(True, "OK")
