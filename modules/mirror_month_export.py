"""
ALFA MIRROR — MONTH EXPORT
Eksport całego miesiąca.
"""

from __future__ import annotations

import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger("ALFA.Mirror.MonthExport")

ARCHIVE_DIR = Path("storage/gemini_mirror")
EXPORT_DIR = Path("storage/gemini_exports")


def _session_to_datetime(session_name: str) -> datetime:
    """Konwertuje nazwę sesji (timestamp) na datetime."""
    ts = int(session_name)
    return datetime.fromtimestamp(ts)


def _session_month(session_name: str) -> str:
    """Zwraca miesiąc sesji jako 'YYYY-MM'."""
    dt = _session_to_datetime(session_name)
    return dt.strftime("%Y-%m")


def get_sessions_by_month(month: str) -> List[str]:
    """
    Pobiera sesje z danego miesiąca.
    
    Args:
        month: Format 'YYYY-MM' (np. '2025-12')
        
    Returns:
        Lista ID sesji
    """
    if not ARCHIVE_DIR.exists():
        return []
    
    sessions = []
    
    for folder in ARCHIVE_DIR.iterdir():
        if not folder.is_dir():
            continue
        
        try:
            if _session_month(folder.name) == month:
                sessions.append(folder.name)
        except ValueError:
            continue
    
    return sorted(sessions)


def get_available_months() -> List[Tuple[str, int]]:
    """
    Lista dostępnych miesięcy z liczbą sesji.
    
    Returns:
        Lista (month, count)
    """
    if not ARCHIVE_DIR.exists():
        return []
    
    months = {}
    
    for folder in ARCHIVE_DIR.iterdir():
        if not folder.is_dir():
            continue
        
        try:
            month = _session_month(folder.name)
            months[month] = months.get(month, 0) + 1
        except ValueError:
            continue
    
    return sorted(months.items(), reverse=True)


def export_month(month: str) -> Path:
    """
    Eksportuje cały miesiąc jako ZIP.
    
    Args:
        month: Format 'YYYY-MM'
        
    Returns:
        Ścieżka do pliku ZIP
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create temp directory
    tmp_dir = EXPORT_DIR / f"month_{month}"
    tmp_dir.mkdir(exist_ok=True)
    
    sessions = get_sessions_by_month(month)
    
    for session in sessions:
        src = ARCHIVE_DIR / session
        if src.exists():
            dst = tmp_dir / session
            if not dst.exists():
                shutil.copytree(src, dst)
    
    # Create ZIP
    zip_path = EXPORT_DIR / f"gemini_{month}.zip"
    shutil.make_archive(str(zip_path).replace(".zip", ""), "zip", tmp_dir)
    
    # Cleanup temp
    shutil.rmtree(tmp_dir, ignore_errors=True)
    
    logger.info(f"Exported month {month}: {len(sessions)} sessions -> {zip_path}")
    return zip_path


def export_date_range(start_date: str, end_date: str) -> Path:
    """
    Eksportuje zakres dat.
    
    Args:
        start_date: 'YYYY-MM-DD'
        end_date: 'YYYY-MM-DD'
        
    Returns:
        Ścieżka do ZIP
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    tmp_dir = EXPORT_DIR / f"range_{start_date}_{end_date}"
    tmp_dir.mkdir(exist_ok=True)
    
    count = 0
    
    for folder in ARCHIVE_DIR.iterdir():
        if not folder.is_dir():
            continue
        
        try:
            dt = _session_to_datetime(folder.name)
            if start <= dt <= end:
                dst = tmp_dir / folder.name
                if not dst.exists():
                    shutil.copytree(folder, dst)
                    count += 1
        except ValueError:
            continue
    
    # Create ZIP
    zip_name = f"gemini_{start_date}_to_{end_date}"
    zip_path = EXPORT_DIR / f"{zip_name}.zip"
    shutil.make_archive(str(zip_path).replace(".zip", ""), "zip", tmp_dir)
    
    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)
    
    logger.info(f"Exported range {start_date} to {end_date}: {count} sessions")
    return zip_path
