# ═══════════════════════════════════════════════════════════════════════════
# ALFA CORE v2.0 — CERBER — Security Guardian
# ═══════════════════════════════════════════════════════════════════════════
"""
CERBER: Wielowarstwowy system bezpieczeństwa ALFA.

Funkcje:
- File integrity monitoring (fingerprinting)
- Automatic snapshot & rollback
- Content sanitization (FORBIDDEN patterns)
- IP whitelist guard
- Incident logging z SQLite
- Integration z EventBus

Based on: alfa_guard.py v1.0
Upgraded: CERBER v2.0 with EventBus, threading, async support

Usage:
    from core.cerber import Cerber, get_cerber
    
    cerber = get_cerber()
    cerber.start()  # Background monitoring
    cerber.verify("/path/to/file.py")
    cerber.stop()
"""

import os
import hashlib
import shutil
import sqlite3
import threading
import time
import logging
import socket
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Any

# Import EventBus (lazy to avoid circular)
try:
    from .event_bus import EventBus, Priority, get_bus, publish
except ImportError:
    EventBus = None
    Priority = None
    get_bus = lambda: None
    publish = lambda *a, **k: None

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LOG = logging.getLogger("alfa.cerber")

# File monitoring
WATCH_EXTENSIONS = (".py", ".json", ".yaml", ".yml", ".toml", ".md")
SNAPSHOT_DIR = ".alfa_snapshots"
DB_FILE = "cerber.db"
SCAN_INTERVAL = 1.0  # seconds

# Self-protection
IGNORE_FILES = {"cerber.py", "alfa_guard.py", "cerber.db"}

# Content analysis
FORBIDDEN_PATTERNS = [
    r"<{7}",       # Git conflict markers
    r">{7}",
    r"={7}",
    r"(?i)hallucin",
    r"(?i)placeholder",
    r"(?i)todo\s*:",  # Left-over TODOs
    r"(?i)fixme",
    r"(?i)xxx",
    r"(?i)hack\b",
]

MAX_LINE_LENGTH = 500  # chars

# Security
ALLOWED_IPS = {"127.0.0.1", "::1", "localhost"}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 100    # requests per window

# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════

class IncidentLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    ROLLBACK = "ROLLBACK"
    CLEAN = "CLEAN"
    BLOCK = "BLOCK"

@dataclass
class FileInfo:
    """Tracked file information"""
    path: str
    hash: str
    snapshot_path: Optional[str] = None
    last_modified: float = 0.0
    violations: int = 0

@dataclass
class Incident:
    """Security incident record"""
    id: int = 0
    timestamp: str = ""
    level: str = "INFO"
    message: str = ""
    source: str = ""
    details: Optional[str] = None

@dataclass
class RateLimitEntry:
    """Rate limiting entry"""
    ip: str
    count: int = 0
    window_start: float = field(default_factory=time.time)

# ═══════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════

class CerberDB:
    """SQLite database for incidents and fingerprints."""
    
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_schema()
    
    def _init_schema(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Incidents table
            c.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    source TEXT DEFAULT '',
                    details TEXT
                )
            """)
            
            # Fingerprints table
            c.execute("""
                CREATE TABLE IF NOT EXISTS fingerprints (
                    path TEXT PRIMARY KEY,
                    hash TEXT NOT NULL,
                    snapshot_path TEXT,
                    last_verified TEXT,
                    violations INTEGER DEFAULT 0
                )
            """)
            
            # Rate limits table
            c.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    ip TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    window_start REAL NOT NULL
                )
            """)
            
            conn.commit()
            conn.close()
    
    def log_incident(self, level: IncidentLevel, message: str, 
                     source: str = "", details: str = None) -> int:
        """Log security incident"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute("""
                INSERT INTO incidents (timestamp, level, message, source, details)
                VALUES (?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), level.value, message, source, details))
            
            incident_id = c.lastrowid
            conn.commit()
            conn.close()
            
            LOG.log(
                getattr(logging, level.value, logging.INFO),
                f"[{level.value}] {message}"
            )
            
            return incident_id
    
    def get_incidents(self, limit: int = 100, level: Optional[str] = None) -> List[Incident]:
        """Get recent incidents"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            if level:
                c.execute("""
                    SELECT id, timestamp, level, message, source, details
                    FROM incidents WHERE level = ?
                    ORDER BY id DESC LIMIT ?
                """, (level, limit))
            else:
                c.execute("""
                    SELECT id, timestamp, level, message, source, details
                    FROM incidents ORDER BY id DESC LIMIT ?
                """, (limit,))
            
            rows = c.fetchall()
            conn.close()
            
            return [Incident(*row) for row in rows]
    
    def save_fingerprint(self, info: FileInfo):
        """Save file fingerprint"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute("""
                INSERT OR REPLACE INTO fingerprints 
                (path, hash, snapshot_path, last_verified, violations)
                VALUES (?, ?, ?, ?, ?)
            """, (info.path, info.hash, info.snapshot_path, 
                  datetime.now().isoformat(), info.violations))
            
            conn.commit()
            conn.close()
    
    def get_fingerprint(self, path: str) -> Optional[FileInfo]:
        """Get stored fingerprint"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute("""
                SELECT path, hash, snapshot_path, violations 
                FROM fingerprints WHERE path = ?
            """, (path,))
            
            row = c.fetchone()
            conn.close()
            
            if row:
                return FileInfo(path=row[0], hash=row[1], 
                               snapshot_path=row[2], violations=row[3])
            return None
    
    def check_rate_limit(self, ip: str) -> bool:
        """Check if IP is rate limited. Returns True if allowed."""
        now = time.time()
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute("SELECT count, window_start FROM rate_limits WHERE ip = ?", (ip,))
            row = c.fetchone()
            
            if row:
                count, window_start = row
                
                # Reset window if expired
                if now - window_start > RATE_LIMIT_WINDOW:
                    c.execute("""
                        UPDATE rate_limits SET count = 1, window_start = ?
                        WHERE ip = ?
                    """, (now, ip))
                    conn.commit()
                    conn.close()
                    return True
                
                # Check limit
                if count >= RATE_LIMIT_MAX:
                    conn.close()
                    return False
                
                # Increment
                c.execute("UPDATE rate_limits SET count = count + 1 WHERE ip = ?", (ip,))
            else:
                c.execute("""
                    INSERT INTO rate_limits (ip, count, window_start)
                    VALUES (?, 1, ?)
                """, (ip, now))
            
            conn.commit()
            conn.close()
            return True

# ═══════════════════════════════════════════════════════════════════════════
# CERBER CORE
# ═══════════════════════════════════════════════════════════════════════════

class Cerber:
    """
    CERBER: Multi-layer security guardian.
    
    Layers:
        1. File Integrity - SHA256 fingerprinting
        2. Content Sanitization - FORBIDDEN patterns removal
        3. IP Whitelist - Request source validation
        4. Rate Limiting - DoS protection
        5. Audit Log - SQLite incident tracking
    """
    
    _instance: Optional["Cerber"] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs) -> "Cerber":
        """Singleton pattern"""
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
        self.db = CerberDB(str(self.root_dir / DB_FILE))
        
        self._tracked: Dict[str, FileInfo] = {}
        self._running = False
        self._worker: Optional[threading.Thread] = None
        
        # Compile forbidden patterns
        self._forbidden_regex = [re.compile(p) for p in FORBIDDEN_PATTERNS]
        
        # Stats
        self._stats = {
            "files_tracked": 0,
            "snapshots_created": 0,
            "rollbacks": 0,
            "violations": 0,
            "blocked_ips": 0
        }
        
        self._initialized = True
        LOG.info(f"[Cerber] Initialized at {self.root_dir}")
    
    # ─────────────────────────────────────────────────────────────────────
    # FILE INTEGRITY
    # ─────────────────────────────────────────────────────────────────────
    
    def file_hash(self, path: str) -> str:
        """Calculate SHA256 hash of file"""
        h = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            LOG.error(f"Hash error for {path}: {e}")
            return ""
    
    def create_snapshot(self, path: str) -> Optional[str]:
        """Create backup snapshot of file"""
        try:
            self.snapshot_dir.mkdir(exist_ok=True)
            
            # Create unique snapshot name
            rel_path = Path(path).relative_to(self.root_dir)
            snap_name = str(rel_path).replace(os.sep, "__")
            snap_path = self.snapshot_dir / snap_name
            
            # Don't snapshot self
            if snap_path.resolve() == Path(path).resolve():
                return None
            
            shutil.copy2(path, snap_path)
            self._stats["snapshots_created"] += 1
            
            LOG.debug(f"Snapshot created: {snap_path}")
            return str(snap_path)
            
        except Exception as e:
            LOG.error(f"Snapshot error for {path}: {e}")
            return None
    
    def restore_snapshot(self, path: str) -> bool:
        """Restore file from snapshot"""
        info = self._tracked.get(path) or self.db.get_fingerprint(path)
        
        if not info or not info.snapshot_path:
            self.db.log_incident(IncidentLevel.WARN, 
                                f"No snapshot for {path}", source="restore")
            return False
        
        if not os.path.exists(info.snapshot_path):
            self.db.log_incident(IncidentLevel.WARN,
                                f"Snapshot missing: {info.snapshot_path}", source="restore")
            return False
        
        try:
            shutil.copy2(info.snapshot_path, path)
            self._stats["rollbacks"] += 1
            
            self.db.log_incident(IncidentLevel.ROLLBACK,
                                f"Restored {path} from snapshot", source="restore")
            
            # Emit event
            publish("cerber.rollback", {"path": path}, priority=Priority.CRITICAL if Priority else 0)
            
            return True
        except Exception as e:
            LOG.error(f"Restore error for {path}: {e}")
            return False
    
    # ─────────────────────────────────────────────────────────────────────
    # CONTENT ANALYSIS
    # ─────────────────────────────────────────────────────────────────────
    
    def analyze_content(self, path: str) -> List[str]:
        """Analyze file for violations. Returns list of issues."""
        issues = []
        
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    # Line length
                    if len(line) > MAX_LINE_LENGTH:
                        issues.append(f"Line {line_num}: exceeds {MAX_LINE_LENGTH} chars")
                    
                    # Forbidden patterns
                    for regex in self._forbidden_regex:
                        if regex.search(line):
                            issues.append(f"Line {line_num}: forbidden pattern '{regex.pattern}'")
                            
        except Exception as e:
            issues.append(f"Read error: {e}")
        
        return issues
    
    def sanitize_content(self, path: str) -> int:
        """Remove forbidden content from file. Returns lines removed."""
        cleaned = []
        removed = 0
        
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    # Skip long lines
                    if len(line) > MAX_LINE_LENGTH:
                        removed += 1
                        continue
                    
                    # Skip forbidden patterns
                    skip = False
                    for regex in self._forbidden_regex:
                        if regex.search(line):
                            removed += 1
                            skip = True
                            break
                    
                    if not skip:
                        cleaned.append(line)
            
            if removed > 0:
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(cleaned)
                
                self.db.log_incident(IncidentLevel.CLEAN,
                                    f"Sanitized {path}: {removed} lines removed",
                                    source="sanitize")
                self._stats["violations"] += removed
                
                # Emit event
                publish("cerber.sanitize", {"path": path, "removed": removed})
                
        except Exception as e:
            LOG.error(f"Sanitize error for {path}: {e}")
        
        return removed
    
    def needs_rollback(self, path: str) -> bool:
        """Check if file needs rollback based on violation severity"""
        issues = self.analyze_content(path)
        
        # Critical patterns warrant rollback
        critical_patterns = [r"<{7}", r">{7}", r"={7}"]  # Git conflicts
        
        for issue in issues:
            for pattern in critical_patterns:
                if pattern in issue:
                    return True
        
        # Too many issues = rollback
        return len(issues) > 10
    
    # ─────────────────────────────────────────────────────────────────────
    # IP SECURITY
    # ─────────────────────────────────────────────────────────────────────
    
    def check_ip(self, ip: str) -> bool:
        """Check if IP is allowed"""
        # Localhost always allowed
        if ip in ALLOWED_IPS:
            return True
        
        # Check rate limit
        if not self.db.check_rate_limit(ip):
            self.db.log_incident(IncidentLevel.BLOCK,
                                f"Rate limit exceeded for {ip}",
                                source="ip_check")
            self._stats["blocked_ips"] += 1
            
            publish("cerber.blocked", {"ip": ip, "reason": "rate_limit"}, 
                   priority=Priority.HIGH if Priority else 10)
            
            return False
        
        return True
    
    def add_allowed_ip(self, ip: str):
        """Add IP to whitelist"""
        ALLOWED_IPS.add(ip)
        LOG.info(f"Added to whitelist: {ip}")
    
    # ─────────────────────────────────────────────────────────────────────
    # MONITORING
    # ─────────────────────────────────────────────────────────────────────
    
    def track_file(self, path: str) -> Optional[FileInfo]:
        """Start tracking a file"""
        path = str(Path(path).resolve())
        
        # Ignore self
        if os.path.basename(path) in IGNORE_FILES:
            return None
        
        if not os.path.exists(path):
            return None
        
        file_hash = self.file_hash(path)
        snapshot_path = self.create_snapshot(path)
        
        info = FileInfo(
            path=path,
            hash=file_hash,
            snapshot_path=snapshot_path,
            last_modified=os.path.getmtime(path)
        )
        
        self._tracked[path] = info
        self.db.save_fingerprint(info)
        self._stats["files_tracked"] += 1
        
        LOG.debug(f"Tracking: {path}")
        return info
    
    def verify_file(self, path: str) -> bool:
        """Verify file integrity. Returns True if OK."""
        path = str(Path(path).resolve())
        
        if path not in self._tracked:
            info = self.db.get_fingerprint(path)
            if not info:
                # New file, start tracking
                self.track_file(path)
                return True
            self._tracked[path] = info
        else:
            info = self._tracked[path]
        
        current_hash = self.file_hash(path)
        
        if current_hash != info.hash:
            LOG.info(f"File changed: {path}")
            
            # Analyze
            if self.needs_rollback(path):
                self.restore_snapshot(path)
                return False
            else:
                # Sanitize
                self.sanitize_content(path)
            
            # Update hash
            info.hash = self.file_hash(path)
            info.last_modified = os.path.getmtime(path)
            self._tracked[path] = info
            self.db.save_fingerprint(info)
        
        return True
    
    def scan_directory(self, directory: str = ".") -> List[str]:
        """Scan directory for files to track"""
        directory = Path(directory).resolve()
        tracked = []
        
        for ext in WATCH_EXTENSIONS:
            for path in directory.rglob(f"*{ext}"):
                # Skip ignored
                if path.name in IGNORE_FILES:
                    continue
                # Skip snapshots
                if SNAPSHOT_DIR in str(path):
                    continue
                
                self.track_file(str(path))
                tracked.append(str(path))
        
        return tracked
    
    def _worker_loop(self):
        """Background monitoring loop"""
        LOG.info("[Cerber] Guardian active - monitoring started")
        
        publish("cerber.started", source="cerber", priority=Priority.HIGH if Priority else 10)
        
        while self._running:
            try:
                # Verify tracked files
                for path in list(self._tracked.keys()):
                    if not os.path.exists(path):
                        continue
                    
                    # Skip ignored
                    if os.path.basename(path) in IGNORE_FILES:
                        continue
                    
                    self.verify_file(path)
                
                # Scan for new files
                self.scan_directory(str(self.root_dir))
                
                time.sleep(SCAN_INTERVAL)
                
            except Exception as e:
                LOG.error(f"[Cerber] Monitor error: {e}")
                time.sleep(SCAN_INTERVAL * 2)
        
        LOG.info("[Cerber] Guardian stopped")
    
    # ─────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────
    
    def start(self):
        """Start background monitoring"""
        if self._running:
            return
        
        self._running = True
        self._worker = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="Cerber-Guardian"
        )
        self._worker.start()
        
        LOG.info("[Cerber] Started")
    
    def stop(self):
        """Stop monitoring"""
        if not self._running:
            return
        
        publish("cerber.stopping", source="cerber", priority=Priority.HIGH if Priority else 10)
        
        self._running = False
        if self._worker:
            self._worker.join(timeout=5.0)
            self._worker = None
        
        LOG.info(f"[Cerber] Stopped. Stats: {self._stats}")
    
    def status(self) -> Dict[str, Any]:
        """Get Cerber status"""
        return {
            "running": self._running,
            "root_dir": str(self.root_dir),
            "tracked_files": len(self._tracked),
            "stats": self._stats.copy(),
            "allowed_ips": list(ALLOWED_IPS)
        }
    
    def incidents(self, limit: int = 20, level: Optional[str] = None) -> List[Incident]:
        """Get recent incidents"""
        return self.db.get_incidents(limit, level)
    
    def verify_all(self) -> Dict[str, bool]:
        """Verify all tracked files"""
        results = {}
        for path in self._tracked:
            results[path] = self.verify_file(path)
        return results

# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE / SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════

def get_cerber(root_dir: str = ".") -> Cerber:
    """Get Cerber singleton"""
    return Cerber(root_dir)

def verify(path: str) -> bool:
    """Convenience: verify file integrity"""
    return get_cerber().verify_file(path)

def check_ip(ip: str) -> bool:
    """Convenience: check IP"""
    return get_cerber().check_ip(ip)

# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s] [%(levelname)s] %(message)s'
    )
    
    parser = argparse.ArgumentParser(description="CERBER Security Guardian")
    parser.add_argument("--start", action="store_true", help="Start monitoring")
    parser.add_argument("--verify", type=str, help="Verify file")
    parser.add_argument("--scan", type=str, default=".", help="Scan directory")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--incidents", type=int, default=10, help="Show incidents")
    
    args = parser.parse_args()
    
    cerber = get_cerber()
    
    if args.verify:
        ok = cerber.verify_file(args.verify)
        print(f"{'✅' if ok else '❌'} {args.verify}")
    
    elif args.status:
        import json
        print(json.dumps(cerber.status(), indent=2))
    
    elif args.incidents:
        for inc in cerber.incidents(args.incidents):
            print(f"[{inc.level}] {inc.timestamp}: {inc.message}")
    
    elif args.start:
        print(f"[CERBER] Scanning {args.scan}...")
        files = cerber.scan_directory(args.scan)
        print(f"[CERBER] Tracking {len(files)} files")
        
        cerber.start()
        
        try:
            print("[CERBER] Press Ctrl+C to stop...")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            cerber.stop()
    
    else:
        parser.print_help()
