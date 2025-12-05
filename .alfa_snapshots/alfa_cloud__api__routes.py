"""
🛤️ ALFA CLOUD API ROUTES
Endpointy REST dla ALFA CLOUD OFFLINE
"""

from __future__ import annotations
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from alfa_cloud.api.auth import require_auth, get_current_user
from alfa_cloud.core.cloud_engine import CloudEngine

router = APIRouter()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODELS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AIRequest(BaseModel):
    """Request dla AI analizy"""
    text: str
    task: str = "analysis"
    model: Optional[str] = None


class AIResponse(BaseModel):
    """Response z AI"""
    result: str
    model: str
    task: str
    timestamp: str


class SyncRequest(BaseModel):
    """Request do synchronizacji"""
    peer_ip: str
    peer_port: int = 8766


class FileUploadResponse(BaseModel):
    """Response po uploadzie"""
    file_id: str
    name: str
    size: int
    hash: str
    encrypted: bool


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_cloud(request: Request) -> CloudEngine:
    """Pobiera CloudEngine z app.state"""
    return request.app.state.cloud


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HEALTH & STATUS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/health")
async def health(request: Request):
    """Health check"""
    cloud = get_cloud(request)
    return {
        "status": "healthy",
        "cloud": cloud.config.get("cloud_name", "ALFA_CLOUD_OFFLINE"),
        "version": cloud.config.get("version", "1.0.0"),
        "mode": cloud.config.get("mode", "offline"),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/status")
async def status(request: Request):
    """Pełny status chmury"""
    cloud = get_cloud(request)
    return cloud.status()


@router.get("/stats")
async def stats(request: Request):
    """Statystyki chmury"""
    cloud = get_cloud(request)
    return {
        "files": cloud.stats.total_files,
        "size_mb": round(cloud.stats.total_size_bytes / (1024 * 1024), 2),
        "encrypted": cloud.stats.encrypted_files,
        "synced": cloud.stats.synced_files,
        "last_backup": cloud.stats.last_backup.isoformat() if cloud.stats.last_backup else None,
        "last_sync": cloud.stats.last_sync.isoformat() if cloud.stats.last_sync else None,
        "peers_online": cloud.stats.peers_online
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FILE OPERATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/upload", response_model=FileUploadResponse, dependencies=[Depends(require_auth)])
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    encrypt: bool = Query(False, description="Szyfruj plik"),
    tags: Optional[str] = Query(None, description="Tagi rozdzielone przecinkami")
):
    """Upload pliku do chmury"""
    cloud = get_cloud(request)
    
    # Zapisz tymczasowo
    temp_path = cloud.cache_path / f"upload_{file.filename}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    content = await file.read()
    temp_path.write_bytes(content)
    
    try:
        # Upload do chmury
        tag_list = [t.strip() for t in tags.split(",")] if tags else []
        cloud_file = cloud.upload(
            str(temp_path), 
            encrypt=encrypt,
            tags=tag_list
        )
        
        return FileUploadResponse(
            file_id=cloud_file.id,
            name=cloud_file.name,
            size=cloud_file.size,
            hash=cloud_file.hash,
            encrypted=cloud_file.encrypted
        )
    finally:
        # Usuń temp
        if temp_path.exists():
            temp_path.unlink()


@router.get("/files")
async def list_files(
    request: Request,
    path: Optional[str] = None,
    include_deleted: bool = False
):
    """Lista plików w chmurze"""
    cloud = get_cloud(request)
    files = cloud.list_files(path=path, include_deleted=include_deleted)
    
    return {
        "files": [
            {
                "id": f.id,
                "name": f.name,
                "path": f.path,
                "size": f.size,
                "hash": f.hash[:16] + "...",
                "encrypted": f.encrypted,
                "created_at": f.created_at.isoformat(),
                "tags": f.tags
            }
            for f in files
        ],
        "count": len(files)
    }


@router.get("/files/{file_id}")
async def get_file_info(request: Request, file_id: str):
    """Informacje o pliku"""
    cloud = get_cloud(request)
    file_record = cloud._get_file_record(file_id)
    
    if not file_record:
        raise HTTPException(status_code=404, detail="Plik nie znaleziony")
    
    return {
        "id": file_record.id,
        "name": file_record.name,
        "path": file_record.path,
        "size": file_record.size,
        "hash": file_record.hash,
        "encrypted": file_record.encrypted,
        "created_at": file_record.created_at.isoformat(),
        "modified_at": file_record.modified_at.isoformat()
    }


@router.get("/download/{file_id}", dependencies=[Depends(require_auth)])
async def download_file(request: Request, file_id: str):
    """Download pliku"""
    cloud = get_cloud(request)
    
    try:
        # Download do temp
        temp_path = cloud.download(file_id, str(cloud.cache_path / f"download_{file_id}"))
        
        return FileResponse(
            path=str(temp_path),
            filename=temp_path.name,
            media_type="application/octet-stream"
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Plik nie znaleziony")


@router.delete("/files/{file_id}", dependencies=[Depends(require_auth)])
async def delete_file(
    request: Request, 
    file_id: str,
    permanent: bool = Query(False, description="Usuń permanentnie")
):
    """Usuwa plik"""
    cloud = get_cloud(request)
    cloud.delete(file_id, permanent=permanent)
    
    return {"status": "deleted", "file_id": file_id, "permanent": permanent}


@router.get("/search")
async def search_files(request: Request, q: str = Query(..., description="Szukana fraza")):
    """Szukaj plików"""
    cloud = get_cloud(request)
    files = cloud.search(q)
    
    return {
        "query": q,
        "results": [
            {"id": f.id, "name": f.name, "path": f.path, "size": f.size}
            for f in files
        ],
        "count": len(files)
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI OPERATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/ai/analyze", response_model=AIResponse, dependencies=[Depends(require_auth)])
async def ai_analyze(request: Request, payload: AIRequest):
    """Analiza tekstu przez lokalne AI (Ollama)"""
    cloud = get_cloud(request)
    
    # Sprawdź czy AI włączone
    ai_config = cloud.config.get("ai_local", {})
    if not ai_config.get("enabled"):
        raise HTTPException(status_code=503, detail="AI jest wyłączone")
    
    try:
        import httpx
        
        model = payload.model or ai_config.get("models", {}).get(payload.task, ai_config.get("default_model", "llama3"))
        endpoint = ai_config.get("endpoint", "http://127.0.0.1:11434")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{endpoint}/api/generate",
                json={
                    "model": model,
                    "prompt": payload.text,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
        
        return AIResponse(
            result=data.get("response", ""),
            model=model,
            task=payload.task,
            timestamp=datetime.now().isoformat()
        )
        
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama nie jest dostępne. Uruchom: ollama serve")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd AI: {str(e)}")


@router.get("/ai/models")
async def list_ai_models(request: Request):
    """Lista dostępnych modeli AI"""
    cloud = get_cloud(request)
    ai_config = cloud.config.get("ai_local", {})
    
    if not ai_config.get("enabled"):
        return {"enabled": False, "models": []}
    
    try:
        import httpx
        
        endpoint = ai_config.get("endpoint", "http://127.0.0.1:11434")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{endpoint}/api/tags")
            response.raise_for_status()
            data = response.json()
        
        models = [m.get("name") for m in data.get("models", [])]
        
        return {
            "enabled": True,
            "endpoint": endpoint,
            "default_model": ai_config.get("default_model"),
            "models": models
        }
        
    except Exception as e:
        return {"enabled": True, "error": str(e), "models": []}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYNC OPERATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/sync", dependencies=[Depends(require_auth)])
async def sync_to_peer(request: Request, payload: SyncRequest):
    """Synchronizuj z peerem w LAN"""
    cloud = get_cloud(request)
    
    await cloud.sync_to(payload.peer_ip, payload.peer_port)
    
    return {
        "status": "synced",
        "peer": f"{payload.peer_ip}:{payload.peer_port}",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/peers")
async def discover_peers(request: Request):
    """Odkryj peery w sieci LAN"""
    cloud = get_cloud(request)
    
    # TODO: Implementacja discovery
    return {
        "peers": [
            {"id": p.id, "name": p.name, "ip": p.ip, "online": p.is_online}
            for p in cloud.peers.values()
        ],
        "count": len(cloud.peers)
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKUP OPERATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/backup", dependencies=[Depends(require_auth)])
async def create_backup(request: Request):
    """Twórz backup"""
    cloud = get_cloud(request)
    
    backup_path = await cloud.backup()
    
    return {
        "status": "created",
        "path": str(backup_path),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/backups")
async def list_backups(request: Request):
    """Lista backupów"""
    cloud = get_cloud(request)
    
    backups = []
    if cloud.backup_path.exists():
        for backup_dir in sorted(cloud.backup_path.iterdir(), reverse=True):
            if backup_dir.is_dir():
                manifest_path = backup_dir / "manifest.json"
                if manifest_path.exists():
                    import json
                    manifest = json.loads(manifest_path.read_text())
                    backups.append({
                        "name": backup_dir.name,
                        "path": str(backup_dir),
                        "timestamp": manifest.get("timestamp"),
                        "files": manifest.get("stats", {}).get("total_files", 0)
                    })
    
    return {"backups": backups, "count": len(backups)}


@router.post("/restore/{backup_name}", dependencies=[Depends(require_auth)])
async def restore_backup(request: Request, backup_name: str):
    """Przywróć z backupu"""
    cloud = get_cloud(request)
    
    backup_path = cloud.backup_path / backup_name
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup nie znaleziony")
    
    await cloud.restore(str(backup_path))
    
    return {
        "status": "restored",
        "backup": backup_name,
        "timestamp": datetime.now().isoformat()
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECURITY ENDPOINTS (Cerber v7)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/security/status")
async def security_status(request: Request):
    """🛡️ Status bezpieczeństwa"""
    cloud = get_cloud(request)
    
    if not cloud.security:
        return {
            "status": "disabled",
            "message": "Security module is not enabled"
        }
    
    return cloud.security.get_status()


@router.get("/security/alerts")
async def security_alerts(request: Request, limit: int = Query(50, ge=1, le=1000)):
    """🚨 Lista alertów bezpieczeństwa"""
    cloud = get_cloud(request)
    
    if not cloud.security:
        raise HTTPException(status_code=503, detail="Security module not enabled")
    
    alerts = cloud.security.get_alerts()
    return {
        "total": len(alerts),
        "alerts": alerts[-limit:]
    }


@router.get("/security/captures")
async def security_captures(request: Request):
    """🪤 Przechwycone payloady z honeypotów"""
    cloud = get_cloud(request)
    
    if not cloud.security:
        raise HTTPException(status_code=503, detail="Security module not enabled")
    
    return {
        "captures": cloud.security.get_captures()
    }


@router.get("/security/decoys")
async def security_decoys(request: Request):
    """🪤 Status przynęt"""
    cloud = get_cloud(request)
    
    if not cloud.security:
        raise HTTPException(status_code=503, detail="Security module not enabled")
    
    return {
        "decoys": cloud.security.get_decoy_status()
    }


@router.post("/security/evidence/capture")
async def capture_evidence(request: Request):
    """📸 Zbierz dowody forensyczne"""
    cloud = get_cloud(request)
    
    if not cloud.security:
        raise HTTPException(status_code=503, detail="Security module not enabled")
    
    bundle = cloud.security.capture_evidence()
    
    return {
        "status": "captured",
        "bundle_id": bundle.id,
        "artifacts": len(bundle.artifacts),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/security/report")
async def generate_security_report(request: Request):
    """📄 Generuj raport bezpieczeństwa"""
    cloud = get_cloud(request)
    
    if not cloud.security:
        raise HTTPException(status_code=503, detail="Security module not enabled")
    
    report_path = cloud.security.export_security_report()
    
    return {
        "status": "generated",
        "path": str(report_path),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/security/honeypot/start")
async def start_honeypot(request: Request, port: int = Query(4040, ge=1024, le=65535)):
    """🪤 Uruchom honeypot na porcie"""
    cloud = get_cloud(request)
    
    if not cloud.security:
        raise HTTPException(status_code=503, detail="Security module not enabled")
    
    cloud.security.start_honeypot(port=port)
    
    return {
        "status": "started",
        "port": port,
        "timestamp": datetime.now().isoformat()
    }
