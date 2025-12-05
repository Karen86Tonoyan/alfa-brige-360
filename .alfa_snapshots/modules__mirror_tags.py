"""
ALFA MIRROR — TAGS
System tagowania sesji.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ALFA.Mirror.Tags")

TAG_FILE = Path("storage/tags.json")


class TagManager:
    """
    Manager tagów dla sesji archiwum.
    """
    
    def __init__(self, tag_file: Optional[Path] = None):
        self.tag_file = tag_file or TAG_FILE
        self.tags: Dict[str, List[str]] = {}
        self._load()
    
    def _load(self) -> None:
        """Ładuje tagi z pliku."""
        if self.tag_file.exists():
            try:
                self.tags = json.loads(self.tag_file.read_text(encoding="utf8"))
                logger.debug(f"Loaded {len(self.tags)} tags")
            except Exception as e:
                logger.error(f"Failed to load tags: {e}")
                self.tags = {}
        else:
            self.tags = {}
    
    def _save(self) -> None:
        """Zapisuje tagi do pliku."""
        try:
            self.tag_file.parent.mkdir(parents=True, exist_ok=True)
            self.tag_file.write_text(
                json.dumps(self.tags, indent=4, ensure_ascii=False),
                encoding="utf8"
            )
        except Exception as e:
            logger.error(f"Failed to save tags: {e}")
    
    def tag(self, session: str, tag: str) -> None:
        """
        Dodaje tag do sesji.
        
        Args:
            session: ID sesji
            tag: Nazwa tagu
        """
        tag = tag.lower().strip()
        if not tag:
            return
        
        self.tags.setdefault(tag, [])
        if session not in self.tags[tag]:
            self.tags[tag].append(session)
            self._save()
            logger.debug(f"Tagged {session} with '{tag}'")
    
    def untag(self, session: str, tag: str) -> bool:
        """
        Usuwa tag z sesji.
        
        Returns:
            True jeśli usunięto
        """
        tag = tag.lower().strip()
        if tag in self.tags and session in self.tags[tag]:
            self.tags[tag].remove(session)
            if not self.tags[tag]:
                del self.tags[tag]
            self._save()
            return True
        return False
    
    def get(self, tag: str) -> List[str]:
        """
        Pobiera sesje z danym tagiem.
        
        Returns:
            Lista ID sesji
        """
        return self.tags.get(tag.lower().strip(), [])
    
    def get_session_tags(self, session: str) -> List[str]:
        """
        Pobiera tagi dla sesji.
        
        Returns:
            Lista tagów
        """
        return [tag for tag, sessions in self.tags.items() if session in sessions]
    
    def list_tags(self) -> List[Dict[str, Any]]:
        """
        Lista wszystkich tagów z liczbą sesji.
        
        Returns:
            Lista tagów z metadanymi
        """
        return [
            {"tag": tag, "count": len(sessions)}
            for tag, sessions in sorted(self.tags.items())
        ]
    
    def delete_tag(self, tag: str) -> bool:
        """Usuwa cały tag."""
        tag = tag.lower().strip()
        if tag in self.tags:
            del self.tags[tag]
            self._save()
            return True
        return False
    
    def clear_session(self, session: str) -> int:
        """
        Usuwa wszystkie tagi z sesji.
        
        Returns:
            Liczba usuniętych tagów
        """
        removed = 0
        for tag in list(self.tags.keys()):
            if session in self.tags[tag]:
                self.tags[tag].remove(session)
                removed += 1
                if not self.tags[tag]:
                    del self.tags[tag]
        
        if removed:
            self._save()
        return removed
    
    def status(self) -> Dict[str, Any]:
        """Status managera tagów."""
        total_sessions = set()
        for sessions in self.tags.values():
            total_sessions.update(sessions)
        
        return {
            "total_tags": len(self.tags),
            "tagged_sessions": len(total_sessions),
            "tag_file": str(self.tag_file),
        }


# Auto-tagger (AI-based)

class AutoTagger:
    """
    Automatyczne tagowanie sesji przez AI.
    """
    
    def __init__(self, provider, tag_manager: TagManager):
        """
        Args:
            provider: Provider LLM (Gemini/DeepSeek)
            tag_manager: TagManager instance
        """
        self.provider = provider
        self.tag_manager = tag_manager
    
    def suggest_tags(self, text: str) -> List[str]:
        """
        Sugeruje tagi na podstawie tekstu.
        
        Returns:
            Lista sugerowanych tagów
        """
        prompt = (
            "Na podstawie poniższego tekstu wypisz 3–7 krótkich tagów "
            "(jedno lub dwa słowa, po polsku), rozdzielonych przecinkami. "
            "Nie dodawaj żadnych wyjaśnień.\n\n" + text[:3000]
        )
        
        try:
            response = self.provider.generate(prompt)
            tags = [t.strip().lower() for t in response.split(",") if t.strip()]
            return tags[:7]
        except Exception as e:
            logger.error(f"AutoTagger error: {e}")
            return []
    
    def autotag_session(self, session: str) -> List[str]:
        """
        Automatycznie taguje sesję.
        
        Args:
            session: ID sesji
            
        Returns:
            Lista dodanych tagów
        """
        from pathlib import Path
        
        ARCHIVE_DIR = Path("storage/gemini_mirror")
        session_dir = ARCHIVE_DIR / session
        
        if not session_dir.exists():
            return []
        
        # Collect text from session
        texts = []
        
        # Summary first
        summary_file = session_dir / "summary.md"
        if summary_file.exists():
            texts.append(summary_file.read_text(encoding="utf8"))
        
        # Then text files
        for text_file in session_dir.glob("text_*.md"):
            texts.append(text_file.read_text(encoding="utf8"))
        
        if not texts:
            return []
        
        full_text = "\n\n".join(texts)
        tags = self.suggest_tags(full_text)
        
        # Apply tags
        for tag in tags:
            self.tag_manager.tag(session, tag)
        
        logger.info(f"AutoTagged {session}: {tags}")
        return tags
