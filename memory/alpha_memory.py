"""
ALFA MEMORY v1 — ALPHA MEMORY
Główny moduł pamięci konwersacyjnej.
"""

from typing import Optional, Dict, Any, List
import logging
import time
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger("ALFA.Memory")


@dataclass
class MemoryEntry:
    """Pojedynczy wpis w pamięci."""
    role: str  # user, assistant, system
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        return cls(**data)


class AlphaMemory:
    """
    ALFA MEMORY — Pamięć konwersacyjna z historią.
    """
    
    def __init__(
        self,
        max_entries: int = 100,
        persist_path: Optional[str] = None
    ):
        """
        Args:
            max_entries: Maksymalna liczba wpisów
            persist_path: Ścieżka do zapisu (opcjonalne)
        """
        self.max_entries = max_entries
        self.persist_path = Path(persist_path) if persist_path else None
        
        self._entries: List[MemoryEntry] = []
        self._session_id: str = f"session_{int(time.time())}"
        
        # Load persisted memory
        if self.persist_path and self.persist_path.exists():
            self._load()
        
        logger.info(f"AlphaMemory initialized (max: {max_entries})")
    
    def add(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEntry:
        """
        Dodaje wpis do pamięci.
        
        Args:
            role: Rola (user/assistant/system)
            content: Treść wiadomości
            metadata: Dodatkowe metadane
            
        Returns:
            Utworzony wpis
        """
        entry = MemoryEntry(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        
        self._entries.append(entry)
        
        # Trim if over limit
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]
        
        # Auto-persist
        if self.persist_path:
            self._save()
        
        logger.debug(f"Added memory entry: {role} ({len(content)} chars)")
        return entry
    
    def get_history(
        self,
        limit: Optional[int] = None,
        role_filter: Optional[str] = None
    ) -> List[MemoryEntry]:
        """
        Pobiera historię wpisów.
        
        Args:
            limit: Maksymalna liczba wpisów
            role_filter: Filtr po roli
            
        Returns:
            Lista wpisów
        """
        entries = self._entries
        
        if role_filter:
            entries = [e for e in entries if e.role == role_filter]
        
        if limit:
            entries = entries[-limit:]
        
        return entries
    
    def get_context(
        self,
        max_tokens: int = 4000,
        format_style: str = "chat"
    ) -> str:
        """
        Pobiera kontekst konwersacji dla LLM.
        
        Args:
            max_tokens: Przybliżony limit tokenów
            format_style: Styl formatowania (chat/raw)
            
        Returns:
            Sformatowany kontekst
        """
        # Estimate ~4 chars per token
        max_chars = max_tokens * 4
        
        context_parts = []
        total_chars = 0
        
        # Iterate backwards to get most recent
        for entry in reversed(self._entries):
            if format_style == "chat":
                part = f"{entry.role}: {entry.content}"
            else:
                part = entry.content
            
            if total_chars + len(part) > max_chars:
                break
            
            context_parts.insert(0, part)
            total_chars += len(part)
        
        return "\n".join(context_parts)
    
    def get_messages(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Pobiera wiadomości w formacie API.
        
        Returns:
            Lista dict z role i content
        """
        entries = self._entries[-limit:] if limit else self._entries
        return [{"role": e.role, "content": e.content} for e in entries]
    
    def search(
        self,
        query: str,
        limit: int = 5
    ) -> List[MemoryEntry]:
        """
        Proste wyszukiwanie w pamięci.
        
        Args:
            query: Fraza do wyszukania
            limit: Maksymalna liczba wyników
            
        Returns:
            Lista pasujących wpisów
        """
        query_lower = query.lower()
        matches = []
        
        for entry in self._entries:
            if query_lower in entry.content.lower():
                matches.append(entry)
        
        return matches[-limit:]
    
    def clear(self) -> int:
        """Czyści pamięć."""
        count = len(self._entries)
        self._entries = []
        
        if self.persist_path:
            self._save()
        
        logger.info(f"Memory cleared ({count} entries)")
        return count
    
    def _save(self) -> None:
        """Zapisuje pamięć do pliku."""
        if not self.persist_path:
            return
        
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "session_id": self._session_id,
                "entries": [e.to_dict() for e in self._entries]
            }
            
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Memory saved to {self.persist_path}")
            
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
    
    def _load(self) -> None:
        """Ładuje pamięć z pliku."""
        if not self.persist_path or not self.persist_path.exists():
            return
        
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._session_id = data.get("session_id", self._session_id)
            self._entries = [
                MemoryEntry.from_dict(e)
                for e in data.get("entries", [])
            ]
            
            logger.info(f"Loaded {len(self._entries)} entries from memory")
            
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
    
    def status(self) -> Dict[str, Any]:
        """Status pamięci."""
        return {
            "session_id": self._session_id,
            "total_entries": len(self._entries),
            "max_entries": self.max_entries,
            "persist_enabled": self.persist_path is not None,
            "roles": {
                role: len([e for e in self._entries if e.role == role])
                for role in set(e.role for e in self._entries)
            }
        }
