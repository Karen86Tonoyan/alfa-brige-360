"""
📁 FILE AGENT
Agent zarządzania plikami dla ALFA CLOUD
"""

from __future__ import annotations
import os
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Callable
import logging
import asyncio

from alfa_cloud.core.event_bus import EventBus


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA CLASSES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class FileInfo:
    """Informacje o pliku"""
    path: str
    name: str
    size: int
    hash: str
    created_at: datetime
    modified_at: datetime
    is_dir: bool = False
    extension: str = ""
    
    @classmethod
    def from_path(cls, path: Path) -> 'FileInfo':
        """Tworzy FileInfo z ścieżki"""
        stat = path.stat()
        
        hash_value = ""
        if path.is_file():
            hash_value = hashlib.blake2b(path.read_bytes()).hexdigest()[:32]
        
        return cls(
            path=str(path),
            name=path.name,
            size=stat.st_size,
            hash=hash_value,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            is_dir=path.is_dir(),
            extension=path.suffix.lower()
        )


@dataclass 
class FileOperation:
    """Operacja na pliku"""
    operation: str  # copy, move, delete, rename
    source: str
    destination: Optional[str] = None
    timestamp: datetime = None
    success: bool = False
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FILE AGENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FileAgent:
    """
    📁 Agent zarządzania plikami
    
    Funkcje:
    - Operacje CRUD na plikach
    - Organizacja (sortowanie, grupowanie)
    - Wyszukiwanie
    - Monitorowanie zmian
    - Automatyczne akcje
    """
    
    def __init__(self, 
                 storage_path: str,
                 event_bus: Optional[EventBus] = None):
        self.storage_path = Path(storage_path)
        self.event_bus = event_bus or EventBus()
        self.logger = logging.getLogger("ALFA_CLOUD.FileAgent")
        
        # Historia operacji
        self.history: List[FileOperation] = []
        
        # Watchers
        self._watch_callbacks: Dict[str, List[Callable]] = {}
        self._watching = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CRUD OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def list_files(self, 
                   path: Optional[str] = None,
                   pattern: str = "*",
                   recursive: bool = False) -> List[FileInfo]:
        """Lista plików w katalogu"""
        search_path = Path(path) if path else self.storage_path
        
        if not search_path.exists():
            return []
        
        files = []
        if recursive:
            for file_path in search_path.rglob(pattern):
                files.append(FileInfo.from_path(file_path))
        else:
            for file_path in search_path.glob(pattern):
                files.append(FileInfo.from_path(file_path))
        
        return sorted(files, key=lambda f: f.name)
    
    def get_file(self, path: str) -> Optional[FileInfo]:
        """Pobiera informacje o pliku"""
        file_path = Path(path)
        if file_path.exists():
            return FileInfo.from_path(file_path)
        return None
    
    def copy_file(self, source: str, destination: str) -> FileOperation:
        """Kopiuje plik"""
        op = FileOperation(operation="copy", source=source, destination=destination)
        
        try:
            src = Path(source)
            dst = Path(destination)
            
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            
            op.success = True
            self.logger.info(f"📋 Skopiowano: {src.name} → {dst.name}")
            self.event_bus.emit("file:copied", {"source": source, "destination": destination})
            
        except Exception as e:
            op.error = str(e)
            self.logger.error(f"❌ Błąd kopiowania: {e}")
        
        self.history.append(op)
        return op
    
    def move_file(self, source: str, destination: str) -> FileOperation:
        """Przenosi plik"""
        op = FileOperation(operation="move", source=source, destination=destination)
        
        try:
            src = Path(source)
            dst = Path(destination)
            
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            
            op.success = True
            self.logger.info(f"📦 Przeniesiono: {src.name} → {dst.name}")
            self.event_bus.emit("file:moved", {"source": source, "destination": destination})
            
        except Exception as e:
            op.error = str(e)
            self.logger.error(f"❌ Błąd przenoszenia: {e}")
        
        self.history.append(op)
        return op
    
    def delete_file(self, path: str, permanent: bool = False) -> FileOperation:
        """Usuwa plik (lub do kosza)"""
        op = FileOperation(operation="delete", source=path)
        
        try:
            file_path = Path(path)
            
            if permanent:
                if file_path.is_dir():
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()
            else:
                # Przenieś do kosza
                trash_path = self.storage_path / ".trash" / file_path.name
                trash_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(file_path, trash_path)
                op.destination = str(trash_path)
            
            op.success = True
            self.logger.info(f"🗑️ Usunięto: {file_path.name}")
            self.event_bus.emit("file:deleted", {"path": path, "permanent": permanent})
            
        except Exception as e:
            op.error = str(e)
            self.logger.error(f"❌ Błąd usuwania: {e}")
        
        self.history.append(op)
        return op
    
    def rename_file(self, path: str, new_name: str) -> FileOperation:
        """Zmienia nazwę pliku"""
        file_path = Path(path)
        new_path = file_path.parent / new_name
        
        return self.move_file(path, str(new_path))
    
    def create_folder(self, path: str) -> bool:
        """Tworzy folder"""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            self.logger.info(f"📁 Utworzono folder: {path}")
            self.event_bus.emit("folder:created", {"path": path})
            return True
        except Exception as e:
            self.logger.error(f"❌ Błąd tworzenia folderu: {e}")
            return False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SEARCH
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def search(self, 
               query: str,
               path: Optional[str] = None,
               extensions: Optional[List[str]] = None,
               min_size: Optional[int] = None,
               max_size: Optional[int] = None,
               modified_after: Optional[datetime] = None) -> List[FileInfo]:
        """
        Wyszukuje pliki
        
        Args:
            query: Szukany tekst w nazwie
            path: Ścieżka do przeszukania
            extensions: Lista rozszerzeń (np. ['.txt', '.pdf'])
            min_size: Minimalny rozmiar w bajtach
            max_size: Maksymalny rozmiar
            modified_after: Zmodyfikowane po dacie
        """
        all_files = self.list_files(path, "*", recursive=True)
        results = []
        
        for file_info in all_files:
            # Filtruj po nazwie
            if query.lower() not in file_info.name.lower():
                continue
            
            # Filtruj po rozszerzeniu
            if extensions and file_info.extension not in extensions:
                continue
            
            # Filtruj po rozmiarze
            if min_size and file_info.size < min_size:
                continue
            if max_size and file_info.size > max_size:
                continue
            
            # Filtruj po dacie
            if modified_after and file_info.modified_at < modified_after:
                continue
            
            results.append(file_info)
        
        return results
    
    def find_duplicates(self, path: Optional[str] = None) -> Dict[str, List[str]]:
        """Znajduje duplikaty plików (po hashu)"""
        files = self.list_files(path, "*", recursive=True)
        
        hash_map: Dict[str, List[str]] = {}
        for f in files:
            if not f.is_dir and f.hash:
                if f.hash not in hash_map:
                    hash_map[f.hash] = []
                hash_map[f.hash].append(f.path)
        
        # Zwróć tylko duplikaty
        return {h: paths for h, paths in hash_map.items() if len(paths) > 1}
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ORGANIZATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def organize_by_extension(self, 
                              source_path: str,
                              dest_path: Optional[str] = None) -> Dict[str, int]:
        """
        Organizuje pliki według rozszerzenia
        
        Tworzy foldery: images/, documents/, videos/, audio/, other/
        """
        ext_map = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'],
            'documents': ['.pdf', '.doc', '.docx', '.txt', '.md', '.xls', '.xlsx', '.ppt', '.pptx'],
            'videos': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv'],
            'audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'],
            'code': ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.html', '.css', '.json'],
            'archives': ['.zip', '.rar', '.7z', '.tar', '.gz']
        }
        
        dest = Path(dest_path) if dest_path else Path(source_path)
        files = self.list_files(source_path, "*", recursive=False)
        
        moved = {}
        
        for file_info in files:
            if file_info.is_dir:
                continue
            
            # Znajdź kategorię
            category = 'other'
            for cat, exts in ext_map.items():
                if file_info.extension in exts:
                    category = cat
                    break
            
            # Przenieś
            target_dir = dest / category
            target_dir.mkdir(parents=True, exist_ok=True)
            
            self.move_file(file_info.path, str(target_dir / file_info.name))
            
            if category not in moved:
                moved[category] = 0
            moved[category] += 1
        
        return moved
    
    def organize_by_date(self,
                         source_path: str,
                         dest_path: Optional[str] = None,
                         format: str = "%Y/%m") -> Dict[str, int]:
        """
        Organizuje pliki według daty modyfikacji
        
        Tworzy foldery: 2024/01/, 2024/02/, itd.
        """
        dest = Path(dest_path) if dest_path else Path(source_path)
        files = self.list_files(source_path, "*", recursive=False)
        
        moved = {}
        
        for file_info in files:
            if file_info.is_dir:
                continue
            
            # Folder według daty
            date_folder = file_info.modified_at.strftime(format)
            target_dir = dest / date_folder
            target_dir.mkdir(parents=True, exist_ok=True)
            
            self.move_file(file_info.path, str(target_dir / file_info.name))
            
            if date_folder not in moved:
                moved[date_folder] = 0
            moved[date_folder] += 1
        
        return moved
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STATS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def get_stats(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Statystyki storage"""
        files = self.list_files(path, "*", recursive=True)
        
        total_size = sum(f.size for f in files if not f.is_dir)
        file_count = sum(1 for f in files if not f.is_dir)
        dir_count = sum(1 for f in files if f.is_dir)
        
        # Rozmiar według rozszerzenia
        size_by_ext = {}
        for f in files:
            if not f.is_dir:
                ext = f.extension or 'no_extension'
                if ext not in size_by_ext:
                    size_by_ext[ext] = 0
                size_by_ext[ext] += f.size
        
        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count,
            "folder_count": dir_count,
            "size_by_extension": size_by_ext,
            "largest_files": sorted(files, key=lambda f: f.size, reverse=True)[:10]
        }
    
    def empty_trash(self) -> int:
        """Opróżnia kosz"""
        trash_path = self.storage_path / ".trash"
        if not trash_path.exists():
            return 0
        
        count = 0
        for item in trash_path.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            count += 1
        
        self.logger.info(f"🗑️ Opróżniono kosz: {count} elementów")
        return count
