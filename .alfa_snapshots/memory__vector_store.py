"""
ALFA MEMORY v1 — VECTOR STORE
Prosty vector store dla semantic search.
"""

from typing import Optional, Dict, Any, List, Tuple
import logging
import json
import math
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger("ALFA.VectorStore")


@dataclass
class VectorEntry:
    """Pojedynczy wpis z wektorem."""
    id: str
    text: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Oblicza cosine similarity między wektorami."""
    if len(v1) != len(v2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


def simple_embedding(text: str, dim: int = 64) -> List[float]:
    """
    Proste embeddowanie tekstu (fallback gdy brak modelu).
    Używa character-level features.
    """
    text = text.lower().strip()
    if not text:
        return [0.0] * dim
    
    # Character frequency features
    vector = [0.0] * dim
    
    for i, char in enumerate(text):
        idx = ord(char) % dim
        vector[idx] += 1.0 / (i + 1)  # Weighted by position
    
    # Word-level features
    words = text.split()
    for i, word in enumerate(words):
        idx = (hash(word) % (dim // 2)) + (dim // 2)
        vector[idx] += 1.0 / (len(words) + 1)
    
    # Normalize
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
    
    return vector


class VectorStore:
    """
    Prosty Vector Store dla semantic search.
    Używa prostego embeddingu gdy brak zewnętrznego modelu.
    """
    
    def __init__(
        self,
        persist_path: Optional[str] = None,
        embedding_dim: int = 64,
        embedding_fn: Optional[callable] = None
    ):
        """
        Args:
            persist_path: Ścieżka do zapisu
            embedding_dim: Wymiar wektora
            embedding_fn: Funkcja embeddingu (opcjonalna)
        """
        self.persist_path = Path(persist_path) if persist_path else None
        self.embedding_dim = embedding_dim
        self.embedding_fn = embedding_fn or (lambda t: simple_embedding(t, embedding_dim))
        
        self._entries: Dict[str, VectorEntry] = {}
        self._id_counter = 0
        
        # Load persisted data
        if self.persist_path and self.persist_path.exists():
            self._load()
        
        logger.info(f"VectorStore initialized (dim: {embedding_dim})")
    
    def _generate_id(self) -> str:
        """Generuje unikalny ID."""
        self._id_counter += 1
        return f"vec_{self._id_counter}"
    
    def add(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        entry_id: Optional[str] = None
    ) -> str:
        """
        Dodaje tekst do store.
        
        Args:
            text: Tekst do dodania
            metadata: Metadane
            entry_id: Opcjonalny ID
            
        Returns:
            ID wpisu
        """
        entry_id = entry_id or self._generate_id()
        vector = self.embedding_fn(text)
        
        self._entries[entry_id] = VectorEntry(
            id=entry_id,
            text=text,
            vector=vector,
            metadata=metadata or {}
        )
        
        if self.persist_path:
            self._save()
        
        logger.debug(f"Added vector: {entry_id}")
        return entry_id
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0
    ) -> List[Tuple[str, float, str]]:
        """
        Wyszukuje podobne teksty.
        
        Args:
            query: Zapytanie
            top_k: Liczba wyników
            min_score: Minimalny score
            
        Returns:
            Lista (id, score, text)
        """
        if not self._entries:
            return []
        
        query_vector = self.embedding_fn(query)
        
        # Calculate similarities
        scores = []
        for entry_id, entry in self._entries.items():
            score = cosine_similarity(query_vector, entry.vector)
            if score >= min_score:
                scores.append((entry_id, score, entry.text))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores[:top_k]
    
    def get(self, entry_id: str) -> Optional[VectorEntry]:
        """Pobiera wpis po ID."""
        return self._entries.get(entry_id)
    
    def delete(self, entry_id: str) -> bool:
        """Usuwa wpis."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            if self.persist_path:
                self._save()
            return True
        return False
    
    def clear(self) -> int:
        """Czyści store."""
        count = len(self._entries)
        self._entries.clear()
        if self.persist_path:
            self._save()
        logger.info(f"VectorStore cleared ({count} entries)")
        return count
    
    def _save(self) -> None:
        """Zapisuje do pliku."""
        if not self.persist_path:
            return
        
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "id_counter": self._id_counter,
                "entries": {
                    eid: {
                        "text": e.text,
                        "vector": e.vector,
                        "metadata": e.metadata
                    }
                    for eid, e in self._entries.items()
                }
            }
            
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save VectorStore: {e}")
    
    def _load(self) -> None:
        """Ładuje z pliku."""
        if not self.persist_path or not self.persist_path.exists():
            return
        
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._id_counter = data.get("id_counter", 0)
            
            for eid, entry_data in data.get("entries", {}).items():
                self._entries[eid] = VectorEntry(
                    id=eid,
                    text=entry_data["text"],
                    vector=entry_data["vector"],
                    metadata=entry_data.get("metadata", {})
                )
            
            logger.info(f"Loaded {len(self._entries)} vectors")
            
        except Exception as e:
            logger.error(f"Failed to load VectorStore: {e}")
    
    def status(self) -> Dict[str, Any]:
        """Status store."""
        return {
            "total_entries": len(self._entries),
            "embedding_dim": self.embedding_dim,
            "persist_enabled": self.persist_path is not None
        }
