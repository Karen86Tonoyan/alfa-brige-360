"""
ALFA_SEAT — FastAPI Router
All endpoints for the command center.
"""

import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from .models import TaskRequest, RoleUpdate, TaskMode
from .registry import MODEL_REGISTRY, list_models, check_model_health
from .roles import ROLES, get_all_roles, set_role
from .executor import run_pipeline
from .cerber import cerber_check_roles, cerber_check_task, cerber_check_model_switch
from .logs import LOG_BUS

logger = logging.getLogger("ALFA.Seat.Router")

router = APIRouter(prefix="/alfa-seat", tags=["ALFA_SEAT"])


# ═══════════════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/status")
async def seat_status():
    """Get ALFA_SEAT status."""
    return {
        "status": "alive",
        "version": "1.0.0",
        "roles": ROLES,
        "models": list(MODEL_REGISTRY.keys()),
        "log_connections": len(LOG_BUS.connections)
    }


@router.get("/health")
async def seat_health():
    """Health check with model status."""
    model_status = {}
    for model_id in MODEL_REGISTRY:
        model_status[model_id] = await check_model_health(model_id)
    
    all_healthy = all(model_status.values())
    
    return {
        "healthy": all_healthy,
        "models": model_status
    }


# ═══════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/models")
async def get_models():
    """List all registered models."""
    return list_models()


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """Get model details."""
    if model_id not in MODEL_REGISTRY:
        raise HTTPException(404, f"Model not found: {model_id}")
    
    model = MODEL_REGISTRY[model_id]
    return {
        "id": model_id,
        "name": model["name"],
        "type": model["type"],
        "provider": model["provider"],
        "healthy": await check_model_health(model_id)
    }


# ═══════════════════════════════════════════════════════════════════════════
# ROLES
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/roles")
async def get_roles():
    """Get all role assignments."""
    return get_all_roles()


@router.post("/roles/{role}")
async def update_role(role: str, data: RoleUpdate):
    """Update role assignment."""
    if role not in ROLES:
        raise HTTPException(404, f"Role not found: {role}")
    
    # Cerber validation
    decision = await cerber_check_model_switch(role, data.model_id, MODEL_REGISTRY)
    if not decision.allowed:
        await LOG_BUS.warning(
            f"Role change blocked: {role} → {data.model_id} ({decision.reason})",
            source="cerber"
        )
        raise HTTPException(403, decision.reason)
    
    old_model = ROLES[role]
    set_role(role, data.model_id)
    
    await LOG_BUS.info(
        f"Role updated: {role} — {old_model} → {data.model_id}",
        source="roles"
    )
    
    return {
        "status": "ok",
        "role": role,
        "old_model": old_model,
        "new_model": data.model_id
    }


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/execute")
async def execute_task(req: TaskRequest):
    """Execute AI pipeline."""
    # Cerber validation
    task_decision = await cerber_check_task(req.instruction, req.mode.value)
    if not task_decision.allowed:
        await LOG_BUS.warning(
            f"Task blocked: {task_decision.reason}",
            source="cerber"
        )
        raise HTTPException(403, task_decision.reason)
    
    roles_decision = await cerber_check_roles(ROLES, MODEL_REGISTRY)
    if not roles_decision.allowed:
        await LOG_BUS.warning(
            f"Roles invalid: {roles_decision.reason}",
            source="cerber"
        )
        raise HTTPException(403, roles_decision.reason)
    
    await LOG_BUS.info(
        f"Pipeline starting — Mode: {req.mode.value}",
        source="executor"
    )
    
    result = await run_pipeline(req.instruction, req.mode.value)
    
    if not result.get("success"):
        raise HTTPException(500, result.get("error", "Pipeline failed"))
    
    return result


@router.post("/execute/plan")
async def execute_plan_only(instruction: str):
    """Quick endpoint for PLAN mode."""
    req = TaskRequest(instruction=instruction, mode=TaskMode.PLAN)
    return await execute_task(req)


@router.post("/execute/build")
async def execute_build(instruction: str):
    """Quick endpoint for BUILD mode."""
    req = TaskRequest(instruction=instruction, mode=TaskMode.BUILD)
    return await execute_task(req)


@router.post("/execute/test")
async def execute_full_test(instruction: str):
    """Quick endpoint for full TEST mode."""
    req = TaskRequest(instruction=instruction, mode=TaskMode.TEST)
    return await execute_task(req)


# ═══════════════════════════════════════════════════════════════════════════
# WEBSOCKET — LIVE LOGS
# ═══════════════════════════════════════════════════════════════════════════

@router.websocket("/logs")
async def logs_websocket(ws: WebSocket):
    """WebSocket endpoint for live logs."""
    await ws.accept()
    await LOG_BUS.connect(ws)
    
    try:
        # Send welcome message
        await ws.send_json({
            "timestamp": "NOW",
            "level": "INFO",
            "source": "system",
            "message": "Connected to ALFA_SEAT LogBus"
        })
        
        # Keep connection alive
        while True:
            try:
                # Wait for ping/messages (keep-alive)
                data = await ws.receive_text()
                if data == "ping":
                    await ws.send_text("pong")
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        await LOG_BUS.disconnect(ws)


# ═══════════════════════════════════════════════════════════════════════════
# CERBER STATUS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/cerber/status")
async def cerber_status():
    """Get Cerber security status."""
    from .cerber import CERBER_SEAT_ENABLED, ALLOWED_ROLE_MODELS, MAX_TASK_LENGTH
    
    return {
        "enabled": CERBER_SEAT_ENABLED,
        "max_task_length": MAX_TASK_LENGTH,
        "allowed_role_models": {
            role: list(models) 
            for role, models in ALLOWED_ROLE_MODELS.items()
        }
    }
