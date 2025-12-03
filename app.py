# ═══════════════════════════════════════════════════════════════════════════
# ALFA CORE v2.0 — REST API — FastAPI Backend
# ═══════════════════════════════════════════════════════════════════════════
"""
REST API dla ALFA System.

Endpoints:
    /health          - Health check
    /status          - System status
    /chat            - AI chat (Ollama/DeepSeek)
    /modules         - Module management
    /cerber          - Security endpoints
    /events          - EventBus access

Usage:
    python app.py              # Development mode (uvicorn reload)
    python app.py --prod       # Production mode
    python app.py --port 8080  # Custom port

Dependencies:
    pip install fastapi uvicorn pydantic
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from pydantic import BaseModel, Field

try:
    from fastapi import FastAPI, HTTPException, Request, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, StreamingResponse
except ImportError:
    print("FastAPI not installed. Run: pip install fastapi uvicorn")
    sys.exit(1)

# Add root to path
ALFA_ROOT = Path(__file__).parent
sys.path.insert(0, str(ALFA_ROOT))

from config import VERSION, CODENAME, DEV_MODE, ALLOWED_IPS
from core_manager import CoreManager, get_manager
from core import get_bus, get_cerber, Priority, publish

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LOG = logging.getLogger("alfa.api")

API_PREFIX = "/api/v1"
DEFAULT_PORT = 8000

# ═══════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    """Chat request model"""
    prompt: str = Field(..., min_length=1, max_length=10000)
    profile: str = Field(default="balanced", pattern="^(fast|balanced|creative|security)$")
    stream: bool = False
    context: Optional[List[Dict[str, str]]] = None

class ChatResponse(BaseModel):
    """Chat response model"""
    content: str
    model: str
    profile: str
    tokens: Optional[int] = None
    latency_ms: float

class ModuleRequest(BaseModel):
    """Module operation request"""
    name: str = Field(..., min_length=1)
    action: str = Field(..., pattern="^(load|unload|reload)$")

class CerberVerifyRequest(BaseModel):
    """Cerber verification request"""
    path: str

class EventRequest(BaseModel):
    """Event publish request"""
    topic: str = Field(..., min_length=1)
    payload: Optional[Any] = None
    priority: int = Field(default=50, ge=0, le=200)

class StatusResponse(BaseModel):
    """System status response"""
    version: str
    codename: str
    mode: str
    uptime_seconds: float
    extensions_count: int
    mcp_servers_count: int
    layers: Dict[str, List[str]]
    cerber_status: Dict[str, Any]
    eventbus_stats: Dict[str, Any]

# ═══════════════════════════════════════════════════════════════════════════
# DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════

_start_time = datetime.now()

def get_core_manager() -> CoreManager:
    """Dependency: get CoreManager singleton"""
    return get_manager()

async def verify_ip(request: Request):
    """Dependency: verify client IP"""
    client_ip = request.client.host if request.client else "unknown"
    
    cerber = get_cerber()
    if not cerber.check_ip(client_ip):
        LOG.warning(f"Blocked request from {client_ip}")
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return client_ip

# ═══════════════════════════════════════════════════════════════════════════
# LIFESPAN
# ═══════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown"""
    # Startup
    LOG.info("ALFA API starting...")
    
    # Start EventBus
    bus = get_bus()
    bus.start()
    
    # Start Cerber
    cerber = get_cerber(str(ALFA_ROOT))
    cerber.start()
    
    # Emit boot event
    publish("system.api.started", {"port": DEFAULT_PORT}, priority=Priority.HIGH)
    
    LOG.info(f"ALFA API v{VERSION} ready")
    
    yield
    
    # Shutdown
    LOG.info("ALFA API shutting down...")
    publish("system.api.stopping", priority=Priority.CRITICAL)
    
    cerber.stop()
    bus.stop()
    
    LOG.info("ALFA API stopped")

# ═══════════════════════════════════════════════════════════════════════════
# APP INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="ALFA System API",
    description="REST API for ALFA System v2.0 - AI-powered personal assistant",
    version=VERSION,
    lifespan=lifespan,
    docs_url="/docs" if DEV_MODE else None,
    redoc_url="/redoc" if DEV_MODE else None
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if DEV_MODE else ["http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ═══════════════════════════════════════════════════════════════════════════
# ROUTES: SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "ALFA System API",
        "version": VERSION,
        "codename": CODENAME,
        "docs": "/docs" if DEV_MODE else None
    }

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.get(f"{API_PREFIX}/status", response_model=StatusResponse)
async def status(
    manager: CoreManager = Depends(get_core_manager),
    client_ip: str = Depends(verify_ip)
):
    """Get system status"""
    uptime = (datetime.now() - _start_time).total_seconds()
    mgr_status = manager.get_status()
    
    cerber = get_cerber()
    bus = get_bus()
    
    return StatusResponse(
        version=VERSION,
        codename=CODENAME,
        mode="DEV" if DEV_MODE else "PROD",
        uptime_seconds=uptime,
        extensions_count=mgr_status["extensions_count"],
        mcp_servers_count=mgr_status["mcp_servers_count"],
        layers=mgr_status["layers"],
        cerber_status=cerber.status(),
        eventbus_stats=bus.stats()
    )

# ═══════════════════════════════════════════════════════════════════════════
# ROUTES: CHAT / AI
# ═══════════════════════════════════════════════════════════════════════════

@app.post(f"{API_PREFIX}/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    manager: CoreManager = Depends(get_core_manager),
    client_ip: str = Depends(verify_ip)
):
    """
    Send prompt to AI (Ollama).
    
    Profiles:
    - fast: mistral, low temp
    - balanced: llama3, medium temp
    - creative: deepseek-r1, high temp
    - security: low temp, strict
    """
    import time
    start = time.time()
    
    # Build messages
    messages = request.context or []
    messages.append({"role": "user", "content": request.prompt})
    
    # Get profile config
    from config import MODELS
    profile_config = MODELS.get(request.profile, MODELS["balanced"])
    
    # Call Ollama
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": profile_config["model"],
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": profile_config.get("temperature", 0.7),
                        "top_p": profile_config.get("top_p", 0.9)
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            
    except Exception as e:
        LOG.error(f"Ollama error: {e}")
        raise HTTPException(status_code=503, detail=f"AI service unavailable: {e}")
    
    latency = (time.time() - start) * 1000
    
    # Emit event
    publish("chat.response", {
        "profile": request.profile,
        "tokens": data.get("eval_count"),
        "latency_ms": latency
    })
    
    return ChatResponse(
        content=data.get("message", {}).get("content", ""),
        model=profile_config["model"],
        profile=request.profile,
        tokens=data.get("eval_count"),
        latency_ms=latency
    )

@app.post(f"{API_PREFIX}/chat/stream")
async def chat_stream(
    request: ChatRequest,
    manager: CoreManager = Depends(get_core_manager),
    client_ip: str = Depends(verify_ip)
):
    """Stream chat response (SSE)"""
    from config import MODELS
    profile_config = MODELS.get(request.profile, MODELS["balanced"])
    
    messages = request.context or []
    messages.append({"role": "user", "content": request.prompt})
    
    async def stream_generator():
        import httpx
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                "http://localhost:11434/api/chat",
                json={
                    "model": profile_config["model"],
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": profile_config.get("temperature", 0.7)
                    }
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        yield f"data: {line}\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream"
    )

# ═══════════════════════════════════════════════════════════════════════════
# ROUTES: MODULES
# ═══════════════════════════════════════════════════════════════════════════

@app.get(f"{API_PREFIX}/modules")
async def list_modules(
    manager: CoreManager = Depends(get_core_manager),
    client_ip: str = Depends(verify_ip)
):
    """List all modules"""
    return {
        "modules": manager.list_modules(),
        "loaded": [
            name for name, info in manager.modules.items()
            if info.status.value == "loaded"
        ]
    }

@app.post(f"{API_PREFIX}/modules")
async def module_action(
    request: ModuleRequest,
    manager: CoreManager = Depends(get_core_manager),
    client_ip: str = Depends(verify_ip)
):
    """Load/unload/reload module"""
    if request.action == "load":
        info = manager.load_module(request.name)
        if not info:
            raise HTTPException(status_code=404, detail=f"Module not found: {request.name}")
        return {"status": "loaded", "module": request.name}
    
    elif request.action == "unload":
        if not manager.unload_module(request.name):
            raise HTTPException(status_code=404, detail=f"Module not found: {request.name}")
        return {"status": "unloaded", "module": request.name}
    
    elif request.action == "reload":
        info = manager.reload_module(request.name)
        if not info:
            raise HTTPException(status_code=404, detail=f"Module not found: {request.name}")
        return {"status": "reloaded", "module": request.name}

@app.get(f"{API_PREFIX}/modules/{{name}}")
async def get_module_info(
    name: str,
    manager: CoreManager = Depends(get_core_manager),
    client_ip: str = Depends(verify_ip)
):
    """Get module info"""
    info = manager.get_module_info(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Module not found: {name}")
    
    return {
        "name": info.name,
        "type": info.type.value,
        "status": info.status.value,
        "layer": info.layer,
        "enabled": info.enabled,
        "description": info.description,
        "commands": info.commands,
        "error": info.error
    }

# ═══════════════════════════════════════════════════════════════════════════
# ROUTES: LAYERS (MCP)
# ═══════════════════════════════════════════════════════════════════════════

@app.get(f"{API_PREFIX}/layers")
async def list_layers(
    manager: CoreManager = Depends(get_core_manager),
    client_ip: str = Depends(verify_ip)
):
    """List MCP layers"""
    return {"layers": manager.layers}

@app.get(f"{API_PREFIX}/layers/{{name}}")
async def get_layer(
    name: str,
    manager: CoreManager = Depends(get_core_manager),
    client_ip: str = Depends(verify_ip)
):
    """Get layer servers"""
    if name not in manager.layers:
        raise HTTPException(status_code=404, detail=f"Layer not found: {name}")
    
    servers = manager.layers[name]
    return {
        "layer": name,
        "servers": servers,
        "count": len(servers)
    }

@app.get(f"{API_PREFIX}/mcp/health")
async def mcp_health(
    manager: CoreManager = Depends(get_core_manager),
    client_ip: str = Depends(verify_ip)
):
    """Check MCP servers health"""
    health = await manager.mcp_health()
    return {"servers": health}

# ═══════════════════════════════════════════════════════════════════════════
# ROUTES: CERBER
# ═══════════════════════════════════════════════════════════════════════════

@app.get(f"{API_PREFIX}/cerber/status")
async def cerber_status(client_ip: str = Depends(verify_ip)):
    """Get Cerber status"""
    cerber = get_cerber()
    return cerber.status()

@app.post(f"{API_PREFIX}/cerber/verify")
async def cerber_verify(
    request: CerberVerifyRequest,
    client_ip: str = Depends(verify_ip)
):
    """Verify file integrity"""
    cerber = get_cerber()
    ok = cerber.verify_file(request.path)
    
    return {
        "path": request.path,
        "integrity": "ok" if ok else "compromised",
        "verified_at": datetime.now().isoformat()
    }

@app.get(f"{API_PREFIX}/cerber/incidents")
async def cerber_incidents(
    limit: int = 20,
    level: Optional[str] = None,
    client_ip: str = Depends(verify_ip)
):
    """Get Cerber incidents"""
    cerber = get_cerber()
    incidents = cerber.incidents(limit, level)
    
    return {
        "incidents": [
            {
                "id": i.id,
                "timestamp": i.timestamp,
                "level": i.level,
                "message": i.message,
                "source": i.source
            }
            for i in incidents
        ],
        "count": len(incidents)
    }

# ═══════════════════════════════════════════════════════════════════════════
# ROUTES: EVENTS
# ═══════════════════════════════════════════════════════════════════════════

@app.post(f"{API_PREFIX}/events")
async def publish_event(
    request: EventRequest,
    client_ip: str = Depends(verify_ip)
):
    """Publish event to EventBus"""
    event_id = publish(
        request.topic,
        request.payload,
        source=f"api:{client_ip}",
        priority=request.priority
    )
    
    return {
        "event_id": event_id,
        "topic": request.topic,
        "published_at": datetime.now().isoformat()
    }

@app.get(f"{API_PREFIX}/events/stats")
async def event_stats(client_ip: str = Depends(verify_ip)):
    """Get EventBus stats"""
    bus = get_bus()
    return bus.stats()

@app.get(f"{API_PREFIX}/events/topics")
async def event_topics(client_ip: str = Depends(verify_ip)):
    """Get registered topics"""
    bus = get_bus()
    return {"topics": list(bus.topics())}

@app.get(f"{API_PREFIX}/events/audit")
async def event_audit(
    limit: int = 50,
    topic: Optional[str] = None,
    client_ip: str = Depends(verify_ip)
):
    """Get event audit log"""
    bus = get_bus()
    return {"entries": bus.audit_log(topic=topic, limit=limit)}

@app.get(f"{API_PREFIX}/events/dlq")
async def event_dlq(
    limit: int = 10,
    client_ip: str = Depends(verify_ip)
):
    """Get dead letter queue"""
    bus = get_bus()
    dlq = bus.dead_letters(limit)
    
    return {
        "dead_letters": [
            {
                "event_id": e.event_id,
                "topic": e.topic,
                "reason": reason
            }
            for e, reason in dlq
        ]
    }

# ═══════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    LOG.error(f"Unhandled error: {exc}", exc_info=True)
    
    # Log to Cerber
    cerber = get_cerber()
    cerber.db.log_incident(
        level=__import__("core.cerber", fromlist=["IncidentLevel"]).IncidentLevel.ERROR,
        message=str(exc),
        source="api",
        details=str(request.url)
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if DEV_MODE else None
        }
    )

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ALFA System API")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--prod", action="store_true", help="Production mode (no reload)")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    
    args = parser.parse_args()
    
    import uvicorn
    
    logging.basicConfig(
        level=logging.DEBUG if DEV_MODE else logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    )
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                  ALFA SYSTEM API v{VERSION}                  ║
╚═══════════════════════════════════════════════════════════╝
    Host: {args.host}
    Port: {args.port}
    Mode: {'PROD' if args.prod else 'DEV'}
    Docs: http://{args.host}:{args.port}/docs
""")
    
    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=not args.prod,
        workers=args.workers if args.prod else 1
    )
