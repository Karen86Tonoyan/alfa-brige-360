"""
ALFA MIRROR ENGINE v1.0
Pełna archiwizacja odpowiedzi Gemini - tekst, obrazy, wideo, audio, pliki.
"""

from __future__ import annotations

import os
import json
import time
import base64
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("ALFA.Mirror")

ARCHIVE_DIR = Path("storage/gemini_mirror")
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def _save_file(folder: Path, filename: str, data: bytes) -> str:
    """Zapisuje plik binarny."""
    path = folder / filename
    with open(path, "wb") as f:
        f.write(data)
    logger.debug(f"Saved: {path}")
    return str(path)


def _generate_thumbnail(video_path: Path, thumb_path: Path) -> bool:
    """Generuje miniaturę z pierwszej klatki wideo."""
    try:
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        ok, frame = cap.read()
        if ok and frame is not None:
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(thumb_path), frame)
            cap.release()
            return True
        cap.release()
    except ImportError:
        logger.debug("OpenCV not available for thumbnails")
    except Exception as e:
        logger.warning(f"Thumbnail generation failed: {e}")
    return False


def mirror_gemini_response(payload: dict) -> str:
    """
    Zapisuje CAŁĄ odpowiedź Gemini:
    - raw.json (oryginalny dump)
    - hash.sha256 (integralność)
    - text_*.md (teksty)
    - image_*.png/jpg (obrazy)
    - video_*.mp4/webm (wideo + thumbnail)
    - audio_*.ogg/wav (audio)
    - file_*.pdf/zip/... (inne pliki)
    - function_*.json (function calls)
    
    Args:
        payload: Surowa odpowiedź JSON z Gemini API
        
    Returns:
        Ścieżka do folderu sesji
    """
    timestamp = int(time.time())
    folder = ARCHIVE_DIR / f"{timestamp}"
    folder.mkdir(parents=True, exist_ok=True)
    
    # RAW JSON
    raw_json = json.dumps(payload, indent=4, ensure_ascii=False)
    (folder / "raw.json").write_text(raw_json, encoding="utf8")
    
    # HASH SHA256
    hash_value = hashlib.sha256(raw_json.encode()).hexdigest()
    (folder / "hash.sha256").write_text(hash_value, encoding="utf8")
    
    # Metadata
    meta = {
        "timestamp": timestamp,
        "hash": hash_value,
        "files": [],
    }
    
    candidates = payload.get("candidates", [])
    if not candidates:
        (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf8")
        return str(folder)
    
    parts = candidates[0].get("content", {}).get("parts", [])
    
    for idx, part in enumerate(parts):
        
        # ============ TEXT ============
        if "text" in part:
            text_file = folder / f"text_{idx}.md"
            text_file.write_text(part["text"], encoding="utf8")
            meta["files"].append({"type": "text", "file": text_file.name})
        
        # ============ IMAGE (inlineData) ============
        if (
            "inlineData" in part
            and part["inlineData"].get("mimeType", "").startswith("image/")
        ):
            mime = part["inlineData"]["mimeType"]
            ext = mime.split("/")[-1].replace("jpeg", "jpg")
            data = base64.b64decode(part["inlineData"]["data"])
            filename = f"image_{idx}.{ext}"
            _save_file(folder, filename, data)
            meta["files"].append({"type": "image", "file": filename, "mime": mime})
        
        # ============ VIDEO (fileData) ============
        if (
            "fileData" in part
            and part["fileData"].get("mimeType", "").startswith("video/")
        ):
            mime = part["fileData"]["mimeType"]
            ext = mime.split("/")[-1]
            file_data = part["fileData"].get("data", "")
            
            if file_data:
                data = base64.b64decode(file_data)
                filename = f"video_{idx}.{ext}"
                video_path = folder / filename
                _save_file(folder, filename, data)
                
                # Thumbnail
                thumb_path = folder / f"video_{idx}_thumb.jpg"
                _generate_thumbnail(video_path, thumb_path)
                
                meta["files"].append({"type": "video", "file": filename, "mime": mime})
        
        # ============ AUDIO (fileData) ============
        if (
            "fileData" in part
            and part["fileData"].get("mimeType", "").startswith("audio/")
        ):
            mime = part["fileData"]["mimeType"]
            ext = mime.split("/")[-1]
            file_data = part["fileData"].get("data", "")
            
            if file_data:
                data = base64.b64decode(file_data)
                filename = f"audio_{idx}.{ext}"
                _save_file(folder, filename, data)
                meta["files"].append({"type": "audio", "file": filename, "mime": mime})
        
        # ============ OTHER FILES (PDF, ZIP, etc.) ============
        if (
            "fileData" in part
            and not part["fileData"].get("mimeType", "").startswith(("audio/", "video/", "image/"))
        ):
            mime = part["fileData"]["mimeType"]
            ext = mime.split("/")[-1] or "bin"
            file_data = part["fileData"].get("data", "")
            
            if file_data:
                data = base64.b64decode(file_data)
                filename = f"file_{idx}.{ext}"
                _save_file(folder, filename, data)
                meta["files"].append({"type": "file", "file": filename, "mime": mime})
        
        # ============ FUNCTION CALL ============
        if "functionCall" in part:
            func_file = folder / f"function_{idx}.json"
            func_file.write_text(
                json.dumps(part["functionCall"], indent=4, ensure_ascii=False),
                encoding="utf8",
            )
            meta["files"].append({"type": "function", "file": func_file.name})
    
    # Save metadata
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf8")
    
    logger.info(f"Mirrored session: {folder.name} ({len(meta['files'])} files)")
    return str(folder)


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Pobiera dane sesji."""
    folder = ARCHIVE_DIR / session_id
    if not folder.exists():
        return None
    
    meta_file = folder / "meta.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text(encoding="utf8"))
    
    # Fallback - lista plików
    return {
        "session": session_id,
        "files": [f.name for f in folder.iterdir()],
    }


def list_sessions(limit: int = 100) -> list:
    """Lista ostatnich sesji."""
    sessions = []
    
    for folder in sorted(ARCHIVE_DIR.iterdir(), reverse=True):
        if folder.is_dir():
            sessions.append({
                "id": folder.name,
                "path": str(folder),
                "files": len(list(folder.iterdir())),
            })
            if len(sessions) >= limit:
                break
    
    return sessions


def get_archive_stats() -> Dict[str, Any]:
    """Statystyki archiwum."""
    if not ARCHIVE_DIR.exists():
        return {"sessions": 0, "total_files": 0, "size_bytes": 0}
    
    sessions = 0
    total_files = 0
    size_bytes = 0
    
    for folder in ARCHIVE_DIR.iterdir():
        if folder.is_dir():
            sessions += 1
            for f in folder.iterdir():
                total_files += 1
                size_bytes += f.stat().st_size
    
    return {
        "sessions": sessions,
        "total_files": total_files,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
    }
