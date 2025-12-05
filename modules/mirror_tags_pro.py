"""
ALFA_MIRROR PRO — PERSISTENT TAG MANAGER
System tagów z JSON persistence + Cerber integration.
Poziom: KERNEL-READY
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict
import threading

logger = logging.getLogger("ALFA.Mirror.Tags")


# ═══════════════════════════════════════════════════════════════════════════
# KONFIGURACJA
# ═══════════════════════════════════════════════════════════════════════════

ARCHIVE_DIR = Path("storage/gemini_mirror")
TAG_FILE = ARCHIVE_DIR / "tags.json"
TAG_HISTORY_FILE = ARCHIVE_DIR / "tags_history.json"


# ═══════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TagEntry:
    """Pojedynczy wpis tagu."""
    session: str
    tag: str
    created_at: str
    created_by: str = "system"  # system, user, ai


@dataclass
class TagStats:
    """Statystyki tagów."""
    total_tags: int
    unique_tags: int
    sessions_tagged: int
    most_used: List[tuple]
    recent_tags: List[str]


# ═══════════════════════════════════════════════════════════════════════════
# TAG MANAGER — PERSISTENT
# ═══════════════════════════════════════════════════════════════════════════

class TagManager:
    """
    Zarządza tagami sesji z pełną persistencją.
    
    Features:
    - JSON persistence (przetrwa restart)
    - Thread-safe operacje
    - Historia zmian
    - Statystyki
    - Walidacja tagów
    """
    
    # Zakazane tagi (Cerber)
    FORBIDDEN_TAGS = {
        "nsfw", "porn", "xxx", "illegal", "violence", "hate",
        "racist", "nazi", "terrorism", "drugs", "weapons"
    }
    
    # Max długość tagu
    MAX_TAG_LENGTH = 50
    
    def __init__(self, tag_file: Optional[Path] = None):
        """
        Args:
            tag_file: Ścieżka do pliku JSON (domyślnie TAG_FILE)
        """
        self.tag_file = Path(tag_file) if tag_file else TAG_FILE
        self.history_file = self.tag_file.parent / "tags_history.json"
        
        self._lock = threading.RLock()
        
        # Struktura: {tag: [session1, session2, ...]}
        self.tags: Dict[str, List[str]] = {}
        
        # Reverse index: {session: [tag1, tag2, ...]}
        self._session_tags: Dict[str, List[str]] = {}
        
        # Historia zmian
        self._history: List[dict] = []
        
        # Load existing data
        self._load()
    
    def _load(self) -> None:
        """Ładuje tagi z pliku JSON."""
        with self._lock:
            if self.tag_file.exists():
                try:
                    data = json.loads(self.tag_file.read_text(encoding="utf8"))
                    self.tags = data.get("tags", {})
                    self._rebuild_reverse_index()
                    logger.info(f"Loaded {len(self.tags)} tags from {self.tag_file}")
                except Exception as e:
                    logger.error(f"Cannot load tags: {e}")
                    self.tags = {}
            else:
                self.tags = {}
                self._ensure_dir()
    
    def _save(self) -> None:
        """Zapisuje tagi do pliku JSON."""
        with self._lock:
            self._ensure_dir()
            
            data = {
                "tags": self.tags,
                "updated_at": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            self.tag_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf8"
            )
    
    def _ensure_dir(self) -> None:
        """Tworzy folder jeśli nie istnieje."""
        self.tag_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _rebuild_reverse_index(self) -> None:
        """Przebudowuje reverse index session → tags."""
        self._session_tags = {}
        for tag, sessions in self.tags.items():
            for session in sessions:
                if session not in self._session_tags:
                    self._session_tags[session] = []
                self._session_tags[session].append(tag)
    
    def _validate_tag(self, tag: str) -> str:
        """
        Waliduje i normalizuje tag.
        
        Raises:
            ValueError: Gdy tag jest nieprawidłowy lub zakazany
        """
        # Normalizacja
        tag = tag.strip().lower()
        
        # Usuń niebezpieczne znaki
        tag = "".join(c for c in tag if c.isalnum() or c in "-_")
        
        if not tag:
            raise ValueError("Tag cannot be empty")
        
        if len(tag) > self.MAX_TAG_LENGTH:
            raise ValueError(f"Tag too long (max {self.MAX_TAG_LENGTH})")
        
        # Cerber check
        if tag in self.FORBIDDEN_TAGS:
            logger.warning(f"🛡️ CERBER: Blocked forbidden tag: {tag}")
            raise ValueError(f"Tag '{tag}' is forbidden by Cerber")
        
        return tag
    
    def _log_history(self, action: str, session: str, tag: str, by: str = "system") -> None:
        """Loguje zmianę do historii."""
        entry = {
            "action": action,
            "session": session,
            "tag": tag,
            "by": by,
            "timestamp": datetime.now().isoformat()
        }
        self._history.append(entry)
        
        # Limit historii
        if len(self._history) > 1000:
            self._history = self._history[-500:]
    
    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════
    
    def tag(
        self,
        session: str,
        tag: str,
        created_by: str = "system"
    ) -> bool:
        """
        Dodaje tag do sesji.
        
        Args:
            session: ID sesji
            tag: Nazwa tagu
            created_by: Kto dodał tag (system, user, ai)
            
        Returns:
            True jeśli dodano, False jeśli już istniał
            
        Raises:
            ValueError: Gdy tag jest nieprawidłowy
        """
        tag = self._validate_tag(tag)
        
        with self._lock:
            if tag not in self.tags:
                self.tags[tag] = []
            
            if session in self.tags[tag]:
                return False  # Already tagged
            
            self.tags[tag].append(session)
            
            # Update reverse index
            if session not in self._session_tags:
                self._session_tags[session] = []
            self._session_tags[session].append(tag)
            
            self._log_history("add", session, tag, created_by)
            self._save()
            
            logger.info(f"✅ Tagged '{session}' with '{tag}'")
            return True
    
    def untag(self, session: str, tag: str) -> bool:
        """
        Usuwa tag z sesji.
        
        Returns:
            True jeśli usunięto, False jeśli nie było
        """
        tag = tag.strip().lower()
        
        with self._lock:
            if tag not in self.tags:
                return False
            
            if session not in self.tags[tag]:
                return False
            
            self.tags[tag].remove(session)
            
            # Usuń pusty tag
            if not self.tags[tag]:
                del self.tags[tag]
            
            # Update reverse index
            if session in self._session_tags:
                if tag in self._session_tags[session]:
                    self._session_tags[session].remove(tag)
            
            self._log_history("remove", session, tag)
            self._save()
            
            logger.info(f"🗑️ Removed tag '{tag}' from '{session}'")
            return True
    
    def get_tags(self, session: str) -> List[str]:
        """Pobiera wszystkie tagi sesji."""
        with self._lock:
            return self._session_tags.get(session, []).copy()
    
    def get_by_tag(self, tag: str) -> List[str]:
        """Pobiera wszystkie sesje z danym tagiem."""
        tag = tag.strip().lower()
        with self._lock:
            return self.tags.get(tag, []).copy()
    
    def get_all_tags(self) -> List[str]:
        """Pobiera listę wszystkich tagów."""
        with self._lock:
            return sorted(self.tags.keys())
    
    def search_tags(self, query: str) -> List[str]:
        """Wyszukuje tagi pasujące do zapytania."""
        query = query.strip().lower()
        with self._lock:
            return [t for t in self.tags.keys() if query in t]
    
    def bulk_tag(
        self,
        session: str,
        tags: List[str],
        created_by: str = "system"
    ) -> Dict[str, bool]:
        """
        Dodaje wiele tagów naraz.
        
        Returns:
            Dict: {tag: success}
        """
        results = {}
        for tag in tags:
            try:
                results[tag] = self.tag(session, tag, created_by)
            except ValueError as e:
                results[tag] = False
                logger.warning(f"Invalid tag '{tag}': {e}")
        return results
    
    def rename_tag(self, old_tag: str, new_tag: str) -> int:
        """
        Zmienia nazwę tagu.
        
        Returns:
            Liczba zmienionych sesji
        """
        old_tag = old_tag.strip().lower()
        new_tag = self._validate_tag(new_tag)
        
        with self._lock:
            if old_tag not in self.tags:
                return 0
            
            sessions = self.tags[old_tag].copy()
            del self.tags[old_tag]
            
            if new_tag not in self.tags:
                self.tags[new_tag] = []
            
            for session in sessions:
                if session not in self.tags[new_tag]:
                    self.tags[new_tag].append(session)
            
            self._rebuild_reverse_index()
            self._save()
            
            logger.info(f"Renamed tag '{old_tag}' → '{new_tag}' ({len(sessions)} sessions)")
            return len(sessions)
    
    def delete_tag(self, tag: str) -> int:
        """
        Usuwa tag całkowicie.
        
        Returns:
            Liczba sesji, z których usunięto tag
        """
        tag = tag.strip().lower()
        
        with self._lock:
            if tag not in self.tags:
                return 0
            
            count = len(self.tags[tag])
            del self.tags[tag]
            
            self._rebuild_reverse_index()
            self._save()
            
            logger.info(f"Deleted tag '{tag}' from {count} sessions")
            return count
    
    def stats(self) -> TagStats:
        """Zwraca statystyki tagów."""
        with self._lock:
            # Most used tags
            most_used = sorted(
                [(t, len(s)) for t, s in self.tags.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            # Recent tags (z historii)
            recent = []
            for entry in reversed(self._history[-20:]):
                if entry["action"] == "add" and entry["tag"] not in recent:
                    recent.append(entry["tag"])
            
            return TagStats(
                total_tags=sum(len(s) for s in self.tags.values()),
                unique_tags=len(self.tags),
                sessions_tagged=len(self._session_tags),
                most_used=most_used,
                recent_tags=recent[:10]
            )
    
    def export(self) -> dict:
        """Eksportuje wszystkie tagi."""
        with self._lock:
            return {
                "tags": self.tags.copy(),
                "session_tags": self._session_tags.copy(),
                "stats": asdict(self.stats()),
                "exported_at": datetime.now().isoformat()
            }
    
    def import_tags(self, data: dict) -> int:
        """
        Importuje tagi z eksportu.
        
        Returns:
            Liczba zaimportowanych tagów
        """
        count = 0
        tags = data.get("tags", {})
        
        for tag, sessions in tags.items():
            for session in sessions:
                try:
                    if self.tag(session, tag, "import"):
                        count += 1
                except:
                    pass
        
        return count


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

_instance: Optional[TagManager] = None


def get_tag_manager() -> TagManager:
    """Pobiera globalną instancję TagManager."""
    global _instance
    if _instance is None:
        _instance = TagManager()
    return _instance


# ═══════════════════════════════════════════════════════════════════════════
# QUICK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def tag_session(session: str, tag: str) -> bool:
    """Quick: Dodaj tag do sesji."""
    return get_tag_manager().tag(session, tag)


def get_session_tags(session: str) -> List[str]:
    """Quick: Pobierz tagi sesji."""
    return get_tag_manager().get_tags(session)


def find_by_tag(tag: str) -> List[str]:
    """Quick: Znajdź sesje z tagiem."""
    return get_tag_manager().get_by_tag(tag)


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n" + "═" * 50)
    print("🏷️  ALFA TAG MANAGER TEST")
    print("═" * 50)
    
    tm = TagManager(Path("test_tags.json"))
    
    # Test tagging
    tm.tag("session_001", "projekt-alfa")
    tm.tag("session_001", "python")
    tm.tag("session_001", "gemini")
    tm.tag("session_002", "projekt-alfa")
    tm.tag("session_002", "video")
    
    print(f"\nTagi session_001: {tm.get_tags('session_001')}")
    print(f"Sesje z 'projekt-alfa': {tm.get_by_tag('projekt-alfa')}")
    print(f"Wszystkie tagi: {tm.get_all_tags()}")
    
    # Stats
    stats = tm.stats()
    print(f"\nStatystyki:")
    print(f"  Total tags: {stats.total_tags}")
    print(f"  Unique tags: {stats.unique_tags}")
    print(f"  Most used: {stats.most_used}")
    
    # Test forbidden tag
    print("\n🛡️ Testing Cerber protection...")
    try:
        tm.tag("session_003", "nsfw")
    except ValueError as e:
        print(f"  ✅ Blocked: {e}")
    
    # Cleanup
    Path("test_tags.json").unlink(missing_ok=True)
    print("\n✅ Test complete!")
