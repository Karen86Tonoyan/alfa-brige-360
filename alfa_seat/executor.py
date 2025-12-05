"""
ALFA_SEAT — Pipeline Executor
Orchestrates multi-model AI pipeline execution.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .registry import MODEL_REGISTRY, get_adapter
from .roles import ROLES
from .logs import LOG_BUS

logger = logging.getLogger("ALFA.Seat.Executor")


@dataclass
class PipelineStage:
    """Result from a single pipeline stage."""
    role: str
    model_id: str
    output: str
    duration_ms: int
    success: bool
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""
    mode: str
    stages: list
    total_duration_ms: int
    success: bool
    
    # Stage outputs
    plan: Optional[str] = None
    code: Optional[str] = None
    final_code: Optional[str] = None
    test: Optional[str] = None
    insight: Optional[str] = None


async def run_pipeline(instruction: str, mode: str) -> Dict[str, Any]:
    """
    Execute multi-model AI pipeline.
    
    Modes:
    - PLAN: Only architect creates plan
    - BUILD: Architect → Integrator → Coder
    - TEST: Full pipeline with testing and analysis
    
    Args:
        instruction: Task instruction
        mode: Execution mode (PLAN/BUILD/TEST)
        
    Returns:
        Pipeline result dictionary
    """
    start_time = time.time()
    stages = []
    result = {"mode": mode, "instruction": instruction}
    
    try:
        # ═══════════════════════════════════════════════════════════════════
        # STAGE 1: ARCHITECT — Creates plan
        # ═══════════════════════════════════════════════════════════════════
        arch_model = ROLES["architect"]
        await LOG_BUS.pipeline("ARCHITECT", "Starting", f"Model: {arch_model}")
        
        stage_start = time.time()
        architect = get_adapter(arch_model)
        
        if not architect:
            raise ValueError(f"Architect model not found: {arch_model}")
        
        plan = await architect.plan(instruction)
        stage_duration = int((time.time() - stage_start) * 1000)
        
        stages.append(PipelineStage(
            role="architect",
            model_id=arch_model,
            output=plan[:500] + "..." if len(plan) > 500 else plan,
            duration_ms=stage_duration,
            success=True
        ))
        
        result["plan"] = plan
        await LOG_BUS.pipeline("ARCHITECT", "Complete", f"{stage_duration}ms")
        
        if mode == "PLAN":
            result["stages"] = [s.__dict__ for s in stages]
            result["total_duration_ms"] = int((time.time() - start_time) * 1000)
            result["success"] = True
            return result
        
        # ═══════════════════════════════════════════════════════════════════
        # STAGE 2: INTEGRATOR — Generates initial code
        # ═══════════════════════════════════════════════════════════════════
        integ_model = ROLES["integrator"]
        await LOG_BUS.pipeline("INTEGRATOR", "Starting", f"Model: {integ_model}")
        
        stage_start = time.time()
        integrator = get_adapter(integ_model)
        
        if not integrator:
            raise ValueError(f"Integrator model not found: {integ_model}")
        
        code = await integrator.generate(plan)
        stage_duration = int((time.time() - stage_start) * 1000)
        
        stages.append(PipelineStage(
            role="integrator",
            model_id=integ_model,
            output=code[:500] + "..." if len(code) > 500 else code,
            duration_ms=stage_duration,
            success=True
        ))
        
        result["code"] = code
        await LOG_BUS.pipeline("INTEGRATOR", "Complete", f"{stage_duration}ms")
        
        # ═══════════════════════════════════════════════════════════════════
        # STAGE 3: CODER — Refines code
        # ═══════════════════════════════════════════════════════════════════
        coder_model = ROLES["coder"]
        await LOG_BUS.pipeline("CODER", "Starting", f"Model: {coder_model}")
        
        stage_start = time.time()
        coder = get_adapter(coder_model)
        
        if not coder:
            raise ValueError(f"Coder model not found: {coder_model}")
        
        final_code = await coder.generate(code)
        stage_duration = int((time.time() - stage_start) * 1000)
        
        stages.append(PipelineStage(
            role="coder",
            model_id=coder_model,
            output=final_code[:500] + "..." if len(final_code) > 500 else final_code,
            duration_ms=stage_duration,
            success=True
        ))
        
        result["final_code"] = final_code
        await LOG_BUS.pipeline("CODER", "Complete", f"{stage_duration}ms")
        
        if mode == "BUILD":
            result["stages"] = [s.__dict__ for s in stages]
            result["total_duration_ms"] = int((time.time() - start_time) * 1000)
            result["success"] = True
            return result
        
        # ═══════════════════════════════════════════════════════════════════
        # STAGE 4: TESTER — Analyzes and tests
        # ═══════════════════════════════════════════════════════════════════
        tester_model = ROLES["tester"]
        await LOG_BUS.pipeline("TESTER", "Starting", f"Model: {tester_model}")
        
        stage_start = time.time()
        tester = get_adapter(tester_model)
        
        if not tester:
            raise ValueError(f"Tester model not found: {tester_model}")
        
        test = await tester.analyze(final_code)
        stage_duration = int((time.time() - stage_start) * 1000)
        
        stages.append(PipelineStage(
            role="tester",
            model_id=tester_model,
            output=test[:500] + "..." if len(test) > 500 else test,
            duration_ms=stage_duration,
            success=True
        ))
        
        result["test"] = test
        await LOG_BUS.pipeline("TESTER", "Complete", f"{stage_duration}ms")
        
        # ═══════════════════════════════════════════════════════════════════
        # STAGE 5: ANALYST — Final insights
        # ═══════════════════════════════════════════════════════════════════
        analyst_model = ROLES["analyst"]
        await LOG_BUS.pipeline("ANALYST", "Starting", f"Model: {analyst_model}")
        
        stage_start = time.time()
        analyst = get_adapter(analyst_model)
        
        if not analyst:
            raise ValueError(f"Analyst model not found: {analyst_model}")
        
        insight = await analyst.analyze(test)
        stage_duration = int((time.time() - stage_start) * 1000)
        
        stages.append(PipelineStage(
            role="analyst",
            model_id=analyst_model,
            output=insight[:500] + "..." if len(insight) > 500 else insight,
            duration_ms=stage_duration,
            success=True
        ))
        
        result["insight"] = insight
        await LOG_BUS.pipeline("ANALYST", "Complete", f"{stage_duration}ms")
        
        # ═══════════════════════════════════════════════════════════════════
        # FINALIZE
        # ═══════════════════════════════════════════════════════════════════
        result["stages"] = [s.__dict__ for s in stages]
        result["total_duration_ms"] = int((time.time() - start_time) * 1000)
        result["success"] = True
        
        await LOG_BUS.info(
            f"Pipeline complete: {result['total_duration_ms']}ms, {len(stages)} stages",
            source="executor"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        await LOG_BUS.error(f"Pipeline failed: {str(e)}", source="executor")
        
        result["stages"] = [s.__dict__ for s in stages]
        result["total_duration_ms"] = int((time.time() - start_time) * 1000)
        result["success"] = False
        result["error"] = str(e)
        
        return result
