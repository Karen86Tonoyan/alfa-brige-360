"""
🌐 ALFA CLOUD API SERVER
FastAPI backend dla ALFA CLOUD OFFLINE
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

# Dodaj parent do path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from alfa_cloud.core.cloud_engine import CloudEngine
from alfa_cloud.api.routes import router as api_router
from alfa_cloud.api.ws import ws_handler

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LIFESPAN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Lifecycle management dla FastAPI"""
    # Startup
    print("""
    ╔═══════════════════════════════════════════╗
    ║       ☁️ ALFA CLOUD OFFLINE API ☁️        ║
    ║         http://127.0.0.1:8765            ║
    ╚═══════════════════════════════════════════╝
    """)
    
    # Inicjalizuj Cloud Engine
    cloud = CloudEngine()
    await cloud.start()
    app.state.cloud = cloud
    
    yield
    
    # Shutdown
    await cloud.stop()
    print("⏹️ ALFA CLOUD API zatrzymane")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app = FastAPI(
    title="ALFA CLOUD OFFLINE",
    description="Twoja prywatna chmura — 100% lokalna",
    version="1.0.0",
    lifespan=lifespan
)

# CORS dla LAN
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # LAN: wszystkie originy
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (dashboard)
dashboard_path = Path(__file__).parent.parent / "dashboard"
if dashboard_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")

# API routes
app.include_router(api_router, prefix="/api")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ROOT ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/", response_class=HTMLResponse)
async def root():
    """Strona główna"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ALFA CLOUD OFFLINE</title>
        <style>
            body { 
                background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
                color: #f5f5f5; 
                font-family: 'Segoe UI', system-ui, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
            }
            .container { text-align: center; }
            h1 { 
                font-size: 3em; 
                background: linear-gradient(90deg, #f8d15a, #ffa500);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .status { 
                background: #101018; 
                border: 1px solid #333; 
                border-radius: 12px; 
                padding: 20px; 
                margin: 20px;
            }
            a { color: #f8d15a; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .badge { 
                background: #2a2a3a; 
                padding: 5px 15px; 
                border-radius: 20px; 
                font-size: 0.9em;
                margin: 5px;
                display: inline-block;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>☁️ ALFA CLOUD OFFLINE</h1>
            <p>Twoja prywatna chmura — 100% lokalna, 0% internet</p>
            
            <div class="status">
                <p><strong>Status:</strong> 🟢 ONLINE</p>
                <p>
                    <span class="badge">🔐 AES-256-GCM</span>
                    <span class="badge">🤖 Ollama AI</span>
                    <span class="badge">🔄 LAN Sync</span>
                </p>
            </div>
            
            <p>
                <a href="/dashboard">📊 Dashboard</a> |
                <a href="/api/health">💚 Health Check</a> |
                <a href="/docs">📖 API Docs</a>
            </p>
        </div>
    </body>
    </html>
    """


@app.get("/ping")
async def ping():
    """Prosty ping"""
    return {"status": "pong", "cloud": "ALFA_CLOUD_OFFLINE"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEBSOCKET
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint dla real-time komunikacji"""
    cloud = websocket.app.state.cloud
    await ws_handler(websocket, cloud)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ERROR HANDLERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global error handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
            "cloud": "ALFA_CLOUD_OFFLINE"
        }
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
