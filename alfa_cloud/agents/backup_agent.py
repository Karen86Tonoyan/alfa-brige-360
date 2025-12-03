"""
💾 BACKUP AGENT
Agent automatycznego backup dla ALFA CLOUD
"""

from __future__ import annotations
import os
import shutil
import json
import hashlib
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import logging
import zipfile
import tarfile

from alfa_cloud.core.event_bus import EventBus


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA CLASSES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class BackupInfo:
    """Informacje o backupie"""
    id: str
    name: str
    path: str
    size: int
    files_count: int
    created_at: datetime
    type: str = "full"  # full, incremental, differential
    compressed: bool = True
    encrypted: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class BackupConfig:
    """Konfiguracja backupu"""
    enabled: bool = True
    auto_backup: bool = True
    interval_hours: int = 24
    backup_path: str = "./backups"
    versions_to_keep: int = 7
    compression: str = "zip"  # zip, tar.gz, none
    encrypt: bool = False
    include_patterns: List[str] = None
    exclude_patterns: List[str] = None
    
    def __post_init__(self):
        if self.include_patterns is None:
            self.include_patterns = ["*"]
        if self.exclude_patterns is None:
            self.exclude_patterns = ["*.tmp", "*.log", ".trash/*", "__pycache__/*"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKUP AGENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BackupAgent:
    """
    💾 Agent backup
    
    Funkcje:
    - Automatyczny backup według harmonogramu
    - Backup pełny i przyrostowy
    - Kompresja (zip, tar.gz)
    - Rotacja wersji
    - Przywracanie
    """
    
    def __init__(self,
                 storage_path: str,
                 backup_path: str,
                 config: Optional[BackupConfig] = None,
                 event_bus: Optional[EventBus] = None):
        
        self.storage_path = Path(storage_path)
        self.backup_path = Path(backup_path)
        self.config = config or BackupConfig(backup_path=backup_path)
        self.event_bus = event_bus or EventBus()
        self.logger = logging.getLogger("ALFA_CLOUD.BackupAgent")
        
        # Utwórz katalog backupów
        self.backup_path.mkdir(parents=True, exist_ok=True)
        
        # Historia backupów
        self._history: List[BackupInfo] = []
        self._load_history()
        
        # Auto-backup task
        self._running = False
        self._backup_task: Optional[asyncio.Task] = None
    
    def _load_history(self):
        """Ładuje historię backupów"""
        history_file = self.backup_path / "backup_history.json"
        if history_file.exists():
            try:
                data = json.loads(history_file.read_text())
                for item in data:
                    item["created_at"] = datetime.fromisoformat(item["created_at"])
                    self._history.append(BackupInfo(**item))
            except Exception as e:
                self.logger.error(f"Błąd ładowania historii: {e}")
    
    def _save_history(self):
        """Zapisuje historię backupów"""
        history_file = self.backup_path / "backup_history.json"
        data = [b.to_dict() for b in self._history]
        history_file.write_text(json.dumps(data, indent=2))
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BACKUP OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def create_backup(self,
                           name: Optional[str] = None,
                           backup_type: str = "full",
                           compress: bool = True) -> BackupInfo:
        """
        Tworzy backup
        
        Args:
            name: Nazwa backupu (domyślnie timestamp)
            backup_type: full, incremental
            compress: Czy kompresować
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"backup_{timestamp}"
        backup_id = hashlib.md5(f"{backup_name}_{timestamp}".encode()).hexdigest()[:12]
        
        self.logger.info(f"💾 Tworzę backup: {backup_name}")
        
        # Katalog tymczasowy
        temp_dir = self.backup_path / f".temp_{backup_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            files_count = 0
            total_size = 0
            
            # Kopiuj pliki
            for item in self.storage_path.rglob("*"):
                # Sprawdź exclude patterns
                relative_path = item.relative_to(self.storage_path)
                if self._should_exclude(str(relative_path)):
                    continue
                
                dest = temp_dir / relative_path
                
                if item.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
                    files_count += 1
                    total_size += item.stat().st_size
            
            # Dodaj manifest
            manifest = {
                "id": backup_id,
                "name": backup_name,
                "type": backup_type,
                "created_at": datetime.now().isoformat(),
                "source_path": str(self.storage_path),
                "files_count": files_count,
                "total_size": total_size
            }
            (temp_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
            
            # Kompresuj
            if compress:
                final_path = self._compress_backup(temp_dir, backup_name)
            else:
                final_path = self.backup_path / backup_name
                shutil.move(temp_dir, final_path)
            
            # Utwórz BackupInfo
            backup_info = BackupInfo(
                id=backup_id,
                name=backup_name,
                path=str(final_path),
                size=self._get_size(final_path),
                files_count=files_count,
                created_at=datetime.now(),
                type=backup_type,
                compressed=compress
            )
            
            self._history.append(backup_info)
            self._save_history()
            
            # Rotacja
            await self._rotate_backups()
            
            self.logger.info(f"✅ Backup utworzony: {backup_name} ({files_count} plików)")
            self.event_bus.emit("backup:created", backup_info.to_dict())
            
            return backup_info
            
        finally:
            # Cleanup temp
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _compress_backup(self, source_dir: Path, name: str) -> Path:
        """Kompresuje backup"""
        if self.config.compression == "zip":
            archive_path = self.backup_path / f"{name}.zip"
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in source_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(source_dir))
            shutil.rmtree(source_dir)
            return archive_path
        
        elif self.config.compression == "tar.gz":
            archive_path = self.backup_path / f"{name}.tar.gz"
            with tarfile.open(archive_path, 'w:gz') as tf:
                tf.add(source_dir, arcname=name)
            shutil.rmtree(source_dir)
            return archive_path
        
        else:
            final_path = self.backup_path / name
            shutil.move(source_dir, final_path)
            return final_path
    
    def _should_exclude(self, path: str) -> bool:
        """Sprawdza czy plik powinien być wykluczony"""
        from fnmatch import fnmatch
        
        for pattern in self.config.exclude_patterns:
            if fnmatch(path, pattern):
                return True
        return False
    
    def _get_size(self, path: Path) -> int:
        """Pobiera rozmiar pliku/folderu"""
        if path.is_file():
            return path.stat().st_size
        
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # RESTORE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def restore_backup(self, 
                            backup_id: str,
                            target_path: Optional[str] = None) -> bool:
        """
        Przywraca z backupu
        
        Args:
            backup_id: ID backupu
            target_path: Ścieżka docelowa (domyślnie storage)
        """
        backup_info = self.get_backup(backup_id)
        if not backup_info:
            self.logger.error(f"Backup nie znaleziony: {backup_id}")
            return False
        
        backup_path = Path(backup_info.path)
        target = Path(target_path) if target_path else self.storage_path
        
        self.logger.info(f"🔄 Przywracam backup: {backup_info.name}")
        
        try:
            # Rozpakuj jeśli skompresowany
            if backup_path.suffix == '.zip':
                with zipfile.ZipFile(backup_path, 'r') as zf:
                    zf.extractall(target)
            
            elif backup_path.suffix == '.gz':
                with tarfile.open(backup_path, 'r:gz') as tf:
                    tf.extractall(target)
            
            else:
                # Kopiuj bezpośrednio
                for item in backup_path.rglob("*"):
                    if item.name == "manifest.json":
                        continue
                    
                    relative = item.relative_to(backup_path)
                    dest = target / relative
                    
                    if item.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest)
            
            self.logger.info(f"✅ Przywrócono backup: {backup_info.name}")
            self.event_bus.emit("backup:restored", backup_info.to_dict())
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Błąd przywracania: {e}")
            return False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ROTATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def _rotate_backups(self):
        """Usuwa stare backupy"""
        if len(self._history) <= self.config.versions_to_keep:
            return
        
        # Sortuj od najstarszych
        sorted_backups = sorted(self._history, key=lambda b: b.created_at)
        
        # Usuń najstarsze
        to_remove = sorted_backups[:-self.config.versions_to_keep]
        
        for backup in to_remove:
            await self.delete_backup(backup.id)
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Usuwa backup"""
        backup_info = self.get_backup(backup_id)
        if not backup_info:
            return False
        
        try:
            backup_path = Path(backup_info.path)
            if backup_path.exists():
                if backup_path.is_dir():
                    shutil.rmtree(backup_path)
                else:
                    backup_path.unlink()
            
            self._history = [b for b in self._history if b.id != backup_id]
            self._save_history()
            
            self.logger.info(f"🗑️ Usunięto backup: {backup_info.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Błąd usuwania backupu: {e}")
            return False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # AUTO BACKUP
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def start_auto_backup(self):
        """Uruchamia automatyczny backup"""
        if not self.config.auto_backup:
            return
        
        self._running = True
        self._backup_task = asyncio.create_task(self._auto_backup_loop())
        self.logger.info(f"⏰ Auto-backup uruchomiony (co {self.config.interval_hours}h)")
    
    async def stop_auto_backup(self):
        """Zatrzymuje automatyczny backup"""
        self._running = False
        if self._backup_task:
            self._backup_task.cancel()
    
    async def _auto_backup_loop(self):
        """Loop automatycznego backupu"""
        interval = self.config.interval_hours * 3600
        
        while self._running:
            try:
                await asyncio.sleep(interval)
                await self.create_backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Błąd auto-backup: {e}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # QUERIES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def list_backups(self) -> List[BackupInfo]:
        """Lista backupów"""
        return sorted(self._history, key=lambda b: b.created_at, reverse=True)
    
    def get_backup(self, backup_id: str) -> Optional[BackupInfo]:
        """Pobiera backup po ID"""
        for b in self._history:
            if b.id == backup_id:
                return b
        return None
    
    def get_latest_backup(self) -> Optional[BackupInfo]:
        """Pobiera najnowszy backup"""
        if not self._history:
            return None
        return max(self._history, key=lambda b: b.created_at)
    
    def get_stats(self) -> Dict[str, Any]:
        """Statystyki backupów"""
        total_size = sum(b.size for b in self._history)
        
        return {
            "total_backups": len(self._history),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "latest": self.get_latest_backup().to_dict() if self._history else None,
            "auto_backup_enabled": self.config.auto_backup,
            "interval_hours": self.config.interval_hours,
            "versions_to_keep": self.config.versions_to_keep
        }
