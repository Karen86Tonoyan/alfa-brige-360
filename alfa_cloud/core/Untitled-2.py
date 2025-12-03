mkdir -p alfa_cloud/{core,api,ai,agents,storage,config,logs,clients,dashboard}alfa_cloud/
├── core/
│   ├── config_loader.py
│   ├── event_bus.py
│   ├── cloud_engine.py
│   ├── encryption.py
│   ├── storage_engine.py
│   └── sync_engine.py
├── api/
│   ├── server.py
│   ├── routes.py
│   ├── auth.py
│   └── ws.py
├── ai/
│   ├── local_llm.py
│   └── analyzer.py
├── agents/
│   ├── file_agent.py
│   └── backup_agent.py
├── storage/
│   ├── vault/        # szyfrowane
│   ├── plain/        # nieszyfrowane
│   └── meta/
├── config/
│   └── cloud_config.json
├── dashboard/
│   ├── index.html
│   └── dashboard.js
├── clients/
│   └── android_api.md
├── run_cloud.py
└── __main__.py       # żeby działało: `python -m alfa_cloud`# alfa_cloud/core/config_loader.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

class ConfigError(Exception):
    pass

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "cloud_config.json"

def load_config(path: Path | None = None) -> Dict[str, Any]:
    cfg_path = path or DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise ConfigError(f"Config not found: {cfg_path}")
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {cfg_path}: {exc}") from exc
    return data    # alfa_cloud/core/event_bus.py
    from __future__ import annotations
    import asyncio
    from collections import defaultdict
    from typing import Awaitable, Callable, Dict, List, Any
    
    Handler = Callable[[Any], Awaitable[None]]
    
    class EventBus:
        def __init__(self) -> None:
            self._subscribers: Dict[str, List[Handler]] = defaultdict(list)
    
        def subscribe(self, event_name: str, handler: Handler) -> None:
            self._subscribers[event_name].append(handler)
    
        async def publish(self, event_name: str, payload: Any) -> None:
            handlers = self._subscribers.get(event_name, [])
            for h in handlers:
                # prosty fire-and-forget; można rozbudować o taski i logowanie
                await h(payload)                # alfa_cloud/core/encryption.py
                from __future__ import annotations
                from dataclasses import dataclass
                from typing import Optional
                import os
                import hashlib
                
                # Tu normalnie użyłbyś: from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                # ale zostawiamy to jako hook, żebyś mógł dobrać lib wg uznania.
                
                @dataclass
                class EncryptionConfig:
                    enabled: bool
                    algorithm: str
                    hash_algorithm: str
                
                class VaultCrypto:
                    def __init__(self, cfg: EncryptionConfig) -> None:
                        self.cfg = cfg
                
                    def hash_bytes(self, data: bytes) -> str:
                        if self.cfg.hash_algorithm.lower() == "blake2b":
                            return hashlib.blake2b(data).hexdigest()
                        return hashlib.sha256(data).hexdigest()
                
                    def encrypt(self, data: bytes, key: bytes) -> bytes:
                        if not self.cfg.enabled:
                            return data
                        # TODO: zaimplementuj AES-256-GCM przy użyciu wybranej biblioteki
                        # Placeholder: NIE JEST BEZPIECZNY, tylko szkielet!
                        return data[::-1]
                
                    def decrypt(self, data: bytes, key: bytes) -> bytes:
                        if not self.cfg.enabled:
                            return data
                        # TODO: AES-256-GCM
                        return data[::-1]
                
                def derive_key_from_password(password: str, salt: bytes) -> bytes:
                    # Hook pod Argon2id – możesz użyć argon2-cffi
                    # Tu placeholder: NIE do użycia produkcyjnie, tylko API.
                    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000, dklen=32)                    # alfa_cloud/core/storage_engine.py
                    from __future__ import annotations
                    from dataclasses import dataclass
                    from pathlib import Path
                    from typing import Optional
                    import os
                    
                    from .encryption import VaultCrypto
                    
                    @dataclass
                    class StorageConfig:
                        root_path: Path
                        max_size_gb: int
                        chunk_size_mb: int
                        compression: str
                        deduplication: bool
                    
                    class StorageEngine:
                        def __init__(self, cfg: StorageConfig, crypto: VaultCrypto) -> None:
                            self.cfg = cfg
                            self.crypto = crypto
                            self.root_plain = cfg.root_path / "plain"
                            self.root_vault = cfg.root_path / "vault"
                            self.root_plain.mkdir(parents=True, exist_ok=True)
                            self.root_vault.mkdir(parents=True, exist_ok=True)
                    
                        def save_file_plain(self, src_path: Path, dest_name: Optional[str] = None) -> Path:
                            dest_name = dest_name or src_path.name
                            dest = self.root_plain / dest_name
                            data = src_path.read_bytes()
                            dest.write_bytes(data)
                            return dest
                    
                        def save_file_vault(self, src_path: Path, key: bytes, dest_name: Optional[str] = None) -> Path:
                            dest_name = dest_name or src_path.name
                            dest = self.root_vault / dest_name
                            data = src_path.read_bytes()
                            enc = self.crypto.encrypt(data, key)
                            dest.write_bytes(enc)
                            return dest                            # alfa_cloud/core/sync_engine.py
                            from __future__ import annotations
                            from dataclasses import dataclass
                            from typing import List
                            
                            @dataclass
                            class SyncConfig:
                                enabled: bool
                                mode: str
                                auto_sync: bool
                                sync_interval_seconds: int
                                conflict_resolution: str
                                hash_compare: bool
                            
                            class SyncEngine:
                                def __init__(self, cfg: SyncConfig) -> None:
                                    self.cfg = cfg
                            
                                async def sync_to_peer(self, address: str) -> None:
                                    if not self.cfg.enabled:
                                        return
                                    # TODO: implement LAN sync (TCP/UDP, wymiana list plików, porównanie hashów)
                                    print(f"[SYNC] (stub) syncing to {address}")                                    # alfa_cloud/ai/local_llm.py
                                    from __future__ import annotations
                                    from dataclasses import dataclass
                                    from typing import Dict, Any
                                    import httpx
                                    
                                    @dataclass
                                    class LocalAIConfig:
                                        enabled: bool
                                        provider: str
                                        endpoint: str
                                        default_model: str
                                        models: Dict[str, str]
                                    
                                    class LocalAI:
                                        def __init__(self, cfg: LocalAIConfig) -> None:
                                            self.cfg = cfg
                                    
                                        async def generate(self, prompt: str, task: str = "analysis") -> str:
                                            if not self.cfg.enabled:
                                                return "[AI DISABLED]"
                                            model = self.cfg.models.get(task, self.cfg.default_model)
                                            async with httpx.AsyncClient() as client:
                                                resp = await client.post(
                                                    f"{self.cfg.endpoint}/api/generate",
                                                    json={"model": model, "prompt": prompt, "stream": False},
                                                    timeout=60,
                                                )
                                            resp.raise_for_status()
                                            data = resp.json()
                                            # zależnie od API ollama – dostosuj
                                            return data.get("response") or data.get("output", "")                                            # alfa_cloud/api/auth.py
                                            from __future__ import annotations
                                            from fastapi import Header, HTTPException, status
                                            
                                            # super-prosty mechanizm; możesz później podmienić na JWT/klucze
                                            API_TOKEN = "alfa-dev-token"
                                            
                                            async def require_auth(authorization: str = Header(...)) -> None:
                                                if authorization != f"Bearer {API_TOKEN}":
                                                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")                                                    # alfa_cloud/api/routes.py
                                                    from __future__ import annotations
                                                    from fastapi import APIRouter, Depends, UploadFile, File
                                                    from pathlib import Path
                                                    
                                                    from ..core.cloud_engine import CloudContext
                                                    from .auth import require_auth
                                                    
                                                    router = APIRouter()
                                                    
                                                    def get_ctx() -> CloudContext:
                                                        # w run_cloud przypniemy CloudContext do app.state
                                                        from .server import app
                                                        return app.state.cloud_ctx  # type: ignore[attr-defined]
                                                    
                                                    @router.get("/health")
                                                    async def health(ctx: CloudContext = Depends(get_ctx)):
                                                        return {
                                                            "cloud": ctx.cfg["cloud_name"],
                                                            "mode": ctx.cfg["mode"],
                                                            "version": ctx.cfg["version"],
                                                        }
                                                    
                                                    @router.post("/upload", dependencies=[Depends(require_auth)])
                                                    async def upload_file(
                                                        file: UploadFile = File(...),
                                                        ctx: CloudContext = Depends(get_ctx),
                                                    ):
                                                        data = await file.read()
                                                        dest = ctx.storage.root_plain / file.filename
                                                        dest.write_bytes(data)
                                                        return {"status": "ok", "path": str(dest)}
                                                    
                                                    @router.post("/ai/analyze", dependencies=[Depends(require_auth)])
                                                    async def ai_analyze(
                                                        payload: dict,
                                                        ctx: CloudContext = Depends(get_ctx),
                                                    ):
                                                        text = payload.get("text", "")
                                                        result = await ctx.ai.generate(text, task="analysis")
                                                        return {"result": result}                                                        # alfa_cloud/api/ws.py
                                                        from __future__ import annotations
                                                        from fastapi import WebSocket, WebSocketDisconnect
                                                        from ..core.cloud_engine import CloudContext
                                                        
                                                        async def ws_handler(ws: WebSocket, ctx: CloudContext) -> None:
                                                            await ws.accept()
                                                            await ws.send_text("ALFA_CLOUD_OFFLINE_WS_READY")
                                                            try:
                                                                while True:
                                                                    msg = await ws.receive_text()
                                                                    # ping-pong + prosty AI echo
                                                                    if msg.startswith("/ai "):
                                                                        prompt = msg[4:]
                                                                        ans = await ctx.ai.generate(prompt)
                                                                        await ws.send_text(f"AI: {ans}")
                                                                    else:
                                                                        await ws.send_text(f"ECHO: {msg}")
                                                            except WebSocketDisconnect:
                                                                await ws.close()# alfa_cloud/api/server.py
from __future__ import annotations
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..core.cloud_engine import build_cloud
from .routes import router as api_router
from .ws import ws_handler

app = FastAPI(title="ALFA CLOUD OFFLINE")

# CORS na LAN
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# dashboard statyczny
app.mount("/dashboard", StaticFiles(directory="alfa_cloud/dashboard", html=True), name="dashboard")

# budujemy CloudContext i przypinamy do app.state
app.state.cloud_ctx = build_cloud()

app.include_router(api_router, prefix="/api")

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_handler(ws, app.state.cloud_ctx)