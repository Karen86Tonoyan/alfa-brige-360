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
# ROUTES: MIRROR — GALLERY & ARCHIVE
# ═══════════════════════════════════════════════════════════════════════════

from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Import MIRROR modules
try:
    from modules.mirror_engine import mirror_gemini_response, list_sessions, get_archive_stats
    MIRROR_ROOT = Path("storage/gemini_mirror")
    MIRROR_AVAILABLE = True
    
    # Definiuj funkcje pomocnicze
    def get_all_sessions():
        return list_sessions(limit=1000)
    
    def get_session_path(session_id: str) -> Path:
        return MIRROR_ROOT / session_id
    
except ImportError as e:
    MIRROR_AVAILABLE = False
    MIRROR_ROOT = Path("storage/gemini_mirror")
    LOG.warning(f"MIRROR modules not available: {e}")

# Optional MIRROR modules
try:
    from modules.mirror_search import search_mirror
except ImportError:
    def search_mirror(query: str, limit: int = 50):
        return []

try:
    from modules.mirror_tags import TagManager
except ImportError:
    class TagManager:
        def tag(self, session, tag): pass
        def get_by_tag(self, tag): return []

try:
    from modules.mirror_zip import export_session_zip
except ImportError:
    def export_session_zip(session): raise NotImplementedError("mirror_zip not available")

try:
    from modules.mirror_month_export import export_month
except ImportError:
    def export_month(month): raise NotImplementedError("mirror_month_export not available")

try:
    from modules.mirror_backup import MirrorBackup
except ImportError:
    class MirrorBackup:
        def status(self): return {"status": "not_available"}
        def sync(self): return {"status": "not_available"}

# Mount static files for archive access
if MIRROR_ROOT.exists():
    try:
        app.mount("/archive", StaticFiles(directory=str(MIRROR_ROOT)), name="archive")
    except:
        pass


class MirrorSearchRequest(BaseModel):
    """MIRROR search request"""
    query: str
    limit: int = 50


class TagRequest(BaseModel):
    """Tag request"""
    session: str
    tags: List[str] = []


@app.get(f"{API_PREFIX}/mirror/status")
async def mirror_status():
    """MIRROR status check"""
    if not MIRROR_AVAILABLE:
        return {"available": False, "error": "MIRROR not installed"}
    
    sessions = get_all_sessions()
    return {
        "available": True,
        "root": str(MIRROR_ROOT),
        "sessions_count": len(sessions),
        "latest_sessions": sessions[:10]
    }


@app.get(f"{API_PREFIX}/gallery", response_class=HTMLResponse)
async def gallery(
    page: int = 1,
    limit: int = 50,
    client_ip: str = Depends(verify_ip)
):
    """
    HTML Gallery view for MIRROR archive.
    Shows all archived Gemini outputs with thumbnails.
    """
    if not MIRROR_AVAILABLE:
        return HTMLResponse("<h1>MIRROR not available</h1>", status_code=503)
    
    sessions = get_all_sessions()
    offset = (page - 1) * limit
    page_sessions = sessions[offset:offset + limit]
    
    # Build HTML gallery
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ALFA MIRROR — Gallery</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Segoe UI', sans-serif; 
            background: #0a0a0a; 
            color: #f0f0f0; 
            padding: 20px;
        }
        .header { 
            text-align: center; 
            padding: 30px; 
            background: linear-gradient(135deg, #1a1a1a, #000);
            border-bottom: 3px solid #FFD700;
            margin-bottom: 30px;
        }
        .header h1 { 
            font-size: 2.5em; 
            color: #FFD700; 
            text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
        }
        .header p { color: #888; margin-top: 10px; }
        .stats { 
            display: flex; 
            justify-content: center; 
            gap: 30px; 
            margin: 20px 0;
        }
        .stat { 
            background: #1a1a1a; 
            padding: 15px 25px; 
            border-radius: 8px;
            border: 1px solid #333;
        }
        .stat span { color: #FFD700; font-size: 1.5em; }
        .gallery { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); 
            gap: 20px;
        }
        .card { 
            background: #141414; 
            border: 1px solid #333;
            border-radius: 12px;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }
        .card:hover { 
            transform: translateY(-5px); 
            border-color: #FFD700;
        }
        .card-header {
            padding: 15px;
            background: #1a1a1a;
            border-bottom: 1px solid #333;
        }
        .card-header h3 { 
            color: #FFD700; 
            font-size: 0.9em;
            word-break: break-all;
        }
        .card-body { padding: 15px; }
        .card-body .preview { 
            width: 100%; 
            height: 150px; 
            object-fit: cover;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .card-meta { 
            font-size: 0.8em; 
            color: #666; 
        }
        .card-actions { 
            padding: 10px 15px;
            background: #1a1a1a;
            display: flex;
            gap: 10px;
        }
        .btn {
            padding: 8px 12px;
            background: #333;
            color: #fff;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8em;
        }
        .btn:hover { background: #FFD700; color: #000; }
        .pagination { 
            margin-top: 30px; 
            text-align: center;
        }
        .pagination a {
            padding: 10px 20px;
            background: #333;
            color: #fff;
            text-decoration: none;
            margin: 0 5px;
            border-radius: 4px;
        }
        .pagination a:hover { background: #FFD700; color: #000; }
        .search-box {
            max-width: 600px;
            margin: 0 auto 30px;
        }
        .search-box input {
            width: 100%;
            padding: 15px 20px;
            font-size: 1em;
            background: #1a1a1a;
            border: 2px solid #333;
            border-radius: 8px;
            color: #fff;
        }
        .search-box input:focus {
            outline: none;
            border-color: #FFD700;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐺 ALFA MIRROR</h1>
        <p>Archive Gallery — All Gemini Outputs</p>
    </div>
    
    <div class="stats">
        <div class="stat">
            <span>""" + str(len(sessions)) + """</span> Sessions
        </div>
        <div class="stat">
            Page <span>""" + str(page) + """</span> of """ + str((len(sessions) // limit) + 1) + """
        </div>
    </div>
    
    <div class="search-box">
        <form action="/api/v1/gallery/search" method="get">
        </form>
    </div>
    
    <div class="gallery">
    """
    
    for session in page_sessions:
        session_path = get_session_path(session)
        if session_path:
            # Find preview image
            preview_img = ""
            for f in session_path.glob("image_*"):
                preview_img = f"/archive/{session}/{f.name}"
                break
            for f in session_path.glob("thumb_*"):
                preview_img = f"/archive/{session}/{f.name}"
                break
            
            # Count files
            file_count = len(list(session_path.glob("*")))
            
            html += f"""
        <div class="card">
            <div class="card-header">
                <h3>{session}</h3>
            </div>
            <div class="card-body">
                {"<img class='preview' src='" + preview_img + "' />" if preview_img else "<div class='preview' style='background:#222;display:flex;align-items:center;justify-content:center;'>📄 Text Only</div>"}
                <div class="card-meta">{file_count} files</div>
            </div>
            <div class="card-actions">
                <a class="btn" href="/archive/{session}/" target="_blank">📂 Browse</a>
                <a class="btn" href="/api/v1/mirror/export/{session}">📦 ZIP</a>
            </div>
        </div>
            """
    
    html += """
    </div>
    
    <div class="pagination">
    """
    
    if page > 1:
        html += f'<a href="/api/v1/gallery?page={page-1}&limit={limit}">← Previous</a>'
    
    if offset + limit < len(sessions):
        html += f'<a href="/api/v1/gallery?page={page+1}&limit={limit}">Next →</a>'
    
    html += """
    </div>
</body>
</html>
    """
    
    return HTMLResponse(html)


@app.get(f"{API_PREFIX}/gallery/search")
async def gallery_search(
    q: str,
    limit: int = 50,
    client_ip: str = Depends(verify_ip)
):
    """Search MIRROR archive"""
    if not MIRROR_AVAILABLE:
        raise HTTPException(503, "MIRROR not available")
    
    results = search_mirror(q, limit=limit)
    return {
        "query": q,
        "count": len(results),
        "results": results
    }


@app.get(API_PREFIX + "/mirror/export/{session}")
async def mirror_export_session(
    session: str,
    client_ip: str = Depends(verify_ip)
):
    """Export session as ZIP"""
    if not MIRROR_AVAILABLE:
        raise HTTPException(503, "MIRROR not available")
    
    try:
        zip_path = export_session_zip(session)
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"{session}.zip"
        )
    except FileNotFoundError:
        raise HTTPException(404, f"Session not found: {session}")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get(API_PREFIX + "/mirror/export/month/{month}")
async def mirror_export_month(
    month: str,
    client_ip: str = Depends(verify_ip)
):
    """
    Export entire month as ZIP.
    Month format: YYYY-MM (e.g., 2025-01)
    """
    if not MIRROR_AVAILABLE:
        raise HTTPException(503, "MIRROR not available")
    
    try:
        zip_path = export_month(month)
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"ALFA_MIRROR_{month}.zip"
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get(f"{API_PREFIX}/timeline", response_class=HTMLResponse)
async def timeline_view(
    year: Optional[int] = None,
    month: Optional[int] = None,
    client_ip: str = Depends(verify_ip)
):
    """
    Timeline view of MIRROR archive.
    Shows sessions organized by date.
    """
    if not MIRROR_AVAILABLE:
        return HTMLResponse("<h1>MIRROR not available</h1>", status_code=503)
    
    from collections import defaultdict
    from datetime import datetime as dt
    
    sessions = get_all_sessions()
    
    # Group by month
    by_month = defaultdict(list)
    for s in sessions:
        try:
            # Format: YYYYMMDD_HHMMSS_UUID
            date_str = s.split("_")[0]
            parsed = dt.strptime(date_str, "%Y%m%d")
            month_key = parsed.strftime("%Y-%m")
            if year and parsed.year != year:
                continue
            if month and parsed.month != month:
                continue
            by_month[month_key].append(s)
        except:
            by_month["unknown"].append(s)
    
    # Build HTML
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ALFA MIRROR — Timeline</title>
    <style>
        body { 
            font-family: 'Segoe UI', sans-serif; 
            background: #0a0a0a; 
            color: #f0f0f0; 
            padding: 40px;
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 { color: #FFD700; margin-bottom: 30px; }
        .month-block { 
            margin-bottom: 40px;
            background: #141414;
            border-radius: 12px;
            padding: 20px;
            border-left: 4px solid #FFD700;
        }
        .month-header { 
            font-size: 1.5em; 
            color: #FFD700;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .month-header .count { 
            font-size: 0.7em;
            background: #333;
            padding: 5px 10px;
            border-radius: 4px;
        }
        .sessions-list { 
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
        }
        .session-item {
            background: #1a1a1a;
            padding: 12px;
            border-radius: 6px;
            font-size: 0.9em;
            word-break: break-all;
        }
        .session-item:hover { background: #2a2a2a; }
        .session-item a { color: #FFD700; text-decoration: none; }
        .export-btn {
            display: inline-block;
            padding: 8px 16px;
            background: #333;
            color: #fff;
            border-radius: 4px;
            text-decoration: none;
            font-size: 0.8em;
        }
        .export-btn:hover { background: #FFD700; color: #000; }
    </style>
</head>
<body>
    <h1>🐺 ALFA MIRROR — Timeline</h1>
    """
    
    for month_key in sorted(by_month.keys(), reverse=True):
        month_sessions = by_month[month_key]
        html += f"""
    <div class="month-block">
        <div class="month-header">
            <span>📅 {month_key}</span>
            <span class="count">{len(month_sessions)} sessions</span>
            <a class="export-btn" href="/api/v1/mirror/export/month/{month_key}">📦 Export Month</a>
        </div>
        <div class="sessions-list">
        """
        
        for s in month_sessions[:20]:  # Limit 20 per month
            html += f'<div class="session-item"><a href="/archive/{s}/" target="_blank">{s}</a></div>'
        
        if len(month_sessions) > 20:
            html += f'<div class="session-item">...and {len(month_sessions) - 20} more</div>'
        
        html += "</div></div>"
    
    html += "</body></html>"
    return HTMLResponse(html)


@app.post(f"{API_PREFIX}/mirror/tags")
async def add_tags(
    request: TagRequest,
    client_ip: str = Depends(verify_ip)
):
    """Add tags to a session"""
    if not MIRROR_AVAILABLE:
        raise HTTPException(503, "MIRROR not available")
    
    tag_manager = TagManager()
    for tag in request.tags:
        tag_manager.tag(request.session, tag)
    
    return {"session": request.session, "tags": request.tags, "status": "added"}


@app.get(API_PREFIX + "/mirror/tags/{tag}")
async def get_by_tag(
    tag: str,
    client_ip: str = Depends(verify_ip)
):
    """Get all sessions with a specific tag"""
    if not MIRROR_AVAILABLE:
        raise HTTPException(503, "MIRROR not available")
    
    tag_manager = TagManager()
    sessions = tag_manager.get_by_tag(tag)
    
    return {"tag": tag, "count": len(sessions), "sessions": sessions}


@app.get(f"{API_PREFIX}/mirror/backup/status")
async def backup_status():
    """Get backup status"""
    if not MIRROR_AVAILABLE:
        raise HTTPException(503, "MIRROR not available")
    
    backup = MirrorBackup()
    return backup.status()


@app.post(f"{API_PREFIX}/mirror/backup/sync")
async def trigger_backup(
    client_ip: str = Depends(verify_ip)
):
    """Trigger manual backup sync"""
    if not MIRROR_AVAILABLE:
        raise HTTPException(503, "MIRROR not available")
    
    backup = MirrorBackup()
    synced = backup.sync_now()
    
    return {"synced_files": synced, "status": "completed"}


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
