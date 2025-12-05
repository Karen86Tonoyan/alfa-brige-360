"""
ALFA_SEAT — Pydantic Models
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class TaskMode(str, Enum):
    """Pipeline execution modes."""
    PLAN = "PLAN"
    BUILD = "BUILD"
    TEST = "TEST"


class TaskRequest(BaseModel):
    """Request for pipeline execution."""
    instruction: str = Field(..., description="Task instruction")
    mode: TaskMode = Field(default=TaskMode.BUILD, description="Execution mode")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class RoleUpdate(BaseModel):
    """Request to update role assignment."""
    model_id: str = Field(..., description="Model ID to assign")


class PipelineResult(BaseModel):
    """Result from pipeline execution."""
    status: str
    plan: Optional[str] = None
    code: Optional[str] = None
    final_code: Optional[str] = None
    test: Optional[str] = None
    insight: Optional[str] = None
    error: Optional[str] = None


class ModelInfo(BaseModel):
    """Information about a registered model."""
    id: str
    name: str
    type: str  # cloud / local
    status: str = "ready"


class CerberDecisionModel(BaseModel):
    """Cerber security decision."""
    allowed: bool
    reason: str = ""
