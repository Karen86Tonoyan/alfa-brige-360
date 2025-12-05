"""
ALFA MIRROR — ZIP EXPORT
Eksport sesji jako ZIP.
"""

from __future__ import annotations

import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ALFA.Mirror.Zip")

ARCHIVE_DIR = Path("storage/gemini_mirror")
EXPORT_DIR = Path("storage/gemini_exports")


def export_zip(session: str) -> Path:
    """
    Eksportuje pojedynczą sesję jako ZIP.
    
    Args:
        session: ID sesji
        
    Returns:
        Ścieżka do pliku ZIP
        
    Raises:
        FileNotFoundError: Jeśli sesja nie istnieje
    """
    src = ARCHIVE_DIR / session
    
    if not src.exists():
        raise FileNotFoundError(f"Session not found: {session}")
    
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    zip_base = EXPORT_DIR / f"session_{session}"
    zip_path = Path(shutil.make_archive(str(zip_base), "zip", src))
    
    logger.info(f"Exported session: {session} -> {zip_path}")
    return zip_path


def export_sessions(sessions: list) -> Path:
    """
    Eksportuje wiele sesji jako jeden ZIP.
    
    Args:
        sessions: Lista ID sesji
        
    Returns:
        Ścieżka do pliku ZIP
    """
    import time
    
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create temp directory
    timestamp = int(time.time())
    tmp_dir = EXPORT_DIR / f"multi_{timestamp}"
    tmp_dir.mkdir(exist_ok=True)
    
    for session in sessions:
        src = ARCHIVE_DIR / session
        if src.exists():
            dst = tmp_dir / session
            shutil.copytree(src, dst)
    
    # Create ZIP
    zip_base = EXPORT_DIR / f"multi_{timestamp}"
    zip_path = Path(shutil.make_archive(str(zip_base), "zip", tmp_dir))
    
    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)
    
    logger.info(f"Exported {len(sessions)} sessions -> {zip_path}")
    return zip_path


def cleanup_exports(max_age_hours: int = 24) -> int:
    """
    Usuwa stare eksporty.
    
    Args:
        max_age_hours: Maksymalny wiek w godzinach
        
    Returns:
        Liczba usuniętych plików
    """
    import time
    
    if not EXPORT_DIR.exists():
        return 0
    
    max_age_seconds = max_age_hours * 3600
    now = time.time()
    removed = 0
    
    for f in EXPORT_DIR.glob("*.zip"):
        if now - f.stat().st_mtime > max_age_seconds:
            f.unlink()
            removed += 1
    
    if removed:
        logger.info(f"Cleaned up {removed} old exports")
    
    return removed
