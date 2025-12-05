"""
ALFA MIRROR — SEARCH
Wyszukiwanie w archiwum.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("ALFA.Mirror.Search")

ARCHIVE_DIR = Path("storage/gemini_mirror")


def search_mirror(query: str, max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Wyszukuje w archiwum Gemini.
    
    Przeszukuje:
    - raw.json
    - text_*.md
    - meta.json
    
    Args:
        query: Fraza do wyszukania
        max_results: Maksymalna liczba wyników
        
    Returns:
        Lista pasujących sesji
    """
    if not ARCHIVE_DIR.exists():
        return []
    
    results = []
    query_lower = query.lower()
    
    for folder in sorted(ARCHIVE_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        
        matched = False
        match_context = ""
        
        # Search in raw.json
        raw_file = folder / "raw.json"
        if raw_file.exists():
            try:
                content = raw_file.read_text(encoding="utf8")
                if query_lower in content.lower():
                    matched = True
                    # Extract context
                    idx = content.lower().find(query_lower)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query) + 50)
                    match_context = "..." + content[start:end] + "..."
            except Exception:
                pass
        
        # Search in text files
        if not matched:
            for text_file in folder.glob("text_*.md"):
                try:
                    content = text_file.read_text(encoding="utf8")
                    if query_lower in content.lower():
                        matched = True
                        idx = content.lower().find(query_lower)
                        start = max(0, idx - 50)
                        end = min(len(content), idx + len(query) + 50)
                        match_context = "..." + content[start:end] + "..."
                        break
                except Exception:
                    pass
        
        if matched:
            results.append({
                "session": folder.name,
                "path": str(folder),
                "context": match_context[:200] if match_context else "",
            })
            
            if len(results) >= max_results:
                break
    
    logger.info(f"Search '{query}': {len(results)} results")
    return results


def search_by_type(file_type: str, max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Wyszukuje sesje zawierające określony typ plików.
    
    Args:
        file_type: image, video, audio, text, function
        max_results: Maksymalna liczba wyników
    """
    if not ARCHIVE_DIR.exists():
        return []
    
    results = []
    
    patterns = {
        "image": ["image_*.png", "image_*.jpg", "image_*.jpeg", "image_*.webp"],
        "video": ["video_*.mp4", "video_*.webm"],
        "audio": ["audio_*.ogg", "audio_*.wav", "audio_*.mp3"],
        "text": ["text_*.md"],
        "function": ["function_*.json"],
        "file": ["file_*.*"],
    }
    
    search_patterns = patterns.get(file_type, [f"{file_type}_*.*"])
    
    for folder in sorted(ARCHIVE_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        
        files_found = []
        for pattern in search_patterns:
            files_found.extend(folder.glob(pattern))
        
        if files_found:
            results.append({
                "session": folder.name,
                "path": str(folder),
                "files": [f.name for f in files_found],
                "count": len(files_found),
            })
            
            if len(results) >= max_results:
                break
    
    return results


def search_by_date(year: int, month: int, day: int = 0) -> List[Dict[str, Any]]:
    """
    Wyszukuje sesje z określonej daty.
    
    Args:
        year: Rok (np. 2025)
        month: Miesiąc (1-12)
        day: Dzień (0 = cały miesiąc)
    """
    from datetime import datetime
    
    if not ARCHIVE_DIR.exists():
        return []
    
    results = []
    
    for folder in sorted(ARCHIVE_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        
        try:
            ts = int(folder.name)
            dt = datetime.fromtimestamp(ts)
            
            if dt.year == year and dt.month == month:
                if day == 0 or dt.day == day:
                    results.append({
                        "session": folder.name,
                        "date": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "path": str(folder),
                    })
        except ValueError:
            continue
    
    return results
