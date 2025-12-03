"""
☁️ ALFA CLOUD ENGINE
Silnik prywatnej chmury offline
"""

import os
import json
import hashlib
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable
from enum import Enum, auto
import shutil
import sqlite3
import threading

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLOUD STATUS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CloudState(Enum):
    """Stan chmury offline"""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    SYNCING = auto()
    BACKING_UP = auto()
    ERROR = auto()
    MAINTENANCE = auto()


class StorageType(Enum):
    """Typy przechowywania"""
    FILE = "file"
    BLOB = "blob"
    STRUCTURED = "structured"
    ENCRYPTED = "encrypted"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA CLASSES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class CloudFile:
    """Reprezentacja pliku w chmurze"""
    id: str
    name: str
    path: str
    size: int
    hash: str
    created_at: datetime
    modified_at: datetime
    encrypted: bool = False
    storage_type: StorageType = StorageType.FILE
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class SyncPeer:
    """Peer do synchronizacji LAN"""
    id: str
    name: str
    ip: str
    port: int
    last_seen: datetime
    is_online: bool = False
    sync_enabled: bool = True


@dataclass
class CloudStats:
    """Statystyki chmury"""
    total_files: int = 0
    total_size_bytes: int = 0
    encrypted_files: int = 0
    synced_files: int = 0
    last_backup: Optional[datetime] = None
    last_sync: Optional[datetime] = None
    peers_online: int = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLOUD ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CloudEngine:
    """
    ☁️ ALFA CLOUD ENGINE
    Silnik prywatnej chmury działającej 100% offline
    """
    
    BANNER = """
    ╔═══════════════════════════════════════════╗
    ║       ☁️ ALFA CLOUD OFFLINE ☁️            ║
    ║   Twoja Prywatna Chmura — 100% Lokalna   ║
    ╚═══════════════════════════════════════════╝
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.state = CloudState.STOPPED
        self.base_path = Path(__file__).parent.parent
        
        # Ładuj konfigurację
        self.config_path = config_path or self.base_path / "config" / "cloud_config.json"
        self.config = self._load_config()
        
        # Ścieżki
        self.storage_path = self.base_path / "storage"
        self.cache_path = self.base_path / "cache"
        self.logs_path = self.base_path / "logs"
        self.backup_path = self.base_path / "backups"
        
        # Komponenty
        self.db: Optional[sqlite3.Connection] = None
        self.logger = self._setup_logging()
        self.stats = CloudStats()
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        # Peers LAN
        self.peers: Dict[str, SyncPeer] = {}
        
        # Lock dla thread safety
        self._lock = threading.RLock()
        
        # Background tasks
        self._running = False
        self._sync_task: Optional[asyncio.Task] = None
        self._backup_task: Optional[asyncio.Task] = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Ładuje konfigurację chmury"""
        if Path(self.config_path).exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "mode": "offline",
            "storage": {"root_path": "./storage"},
            "encryption": {"enabled": True},
            "sync": {"enabled": True}
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Konfiguruje logging"""
        logger = logging.getLogger("ALFA_CLOUD")
        logger.setLevel(logging.INFO)
        
        # File handler
        log_file = self.logs_path / "cloud.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        ))
        logger.addHandler(fh)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('☁️ %(message)s'))
        logger.addHandler(ch)
        
        return logger
    
    def _init_database(self):
        """Inicjalizuje bazę danych SQLite"""
        db_path = self.storage_path / "cloud.db"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        cursor = self.db.cursor()
        
        # Tabela plików
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                size INTEGER,
                hash TEXT,
                created_at TIMESTAMP,
                modified_at TIMESTAMP,
                encrypted INTEGER DEFAULT 0,
                storage_type TEXT DEFAULT 'file',
                metadata TEXT,
                tags TEXT,
                deleted INTEGER DEFAULT 0
            )
        """)
        
        # Tabela wersji (dla backup)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_versions (
                id TEXT PRIMARY KEY,
                file_id TEXT,
                version INTEGER,
                hash TEXT,
                size INTEGER,
                created_at TIMESTAMP,
                backup_path TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            )
        """)
        
        # Tabela sync
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                peer_id TEXT,
                action TEXT,
                timestamp TIMESTAMP,
                status TEXT
            )
        """)
        
        # Tabela peers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS peers (
                id TEXT PRIMARY KEY,
                name TEXT,
                ip TEXT,
                port INTEGER,
                last_seen TIMESTAMP,
                sync_enabled INTEGER DEFAULT 1
            )
        """)
        
        self.db.commit()
        self.logger.info("📊 Baza danych zainicjalizowana")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LIFECYCLE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def start(self):
        """Uruchamia silnik chmury"""
        print(self.BANNER)
        self.state = CloudState.STARTING
        self.logger.info("🚀 Uruchamiam ALFA CLOUD OFFLINE...")
        
        try:
            # Twórz katalogi
            for path in [self.storage_path, self.cache_path, 
                        self.logs_path, self.backup_path]:
                path.mkdir(parents=True, exist_ok=True)
            
            # Inicjalizuj bazę danych
            self._init_database()
            
            # Ładuj statystyki
            await self._load_stats()
            
            # Uruchom background tasks
            self._running = True
            
            if self.config.get("sync", {}).get("auto_sync"):
                self._sync_task = asyncio.create_task(self._sync_loop())
            
            if self.config.get("backup", {}).get("auto_backup"):
                self._backup_task = asyncio.create_task(self._backup_loop())
            
            self.state = CloudState.RUNNING
            self.logger.info("✅ ALFA CLOUD OFFLINE uruchomiona!")
            self._emit("cloud:started", {"timestamp": datetime.now().isoformat()})
            
        except Exception as e:
            self.state = CloudState.ERROR
            self.logger.error(f"❌ Błąd uruchamiania: {e}")
            raise
    
    async def stop(self):
        """Zatrzymuje silnik chmury"""
        self.logger.info("🛑 Zatrzymuję ALFA CLOUD OFFLINE...")
        self._running = False
        
        # Anuluj background tasks
        if self._sync_task:
            self._sync_task.cancel()
        if self._backup_task:
            self._backup_task.cancel()
        
        # Zamknij bazę danych
        if self.db:
            self.db.close()
        
        self.state = CloudState.STOPPED
        self.logger.info("⏹️ ALFA CLOUD OFFLINE zatrzymana")
        self._emit("cloud:stopped", {"timestamp": datetime.now().isoformat()})
    
    def status(self) -> Dict[str, Any]:
        """Zwraca status chmury"""
        return {
            "state": self.state.name,
            "storage_path": str(self.storage_path),
            "stats": {
                "total_files": self.stats.total_files,
                "total_size_mb": round(self.stats.total_size_bytes / (1024 * 1024), 2),
                "encrypted_files": self.stats.encrypted_files,
                "peers_online": self.stats.peers_online
            },
            "config": {
                "encryption_enabled": self.config.get("encryption", {}).get("enabled"),
                "sync_enabled": self.config.get("sync", {}).get("enabled"),
                "ai_enabled": self.config.get("ai_local", {}).get("enabled")
            }
        }
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FILE OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def upload(self, source_path: str, 
               target_path: Optional[str] = None,
               encrypt: bool = False,
               tags: Optional[List[str]] = None) -> CloudFile:
        """
        Upload pliku do chmury
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Plik nie istnieje: {source_path}")
        
        # Generuj ID i ścieżkę docelową
        file_id = self._generate_id(source.name)
        target = target_path or source.name
        dest_path = self.storage_path / "files" / target
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Kopiuj plik
        content = source.read_bytes()
        file_hash = hashlib.blake2b(content).hexdigest()
        
        # Szyfruj jeśli wymagane
        if encrypt or self.config.get("encryption", {}).get("enabled"):
            content = self._encrypt_data(content)
            encrypt = True
        
        # Zapisz plik
        dest_path.write_bytes(content)
        
        # Twórz rekord
        now = datetime.now()
        cloud_file = CloudFile(
            id=file_id,
            name=source.name,
            path=str(dest_path.relative_to(self.storage_path)),
            size=len(content),
            hash=file_hash,
            created_at=now,
            modified_at=now,
            encrypted=encrypt,
            tags=tags or []
        )
        
        # Zapisz do bazy
        self._save_file_record(cloud_file)
        
        self.logger.info(f"📤 Upload: {source.name} → {target}")
        self._emit("file:uploaded", {"file_id": file_id, "name": source.name})
        
        return cloud_file
    
    def download(self, file_id: str, 
                 target_path: Optional[str] = None) -> Path:
        """
        Download pliku z chmury
        """
        file_record = self._get_file_record(file_id)
        if not file_record:
            raise FileNotFoundError(f"Plik nie znaleziony: {file_id}")
        
        source_path = self.storage_path / file_record.path
        if not source_path.exists():
            raise FileNotFoundError(f"Plik nie istnieje na dysku: {source_path}")
        
        content = source_path.read_bytes()
        
        # Deszyfruj jeśli zaszyfrowany
        if file_record.encrypted:
            content = self._decrypt_data(content)
        
        # Zapisz do celu
        target = Path(target_path) if target_path else Path.cwd() / file_record.name
        target.write_bytes(content)
        
        self.logger.info(f"📥 Download: {file_record.name} → {target}")
        self._emit("file:downloaded", {"file_id": file_id, "target": str(target)})
        
        return target
    
    def delete(self, file_id: str, permanent: bool = False):
        """
        Usuwa plik z chmury
        """
        with self._lock:
            if self.db:
                cursor = self.db.cursor()
                
                if permanent:
                    # Usuń z dysku
                    file_record = self._get_file_record(file_id)
                    if file_record:
                        file_path = self.storage_path / file_record.path
                        if file_path.exists():
                            file_path.unlink()
                    
                    cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
                else:
                    # Soft delete
                    cursor.execute(
                        "UPDATE files SET deleted = 1 WHERE id = ?", 
                        (file_id,)
                    )
                
                self.db.commit()
        
        self.logger.info(f"🗑️ Usunięto: {file_id} (permanent={permanent})")
        self._emit("file:deleted", {"file_id": file_id, "permanent": permanent})
    
    def list_files(self, 
                   path: Optional[str] = None,
                   tags: Optional[List[str]] = None,
                   include_deleted: bool = False) -> List[CloudFile]:
        """
        Lista plików w chmurze
        """
        files = []
        
        if self.db:
            cursor = self.db.cursor()
            query = "SELECT * FROM files"
            conditions = []
            params = []
            
            if not include_deleted:
                conditions.append("deleted = 0")
            
            if path:
                conditions.append("path LIKE ?")
                params.append(f"{path}%")
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            cursor.execute(query, params)
            
            for row in cursor.fetchall():
                files.append(CloudFile(
                    id=row[0],
                    name=row[1],
                    path=row[2],
                    size=row[3],
                    hash=row[4],
                    created_at=datetime.fromisoformat(row[5]) if row[5] else datetime.now(),
                    modified_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now(),
                    encrypted=bool(row[7]),
                    storage_type=StorageType(row[8]) if row[8] else StorageType.FILE,
                    metadata=json.loads(row[9]) if row[9] else {},
                    tags=json.loads(row[10]) if row[10] else []
                ))
        
        return files
    
    def search(self, query: str) -> List[CloudFile]:
        """
        Szukaj plików
        """
        files = []
        
        if self.db:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT * FROM files 
                WHERE deleted = 0 
                AND (name LIKE ? OR tags LIKE ? OR metadata LIKE ?)
            """, (f"%{query}%", f"%{query}%", f"%{query}%"))
            
            for row in cursor.fetchall():
                files.append(CloudFile(
                    id=row[0],
                    name=row[1],
                    path=row[2],
                    size=row[3],
                    hash=row[4],
                    created_at=datetime.fromisoformat(row[5]) if row[5] else datetime.now(),
                    modified_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now(),
                    encrypted=bool(row[7])
                ))
        
        return files
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ENCRYPTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def _encrypt_data(self, data: bytes) -> bytes:
        """Szyfruje dane (placeholder - używaj encryption.py)"""
        # TODO: Implementacja z encryption.py
        # Na razie base64 jako placeholder
        import base64
        return b"ENC:" + base64.b64encode(data)
    
    def _decrypt_data(self, data: bytes) -> bytes:
        """Deszyfruje dane (placeholder - używaj encryption.py)"""
        import base64
        if data.startswith(b"ENC:"):
            return base64.b64decode(data[4:])
        return data
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SYNC
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def sync_to(self, peer_ip: str, peer_port: int = 8766):
        """
        Synchronizuj do peera w sieci LAN
        """
        self.state = CloudState.SYNCING
        self.logger.info(f"🔄 Synchronizacja do {peer_ip}:{peer_port}...")
        
        try:
            # TODO: Implementacja rzeczywistej synchronizacji TCP/UDP
            # Na razie placeholder
            await asyncio.sleep(1)
            
            self.stats.last_sync = datetime.now()
            self.logger.info(f"✅ Synchronizacja zakończona")
            self._emit("sync:completed", {"peer": peer_ip})
            
        except Exception as e:
            self.logger.error(f"❌ Błąd synchronizacji: {e}")
            self._emit("sync:failed", {"peer": peer_ip, "error": str(e)})
        
        finally:
            self.state = CloudState.RUNNING
    
    async def discover_peers(self) -> List[SyncPeer]:
        """
        Odkryj peery w sieci LAN (UDP broadcast)
        """
        self.logger.info("🔍 Szukam peerów w sieci LAN...")
        
        # TODO: UDP broadcast discovery
        # Na razie placeholder
        peers = []
        
        return peers
    
    async def _sync_loop(self):
        """Background loop dla auto-sync"""
        interval = self.config.get("sync", {}).get("sync_interval_seconds", 300)
        
        while self._running:
            try:
                await asyncio.sleep(interval)
                
                # Sync do wszystkich online peerów
                for peer in self.peers.values():
                    if peer.is_online and peer.sync_enabled:
                        await self.sync_to(peer.ip, peer.port)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Błąd sync loop: {e}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BACKUP
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def backup(self, target_path: Optional[str] = None) -> Path:
        """
        Twórz backup wszystkich plików
        """
        self.state = CloudState.BACKING_UP
        self.logger.info("💾 Tworzę backup...")
        
        try:
            # Ścieżka backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"
            backup_dir = Path(target_path) if target_path else self.backup_path / backup_name
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Kopiuj storage
            storage_backup = backup_dir / "storage"
            shutil.copytree(self.storage_path, storage_backup, dirs_exist_ok=True)
            
            # Eksportuj bazę danych
            if self.db:
                db_backup = backup_dir / "cloud.db"
                shutil.copy2(self.storage_path / "cloud.db", db_backup)
            
            # Zapisz manifest
            manifest = {
                "timestamp": datetime.now().isoformat(),
                "stats": {
                    "total_files": self.stats.total_files,
                    "total_size": self.stats.total_size_bytes
                }
            }
            (backup_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding='utf-8'
            )
            
            self.stats.last_backup = datetime.now()
            self.logger.info(f"✅ Backup utworzony: {backup_dir}")
            self._emit("backup:completed", {"path": str(backup_dir)})
            
            # Usuń stare backupy
            await self._cleanup_old_backups()
            
            return backup_dir
            
        finally:
            self.state = CloudState.RUNNING
    
    async def restore(self, backup_path: str):
        """
        Przywróć z backupu
        """
        backup_dir = Path(backup_path)
        if not backup_dir.exists():
            raise FileNotFoundError(f"Backup nie istnieje: {backup_path}")
        
        self.logger.info(f"🔄 Przywracam z backupu: {backup_path}")
        
        # Zamknij bazę danych
        if self.db:
            self.db.close()
        
        # Przywróć storage
        storage_backup = backup_dir / "storage"
        if storage_backup.exists():
            shutil.rmtree(self.storage_path, ignore_errors=True)
            shutil.copytree(storage_backup, self.storage_path)
        
        # Przywróć bazę danych
        db_backup = backup_dir / "cloud.db"
        if db_backup.exists():
            shutil.copy2(db_backup, self.storage_path / "cloud.db")
        
        # Reinicjalizuj
        self._init_database()
        await self._load_stats()
        
        self.logger.info("✅ Przywracanie zakończone")
        self._emit("backup:restored", {"path": backup_path})
    
    async def _backup_loop(self):
        """Background loop dla auto-backup"""
        interval = self.config.get("backup", {}).get("backup_interval_hours", 24) * 3600
        
        while self._running:
            try:
                await asyncio.sleep(interval)
                await self.backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Błąd backup loop: {e}")
    
    async def _cleanup_old_backups(self):
        """Usuwa stare backupy"""
        versions_to_keep = self.config.get("backup", {}).get("versions_to_keep", 7)
        
        backups = sorted(
            [d for d in self.backup_path.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for old_backup in backups[versions_to_keep:]:
            shutil.rmtree(old_backup)
            self.logger.info(f"🗑️ Usunięto stary backup: {old_backup.name}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # HELPERS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def _generate_id(self, name: str) -> str:
        """Generuje unikalne ID pliku"""
        import uuid
        return f"{uuid.uuid4().hex[:8]}_{hashlib.md5(name.encode()).hexdigest()[:8]}"
    
    def _save_file_record(self, file: CloudFile):
        """Zapisuje rekord pliku do bazy"""
        with self._lock:
            if self.db:
                cursor = self.db.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO files 
                    (id, name, path, size, hash, created_at, modified_at, 
                     encrypted, storage_type, metadata, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file.id, file.name, file.path, file.size, file.hash,
                    file.created_at.isoformat(), file.modified_at.isoformat(),
                    1 if file.encrypted else 0, file.storage_type.value,
                    json.dumps(file.metadata), json.dumps(file.tags)
                ))
                self.db.commit()
    
    def _get_file_record(self, file_id: str) -> Optional[CloudFile]:
        """Pobiera rekord pliku z bazy"""
        if self.db:
            cursor = self.db.cursor()
            cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            
            if row:
                return CloudFile(
                    id=row[0],
                    name=row[1],
                    path=row[2],
                    size=row[3],
                    hash=row[4],
                    created_at=datetime.fromisoformat(row[5]) if row[5] else datetime.now(),
                    modified_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now(),
                    encrypted=bool(row[7])
                )
        return None
    
    async def _load_stats(self):
        """Ładuje statystyki z bazy"""
        if self.db:
            cursor = self.db.cursor()
            
            # Total files
            cursor.execute("SELECT COUNT(*) FROM files WHERE deleted = 0")
            self.stats.total_files = cursor.fetchone()[0]
            
            # Total size
            cursor.execute("SELECT COALESCE(SUM(size), 0) FROM files WHERE deleted = 0")
            self.stats.total_size_bytes = cursor.fetchone()[0]
            
            # Encrypted files
            cursor.execute("SELECT COUNT(*) FROM files WHERE encrypted = 1 AND deleted = 0")
            self.stats.encrypted_files = cursor.fetchone()[0]
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EVENTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def on(self, event: str, handler: Callable):
        """Rejestruje event handler"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
    
    def _emit(self, event: str, data: Dict[str, Any]):
        """Emituje event"""
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    self.logger.error(f"Błąd event handler: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    async def main():
        cloud = CloudEngine()
        await cloud.start()
        
        print("\n📊 Status:", cloud.status())
        
        # Testowy upload
        # cloud.upload("test.txt")
        
        await cloud.stop()
    
    asyncio.run(main())
