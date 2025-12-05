"""
ALFA MEMORY v1 — KEY-VALUE STORE
Prosty store klucz-wartość z TTL.
"""

from typing import Optional, Dict, Any
import logging
import time
import json
import threading
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("ALFA.KVStore")


@dataclass
class KVEntry:
    """Pojedynczy wpis KV."""
    key: str
    value: Any
    created_at: float
    expires_at: Optional[float] = None
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class KVStore:
    """
    Key-Value Store z TTL i persistence.
    """
    
    def __init__(
        self,
        persist_path: Optional[str] = None,
        default_ttl: Optional[float] = None
    ):
        """
        Args:
            persist_path: Ścieżka do zapisu
            default_ttl: Domyślny TTL w sekundach
        """
        self.persist_path = Path(persist_path) if persist_path else None
        self.default_ttl = default_ttl
        
        self._store: Dict[str, KVEntry] = {}
        self._lock = threading.RLock()
        
        # Load persisted data
        if self.persist_path and self.persist_path.exists():
            self._load()
        
        logger.info("KVStore initialized")
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None
    ) -> None:
        """
        Ustawia wartość.
        
        Args:
            key: Klucz
            value: Wartość
            ttl: Time-to-live w sekundach (None = bez limitu)
        """
        with self._lock:
            ttl = ttl or self.default_ttl
            expires_at = time.time() + ttl if ttl else None
            
            self._store[key] = KVEntry(
                key=key,
                value=value,
                created_at=time.time(),
                expires_at=expires_at
            )
            
            if self.persist_path:
                self._save()
        
        logger.debug(f"Set key: {key}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Pobiera wartość.
        
        Args:
            key: Klucz
            default: Wartość domyślna
            
        Returns:
            Wartość lub default
        """
        with self._lock:
            entry = self._store.get(key)
            
            if entry is None:
                return default
            
            if entry.is_expired():
                del self._store[key]
                return default
            
            return entry.value
    
    def delete(self, key: str) -> bool:
        """Usuwa klucz."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                if self.persist_path:
                    self._save()
                logger.debug(f"Deleted key: {key}")
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """Sprawdza czy klucz istnieje."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._store[key]
                return False
            return True
    
    def keys(self, pattern: Optional[str] = None) -> list:
        """Lista kluczy."""
        with self._lock:
            self._cleanup_expired()
            
            if pattern:
                import fnmatch
                return [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]
            
            return list(self._store.keys())
    
    def clear(self) -> int:
        """Czyści store."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            if self.persist_path:
                self._save()
            logger.info(f"KVStore cleared ({count} entries)")
            return count
    
    def _cleanup_expired(self) -> int:
        """Usuwa wygasłe wpisy."""
        expired = [
            key for key, entry in self._store.items()
            if entry.is_expired()
        ]
        for key in expired:
            del self._store[key]
        return len(expired)
    
    def _save(self) -> None:
        """Zapisuje do pliku."""
        if not self.persist_path:
            return
        
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {}
            for key, entry in self._store.items():
                if not entry.is_expired():
                    data[key] = {
                        "value": entry.value,
                        "created_at": entry.created_at,
                        "expires_at": entry.expires_at
                    }
            
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save KVStore: {e}")
    
    def _load(self) -> None:
        """Ładuje z pliku."""
        if not self.persist_path or not self.persist_path.exists():
            return
        
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for key, entry_data in data.items():
                self._store[key] = KVEntry(
                    key=key,
                    value=entry_data["value"],
                    created_at=entry_data.get("created_at", time.time()),
                    expires_at=entry_data.get("expires_at")
                )
            
            # Cleanup expired
            self._cleanup_expired()
            
            logger.info(f"Loaded {len(self._store)} entries from KVStore")
            
        except Exception as e:
            logger.error(f"Failed to load KVStore: {e}")
    
    def status(self) -> Dict[str, Any]:
        """Status store."""
        with self._lock:
            self._cleanup_expired()
            return {
                "total_entries": len(self._store),
                "persist_enabled": self.persist_path is not None,
                "default_ttl": self.default_ttl
            }
