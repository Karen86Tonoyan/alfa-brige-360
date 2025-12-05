"""
ALFA_SEAT — Role Assignments
Maps roles to model IDs.
"""

from typing import Dict

# Default role assignments
# Can be modified at runtime via API
ROLES: Dict[str, str] = {
    "architect": "claude",      # System design, planning
    "integrator": "gpt",        # Code integration
    "coder": "gpt",             # Code generation
    "tester": "gemini",         # Testing, validation
    "analyst": "deepseek",      # Analysis, insights
}

# Role descriptions
ROLE_DESCRIPTIONS: Dict[str, str] = {
    "architect": "System design and planning. Creates high-level architecture.",
    "integrator": "Integrates components and manages dependencies.",
    "coder": "Writes and refactors code.",
    "tester": "Tests code and validates functionality.",
    "analyst": "Analyzes results and provides insights.",
}


def get_role(role: str) -> str:
    """Get model ID for role."""
    return ROLES.get(role, "gpt")


def set_role(role: str, model_id: str) -> None:
    """Set model ID for role."""
    ROLES[role] = model_id


def get_all_roles() -> Dict[str, dict]:
    """Get all roles with descriptions."""
    return {
        role: {
            "model_id": model_id,
            "description": ROLE_DESCRIPTIONS.get(role, "")
        }
        for role, model_id in ROLES.items()
    }
