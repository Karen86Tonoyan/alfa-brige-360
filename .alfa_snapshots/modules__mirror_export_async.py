"""
ALFA_MIRROR PRO — ASYNC MONTH EXPORT
Eksport miesięczny jako background task (nie blokuje API).
Poziom: PRODUCTION-READY
"""

from __future__ import annotations

import shutil
import json
import logging
import threading
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

logger = logging.getLogger("ALFA.Mirror.Export")


# ═══════════════════════════════════════════════════════════════════════════
# KONFIGURACJA
# ═══════════════════════════════════════════════════════════════════════════

ARCHIVE_DIR = Path("storage/gemini_mirror")
EXPORT_DIR = Path("storage/gemini_exports")
MANIFEST_FILE = "export_manifest.json"


# ═══════════════════════════════════════════════════════════════════════════
# DATACLASSES & ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class ExportStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExportJob:
    """Reprezentuje zadanie eksportu."""
    job_id: str
    month: str
    status: ExportStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    zip_path: Optional[str] = None
    sessions_count: int = 0
    total_size_mb: float = 0
    error: Optional[str] = None
    progress: int = 0  # 0-100
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class ExportManager:
    """
    Zarządza eksportami miesięcznymi.
    
    Features:
    - Async/background export
    - Progress tracking
    - Job queue
    - Manifest generation
    """
    
    def __init__(self):
        self._jobs: Dict[str, ExportJob] = {}
        self._lock = threading.RLock()
        self._executor: Optional[threading.Thread] = None
        
        # Callback na progress update
        self._progress_callback: Optional[Callable[[str, int], None]] = None
        
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    def _generate_job_id(self, month: str) -> str:
        """Generuje unikalne ID zadania."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"export_{month}_{timestamp}"
    
    def _get_session_month(self, session_name: str) -> Optional[str]:
        """Wyciąga miesiąc z nazwy sesji (YYYYMMDD_... lub timestamp)."""
        try:
            # Format: YYYYMMDD_HHMMSS_UUID
            if "_" in session_name:
                date_part = session_name.split("_")[0]
                if len(date_part) == 8:
                    dt = datetime.strptime(date_part, "%Y%m%d")
                    return dt.strftime("%Y-%m")
            
            # Format: Unix timestamp
            ts = int(session_name)
            dt = datetime.fromtimestamp(ts)
            return dt.strftime("%Y-%m")
        except:
            return None
    
    def _get_sessions_for_month(self, month: str) -> List[Path]:
        """Pobiera wszystkie sesje z danego miesiąca."""
        sessions = []
        
        if not ARCHIVE_DIR.exists():
            return sessions
        
        for folder in ARCHIVE_DIR.iterdir():
            if not folder.is_dir():
                continue
            
            session_month = self._get_session_month(folder.name)
            if session_month == month:
                sessions.append(folder)
        
        return sorted(sessions)
    
    def _create_manifest(self, sessions: List[Path], month: str) -> dict:
        """Tworzy manifest eksportu."""
        manifest = {
            "month": month,
            "created_at": datetime.now().isoformat(),
            "sessions_count": len(sessions),
            "sessions": [],
            "total_files": 0,
            "total_size_bytes": 0
        }
        
        for session in sessions:
            session_info = {
                "name": session.name,
                "files": [],
                "size_bytes": 0
            }
            
            for f in session.iterdir():
                if f.is_file():
                    size = f.stat().st_size
                    session_info["files"].append({
                        "name": f.name,
                        "size": size,
                        "type": f.suffix.lstrip(".")
                    })
                    session_info["size_bytes"] += size
                    manifest["total_files"] += 1
                    manifest["total_size_bytes"] += size
            
            manifest["sessions"].append(session_info)
        
        return manifest
    
    def _do_export(self, job: ExportJob) -> None:
        """Wykonuje eksport (w osobnym wątku)."""
        try:
            with self._lock:
                job.status = ExportStatus.IN_PROGRESS
                job.started_at = datetime.now().isoformat()
            
            logger.info(f"Starting export for {job.month}")
            
            # Pobierz sesje
            sessions = self._get_sessions_for_month(job.month)
            
            if not sessions:
                raise ValueError(f"No sessions found for month: {job.month}")
            
            job.sessions_count = len(sessions)
            
            # Stwórz folder tymczasowy
            tmp_dir = EXPORT_DIR / f"tmp_{job.job_id}"
            tmp_dir.mkdir(exist_ok=True)
            
            total_size = 0
            
            # Kopiuj sesje
            for i, session in enumerate(sessions):
                target = tmp_dir / session.name
                
                try:
                    shutil.copytree(session, target)
                    total_size += sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
                except Exception as e:
                    logger.warning(f"Failed to copy {session.name}: {e}")
                
                # Update progress
                progress = int((i + 1) / len(sessions) * 80)  # 0-80% for copying
                job.progress = progress
                
                if self._progress_callback:
                    self._progress_callback(job.job_id, progress)
            
            # Stwórz manifest
            manifest = self._create_manifest(sessions, job.month)
            manifest_path = tmp_dir / MANIFEST_FILE
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf8"
            )
            
            job.progress = 85
            
            # Stwórz ZIP
            zip_name = f"ALFA_MIRROR_{job.month}"
            zip_path = EXPORT_DIR / f"{zip_name}.zip"
            
            # Usuń stary ZIP jeśli istnieje
            if zip_path.exists():
                zip_path.unlink()
            
            logger.info(f"Creating ZIP: {zip_path}")
            shutil.make_archive(
                str(EXPORT_DIR / zip_name),
                "zip",
                tmp_dir
            )
            
            job.progress = 95
            
            # Cleanup tmp
            shutil.rmtree(tmp_dir, ignore_errors=True)
            
            # Finalizacja
            job.zip_path = str(zip_path)
            job.total_size_mb = round(zip_path.stat().st_size / (1024 * 1024), 2)
            job.status = ExportStatus.COMPLETED
            job.completed_at = datetime.now().isoformat()
            job.progress = 100
            
            logger.info(f"✅ Export completed: {zip_path} ({job.total_size_mb} MB)")
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            job.status = ExportStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now().isoformat()
            
            # Cleanup on error
            tmp_dir = EXPORT_DIR / f"tmp_{job.job_id}"
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
    
    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════
    
    def start_export(self, month: str) -> ExportJob:
        """
        Rozpoczyna eksport miesięczny (async).
        
        Args:
            month: Miesiąc w formacie 'YYYY-MM'
            
        Returns:
            ExportJob z job_id do śledzenia
            
        Raises:
            ValueError: Gdy eksport dla tego miesiąca już trwa
        """
        # Walidacja formatu
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            raise ValueError(f"Invalid month format: {month}. Use YYYY-MM")
        
        # Sprawdź czy już nie ma aktywnego eksportu
        for job in self._jobs.values():
            if job.month == month and job.status in [ExportStatus.PENDING, ExportStatus.IN_PROGRESS]:
                raise ValueError(f"Export for {month} already in progress: {job.job_id}")
        
        # Stwórz job
        job_id = self._generate_job_id(month)
        job = ExportJob(
            job_id=job_id,
            month=month,
            status=ExportStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        with self._lock:
            self._jobs[job_id] = job
        
        # Uruchom w tle
        thread = threading.Thread(
            target=self._do_export,
            args=(job,),
            daemon=True
        )
        thread.start()
        
        logger.info(f"Export started: {job_id}")
        return job
    
    def get_job(self, job_id: str) -> Optional[ExportJob]:
        """Pobiera status zadania."""
        return self._jobs.get(job_id)
    
    def get_all_jobs(self) -> List[ExportJob]:
        """Pobiera wszystkie zadania."""
        return list(self._jobs.values())
    
    def get_active_jobs(self) -> List[ExportJob]:
        """Pobiera aktywne zadania."""
        return [
            j for j in self._jobs.values()
            if j.status in [ExportStatus.PENDING, ExportStatus.IN_PROGRESS]
        ]
    
    def get_completed_exports(self) -> List[Path]:
        """Pobiera listę gotowych eksportów."""
        exports = []
        for f in EXPORT_DIR.glob("ALFA_MIRROR_*.zip"):
            exports.append(f)
        return sorted(exports, reverse=True)
    
    def delete_export(self, month: str) -> bool:
        """Usuwa eksport dla miesiąca."""
        zip_path = EXPORT_DIR / f"ALFA_MIRROR_{month}.zip"
        if zip_path.exists():
            zip_path.unlink()
            logger.info(f"Deleted export: {zip_path}")
            return True
        return False
    
    def set_progress_callback(self, callback: Callable[[str, int], None]) -> None:
        """Ustawia callback na aktualizację progress."""
        self._progress_callback = callback


# ═══════════════════════════════════════════════════════════════════════════
# SYNCHRONOUS EXPORT (dla kompatybilności)
# ═══════════════════════════════════════════════════════════════════════════

def export_month_sync(month: str) -> Path:
    """
    Synchroniczny eksport miesiąca (blokujący).
    Dla kompatybilności z poprzednią wersją.
    
    Args:
        month: Format 'YYYY-MM'
        
    Returns:
        Path do ZIP
    """
    manager = ExportManager()
    job = manager.start_export(month)
    
    # Czekaj na zakończenie
    while job.status in [ExportStatus.PENDING, ExportStatus.IN_PROGRESS]:
        import time
        time.sleep(0.5)
    
    if job.status == ExportStatus.FAILED:
        raise RuntimeError(f"Export failed: {job.error}")
    
    return Path(job.zip_path)


# ═══════════════════════════════════════════════════════════════════════════
# FASTAPI INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

_export_manager: Optional[ExportManager] = None


def get_export_manager() -> ExportManager:
    """Pobiera globalną instancję ExportManager."""
    global _export_manager
    if _export_manager is None:
        _export_manager = ExportManager()
    return _export_manager


# ═══════════════════════════════════════════════════════════════════════════
# ASYNC WRAPPER (dla FastAPI)
# ═══════════════════════════════════════════════════════════════════════════

async def async_start_export(month: str) -> ExportJob:
    """Async wrapper dla start_export."""
    manager = get_export_manager()
    return manager.start_export(month)


async def async_get_job_status(job_id: str) -> Optional[dict]:
    """Async wrapper dla get_job."""
    manager = get_export_manager()
    job = manager.get_job(job_id)
    return job.to_dict() if job else None


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import time
    
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n" + "═" * 50)
    print("📦 ALFA ASYNC EXPORT TEST")
    print("═" * 50)
    
    month = sys.argv[1] if len(sys.argv) > 1 else "2025-01"
    
    print(f"\n📅 Exporting month: {month}")
    
    manager = ExportManager()
    
    # Progress callback
    def on_progress(job_id: str, progress: int):
        print(f"   Progress: {progress}%")
    
    manager.set_progress_callback(on_progress)
    
    # Start export
    try:
        job = manager.start_export(month)
        print(f"   Job ID: {job.job_id}")
        print(f"   Status: {job.status.value}")
        
        # Czekaj na zakończenie
        while job.status in [ExportStatus.PENDING, ExportStatus.IN_PROGRESS]:
            time.sleep(1)
            job = manager.get_job(job.job_id)
            print(f"   Status: {job.status.value} ({job.progress}%)")
        
        if job.status == ExportStatus.COMPLETED:
            print(f"\n✅ Export completed!")
            print(f"   ZIP: {job.zip_path}")
            print(f"   Size: {job.total_size_mb} MB")
            print(f"   Sessions: {job.sessions_count}")
        else:
            print(f"\n❌ Export failed: {job.error}")
            
    except ValueError as e:
        print(f"❌ Error: {e}")
    
    print("\n✅ Test complete!")
