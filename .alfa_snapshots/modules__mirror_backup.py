"""
ALFA MIRROR — BACKUP
Auto-backup na zewnętrzny dysk (T7).
"""

from __future__ import annotations

import shutil
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger("ALFA.Mirror.Backup")

SOURCE_DIR = Path("storage/gemini_mirror")
DEFAULT_TARGET = Path("X:/ALFA_MIRROR_BACKUP")  # T7 lub inny dysk


class MirrorBackup:
    """
    System backupu archiwum na zewnętrzny dysk.
    """
    
    def __init__(
        self,
        source: Optional[Path] = None,
        target: Optional[Path] = None,
        interval_seconds: int = 600,  # 10 minut
    ):
        self.source = source or SOURCE_DIR
        self.target = target or DEFAULT_TARGET
        self.interval = interval_seconds
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_backup: Optional[float] = None
        self._on_complete: Optional[Callable] = None
    
    def sync(self) -> dict:
        """
        Wykonuje synchronizację source → target.
        
        Returns:
            Dict z wynikiem
        """
        if not self.source.exists():
            return {"status": "error", "message": "Source does not exist"}
        
        if not self.target.parent.exists():
            return {"status": "error", "message": "Target drive not available"}
        
        try:
            self.target.mkdir(parents=True, exist_ok=True)
            
            copied = 0
            skipped = 0
            
            for item in self.source.iterdir():
                target_item = self.target / item.name
                
                if item.is_dir():
                    if not target_item.exists():
                        shutil.copytree(item, target_item)
                        copied += 1
                    else:
                        # Sync individual files in directory
                        for f in item.iterdir():
                            tf = target_item / f.name
                            if not tf.exists() or f.stat().st_mtime > tf.stat().st_mtime:
                                shutil.copy2(f, tf)
                                copied += 1
                            else:
                                skipped += 1
                else:
                    if not target_item.exists() or item.stat().st_mtime > target_item.stat().st_mtime:
                        shutil.copy2(item, target_item)
                        copied += 1
                    else:
                        skipped += 1
            
            self._last_backup = time.time()
            
            result = {
                "status": "ok",
                "copied": copied,
                "skipped": skipped,
                "target": str(self.target),
            }
            
            logger.info(f"Backup complete: {copied} copied, {skipped} skipped")
            
            if self._on_complete:
                self._on_complete(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def start_auto(self, on_complete: Optional[Callable] = None) -> None:
        """
        Uruchamia automatyczny backup w tle.
        
        Args:
            on_complete: Callback po każdym backupie
        """
        if self._running:
            return
        
        self._running = True
        self._on_complete = on_complete
        self._thread = threading.Thread(target=self._backup_loop, daemon=True)
        self._thread.start()
        
        logger.info(f"Auto-backup started (interval: {self.interval}s)")
    
    def stop_auto(self) -> None:
        """Zatrzymuje automatyczny backup."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Auto-backup stopped")
    
    def _backup_loop(self) -> None:
        """Główna pętla backupu."""
        while self._running:
            try:
                self.sync()
            except Exception as e:
                logger.error(f"Backup loop error: {e}")
            
            # Wait for next interval
            for _ in range(self.interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def status(self) -> dict:
        """Status backupu."""
        return {
            "running": self._running,
            "source": str(self.source),
            "target": str(self.target),
            "interval_seconds": self.interval,
            "last_backup": self._last_backup,
            "source_exists": self.source.exists(),
            "target_available": self.target.parent.exists() if self.target else False,
        }


# Convenience functions

def auto_backup(
    target: Optional[str] = None,
    interval: int = 600
) -> MirrorBackup:
    """
    Uruchamia auto-backup.
    
    Args:
        target: Ścieżka docelowa (opcjonalnie)
        interval: Interwał w sekundach
        
    Returns:
        MirrorBackup instance
    """
    backup = MirrorBackup(
        target=Path(target) if target else None,
        interval_seconds=interval,
    )
    backup.start_auto()
    return backup


def backup_now(target: Optional[str] = None) -> dict:
    """
    Wykonuje natychmiastowy backup.
    
    Returns:
        Wynik backupu
    """
    backup = MirrorBackup(
        target=Path(target) if target else None,
    )
    return backup.sync()


def check_target_available(target: Optional[str] = None) -> bool:
    """
    Sprawdza czy dysk docelowy jest dostępny.
    """
    path = Path(target) if target else DEFAULT_TARGET
    return path.parent.exists()
