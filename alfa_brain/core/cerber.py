# ═══════════════════════════════════════════════════════════════════════════
# ALFA_BRAIN v2.0 — CERBER
# ═══════════════════════════════════════════════════════════════════════════
"""
Security Guardian: Fingerprinting, integrity verification, incident logging.

Usage:
    from core.cerber import Cerber, get_cerber
    
    cerber = get_cerber()
    cerber.scan_directory(".")
    cerber.verify_all()
"""

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("alfa.cerber")

WATCH_EXT = (".py", ".json", ".yaml", ".yml")
SNAPSHOT_DIR = ".snapshots"
DB_FILE = "cerber.db"
IGNORE_FILES = {"cerber.py", "cerber.db"}

# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

class IncidentLevel(Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    ROLLBACK = "ROLLBACK"

@dataclass
class FileInfo:
    path: str
    hash: str
    snapshot_path: Optional[str] = None
    violations: int = 0

# ═══════════════════════════════════════════════════════════════════════════
# CERBER
# ═══════════════════════════════════════════════════════════════════════════

class Cerber:
    """Security Guardian for ALFA system."""
    
    _instance: Optional["Cerber"] = None
    _lock = threading.Lock()
    
    def __new__(cls, root_dir: str = ".") -> "Cerber":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, root_dir: str = "."):
        if getattr(self, '_initialized', False):
            return
        
        self.root_dir = Path(root_dir).resolve()
        self.snapshot_dir = self.root_dir / SNAPSHOT_DIR
        self.db_path = self.root_dir / DB_FILE
        
        self._tracked: Dict[str, FileInfo] = {}
        self._running = False
        self._worker: Optional[threading.Thread] = None
        self._stats = {"files_tracked": 0, "snapshots": 0, "rollbacks": 0, "violations": 0}
        
        self._init_db()
        self._initialized = True
        LOG.info(f"[Cerber] Initialized at {self.root_dir}")
    
    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                source TEXT DEFAULT ''
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS fingerprints (
                path TEXT PRIMARY KEY,
                hash TEXT NOT NULL,
                snapshot_path TEXT,
                violations INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    
    def log_incident(self, level: IncidentLevel, message: str, source: str = ""):
        """Log security incident"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute(
            "INSERT INTO incidents (timestamp, level, message, source) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), level.value, message, source)
        )
        conn.commit()
        conn.close()
        LOG.log(getattr(logging, level.value, logging.INFO), f"[{level.value}] {message}")
    
    def file_hash(self, path: str) -> str:
        """Calculate SHA256 hash"""
        h = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            LOG.error(f"Hash error: {e}")
            return ""
    
    def create_snapshot(self, path: str) -> Optional[str]:
        """Create backup snapshot"""
        try:
            self.snapshot_dir.mkdir(exist_ok=True)
            snap_name = str(Path(path).relative_to(self.root_dir)).replace(os.sep, "__")
            snap_path = self.snapshot_dir / snap_name
            shutil.copy2(path, snap_path)
            self._stats["snapshots"] += 1
            return str(snap_path)
        except Exception as e:
            LOG.error(f"Snapshot error: {e}")
            return None
    
    def restore_snapshot(self, path: str) -> bool:
        """Restore file from snapshot"""
        info = self._tracked.get(path)
        if not info or not info.snapshot_path or not os.path.exists(info.snapshot_path):
            return False
        
        try:
            shutil.copy2(info.snapshot_path, path)
            self._stats["rollbacks"] += 1
            self.log_incident(IncidentLevel.ROLLBACK, f"Restored {path}", "restore")
            return True
        except Exception as e:
            LOG.error(f"Restore error: {e}")
            return False
    
    def track_file(self, path: str) -> Optional[FileInfo]:
        """Start tracking a file"""
        path = str(Path(path).resolve())
        
        if os.path.basename(path) in IGNORE_FILES:
            return None
        if not os.path.exists(path):
            return None
        
        file_hash = self.file_hash(path)
        snapshot = self.create_snapshot(path)
        
        info = FileInfo(path=path, hash=file_hash, snapshot_path=snapshot)
        self._tracked[path] = info
        self._stats["files_tracked"] += 1
        
        return info
    
    def verify_file(self, path: str) -> bool:
        """Verify file integrity"""
        path = str(Path(path).resolve())
        
        if path not in self._tracked:
            self.track_file(path)
            return True
        
        info = self._tracked[path]
        current = self.file_hash(path)
        
        if current != info.hash:
            LOG.warning(f"File changed: {path}")
            info.violations += 1
            self._stats["violations"] += 1
            
            # Update hash
            info.hash = current
            self._tracked[path] = info
            
            return False
        
        return True
    
    def scan_directory(self, directory: str = ".") -> List[str]:
        """Scan directory for files to track"""
        directory = Path(directory).resolve()
        tracked = []
        
        for ext in WATCH_EXT:
            for path in directory.rglob(f"*{ext}"):
                if path.name in IGNORE_FILES:
                    continue
                if SNAPSHOT_DIR in str(path):
                    continue
                
                self.track_file(str(path))
                tracked.append(str(path))
        
        return tracked
    
    def verify_all(self) -> Dict[str, bool]:
        """Verify all tracked files"""
        return {path: self.verify_file(path) for path in self._tracked}
    
    def start(self):
        """Start background monitoring"""
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="Cerber")
        self._worker.start()
    
    def stop(self):
        """Stop monitoring"""
        self._running = False
        if self._worker:
            self._worker.join(timeout=5.0)
        LOG.info(f"[Cerber] Stopped. Stats: {self._stats}")
    
    def _worker_loop(self):
        LOG.info("[Cerber] Guardian active")
        while self._running:
            for path in list(self._tracked.keys()):
                if os.path.exists(path):
                    self.verify_file(path)
            time.sleep(5)
    
    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "root_dir": str(self.root_dir),
            "tracked_files": len(self._tracked),
            "stats": self._stats.copy()
        }
    
    def incidents(self, limit: int = 20) -> List[Dict]:
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("SELECT id, timestamp, level, message, source FROM incidents ORDER BY id DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "timestamp": r[1], "level": r[2], "message": r[3], "source": r[4]} for r in rows]

# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE
# ═══════════════════════════════════════════════════════════════════════════

def get_cerber(root_dir: str = ".") -> Cerber:
    return Cerber(root_dir)

def verify(path: str) -> bool:
    return get_cerber().verify_file(path)

__all__ = ["Cerber", "IncidentLevel", "FileInfo", "get_cerber", "verify"]
