"""
ALFA_MIRROR PRO — AUTO-TAGGING AI
Automatyczne tagowanie sesji przez LLM.
Poziom: OPUS-READY
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Protocol, List, Optional
from dataclasses import dataclass

from .mirror_tags_pro import TagManager, get_tag_manager
from .mirror_summary_pro import get_session_summary, build_session_text, ARCHIVE_DIR

logger = logging.getLogger("ALFA.Mirror.AutoTag")


# ═══════════════════════════════════════════════════════════════════════════
# PROTOKÓŁ — TAG LLM
# ═══════════════════════════════════════════════════════════════════════════

class TagLLM(Protocol):
    """Protokół dla AI tagowania."""
    
    def suggest_tags(self, text: str, max_tags: int = 7) -> List[str]:
        """
        Sugeruje tagi na podstawie tekstu.
        
        Args:
            text: Tekst do analizy
            max_tags: Maksymalna liczba tagów
            
        Returns:
            Lista sugerowanych tagów
        """
        ...


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTERY — GEMINI / DEEPSEEK / LOCAL
# ═══════════════════════════════════════════════════════════════════════════

class GeminiTagLLM:
    """Adapter tagowania przez Gemini."""
    
    name = "gemini"
    
    PROMPT_TEMPLATE = """Na podstawie poniższego tekstu wypisz {max_tags} krótkich tagów.
Tagi powinny być:
- 1-3 słowa (najlepiej 1-2)
- Po polsku lub angielsku (terminy techniczne)
- Opisowe i konkretne
- Bez zbędnych słów

Wypisz TYLKO tagi, rozdzielone przecinkami. Nic więcej.

TEKST:
{text}

TAGI:"""
    
    def __init__(self, provider=None):
        self._provider = provider
    
    @property
    def provider(self):
        if self._provider is None:
            from providers.gemini_provider import GeminiProvider
            self._provider = GeminiProvider()
        return self._provider
    
    def suggest_tags(self, text: str, max_tags: int = 7) -> List[str]:
        # Ogranicz tekst
        text = text[:3000] if len(text) > 3000 else text
        
        prompt = self.PROMPT_TEMPLATE.format(
            max_tags=max_tags,
            text=text
        )
        
        try:
            response = self.provider.generate(prompt)
            return self._parse_tags(response, max_tags)
        except Exception as e:
            logger.error(f"Gemini tagging failed: {e}")
            return []
    
    def _parse_tags(self, response: str, max_tags: int) -> List[str]:
        """Parsuje odpowiedź LLM na listę tagów."""
        # Usuń znaki specjalne
        response = response.strip()
        
        # Znajdź tagi (po przecinkach lub nowych liniach)
        raw_tags = re.split(r'[,\n]', response)
        
        tags = []
        for tag in raw_tags:
            # Wyczyść tag
            tag = tag.strip().lower()
            tag = re.sub(r'[^\w\s-]', '', tag)  # Tylko alfanumeryczne
            tag = re.sub(r'\s+', '-', tag)  # Spacje na myślniki
            tag = tag.strip('-')
            
            if tag and len(tag) >= 2 and len(tag) <= 50:
                tags.append(tag)
        
        # Usuń duplikaty, zachowaj kolejność
        seen = set()
        unique = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        
        return unique[:max_tags]


class DeepSeekTagLLM:
    """Adapter tagowania przez DeepSeek."""
    
    name = "deepseek"
    
    def __init__(self, provider=None):
        self._provider = provider
    
    @property
    def provider(self):
        if self._provider is None:
            from providers.deepseek_provider import DeepSeekProvider
            self._provider = DeepSeekProvider()
        return self._provider
    
    def suggest_tags(self, text: str, max_tags: int = 7) -> List[str]:
        text = text[:2000]
        
        prompt = f"List {max_tags} short tags (1-2 words each) for this text, comma-separated:\n\n{text}\n\nTags:"
        
        try:
            response = self.provider.generate(prompt)
            return self._parse_tags(response, max_tags)
        except Exception as e:
            logger.error(f"DeepSeek tagging failed: {e}")
            return []
    
    def _parse_tags(self, response: str, max_tags: int) -> List[str]:
        tags = []
        for tag in re.split(r'[,\n]', response):
            tag = tag.strip().lower()
            tag = re.sub(r'[^\w\s-]', '', tag)
            tag = re.sub(r'\s+', '-', tag)
            if tag and 2 <= len(tag) <= 50:
                tags.append(tag)
        return list(dict.fromkeys(tags))[:max_tags]


class LocalTagLLM:
    """Adapter tagowania przez Ollama."""
    
    name = "local"
    
    def __init__(self, provider=None):
        self._provider = provider
    
    @property
    def provider(self):
        if self._provider is None:
            from providers.local_provider import LocalProvider
            self._provider = LocalProvider()
        return self._provider
    
    def suggest_tags(self, text: str, max_tags: int = 5) -> List[str]:
        text = text[:1500]
        
        prompt = f"Tags for this text ({max_tags} keywords): {text[:500]}"
        
        try:
            response = self.provider.generate(prompt)
            return self._parse_tags(response, max_tags)
        except:
            return []
    
    def _parse_tags(self, response: str, max_tags: int) -> List[str]:
        tags = []
        for tag in re.split(r'[,\n#]', response):
            tag = tag.strip().lower()[:30]
            tag = re.sub(r'[^\w-]', '', tag)
            if tag and len(tag) >= 2:
                tags.append(tag)
        return list(dict.fromkeys(tags))[:max_tags]


# ═══════════════════════════════════════════════════════════════════════════
# HEURYSTYCZNY TAGGER (FALLBACK)
# ═══════════════════════════════════════════════════════════════════════════

class HeuristicTagger:
    """
    Prosty tagger heurystyczny - nie wymaga LLM.
    Używany jako fallback gdy AI niedostępne.
    """
    
    name = "heuristic"
    
    # Słowa kluczowe → tagi
    KEYWORD_MAP = {
        # Programowanie
        "python": "python",
        "javascript": "javascript",
        "typescript": "typescript",
        "java": "java",
        "code": "kod",
        "function": "funkcje",
        "class": "oop",
        "api": "api",
        "database": "bazy-danych",
        "sql": "sql",
        
        # AI/ML
        "machine learning": "ml",
        "deep learning": "deep-learning",
        "neural": "sieci-neuronowe",
        "gemini": "gemini",
        "gpt": "gpt",
        "llm": "llm",
        "model": "modele",
        
        # Media
        "image": "obrazy",
        "video": "wideo",
        "audio": "audio",
        "music": "muzyka",
        
        # Dokumenty
        "pdf": "pdf",
        "document": "dokumenty",
        "report": "raporty",
        
        # Inne
        "error": "błędy",
        "bug": "debug",
        "test": "testy",
        "security": "bezpieczeństwo",
        "config": "konfiguracja",
    }
    
    def suggest_tags(self, text: str, max_tags: int = 5) -> List[str]:
        text_lower = text.lower()
        
        tags = []
        for keyword, tag in self.KEYWORD_MAP.items():
            if keyword in text_lower:
                tags.append(tag)
        
        # Wykryj języki programowania przez rozszerzenia
        if ".py" in text:
            tags.append("python")
        if ".js" in text or ".ts" in text:
            tags.append("javascript")
        if ".java" in text:
            tags.append("java")
        
        # Usuń duplikaty
        tags = list(dict.fromkeys(tags))
        
        return tags[:max_tags]


# ═══════════════════════════════════════════════════════════════════════════
# GŁÓWNA FUNKCJA — AUTOTAG SESSION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AutoTagResult:
    """Wynik auto-tagowania."""
    session: str
    tags: List[str]
    source: str  # 'summary', 'text', 'fallback'
    tagger: str  # 'gemini', 'deepseek', 'local', 'heuristic'
    success: bool


def autotag_session(
    session: str,
    llm: Optional[TagLLM] = None,
    tag_manager: Optional[TagManager] = None,
    use_summary: bool = True,
    fallback_heuristic: bool = True
) -> AutoTagResult:
    """
    Automatycznie taguje sesję.
    
    Algorytm:
    1. Próbuj z summary.md (krótszy, lepszy dla LLM)
    2. Jeśli brak summary → użyj pełnego tekstu
    3. Wyślij do LLM po sugestie tagów
    4. Zapisz tagi przez TagManager
    
    Args:
        session: ID sesji
        llm: Obiekt TagLLM (domyślnie: GeminiTagLLM)
        tag_manager: TagManager (domyślnie: globalny)
        use_summary: Czy preferować summary.md
        fallback_heuristic: Czy użyć heurystyki gdy LLM zawiedzie
        
    Returns:
        AutoTagResult
    """
    if llm is None:
        llm = GeminiTagLLM()
    
    if tag_manager is None:
        tag_manager = get_tag_manager()
    
    session_dir = ARCHIVE_DIR / session
    
    if not session_dir.exists():
        logger.error(f"Session not found: {session}")
        return AutoTagResult(
            session=session,
            tags=[],
            source="none",
            tagger=llm.name if hasattr(llm, 'name') else "unknown",
            success=False
        )
    
    # Pobierz tekst do analizy
    text = ""
    source = "none"
    
    if use_summary:
        summary = get_session_summary(session)
        if summary:
            text = summary
            source = "summary"
    
    if not text:
        text = build_session_text(session_dir)
        source = "text" if text else "none"
    
    if not text.strip():
        logger.warning(f"No text content in session {session}")
        return AutoTagResult(
            session=session,
            tags=[],
            source=source,
            tagger="none",
            success=False
        )
    
    # Spróbuj LLM
    tags = []
    tagger_name = getattr(llm, 'name', 'unknown')
    
    try:
        tags = llm.suggest_tags(text)
        logger.info(f"LLM suggested {len(tags)} tags for {session}")
    except Exception as e:
        logger.warning(f"LLM tagging failed: {e}")
        
        if fallback_heuristic:
            logger.info("Falling back to heuristic tagger")
            heuristic = HeuristicTagger()
            tags = heuristic.suggest_tags(text)
            tagger_name = "heuristic"
    
    # Zapisz tagi
    saved = 0
    for tag in tags:
        try:
            if tag_manager.tag(session, tag, created_by="ai"):
                saved += 1
        except ValueError as e:
            logger.warning(f"Cannot save tag '{tag}': {e}")
    
    logger.info(f"✅ Auto-tagged '{session}': {tags} (saved: {saved})")
    
    return AutoTagResult(
        session=session,
        tags=tags,
        source=source,
        tagger=tagger_name,
        success=len(tags) > 0
    )


def autotag_all_sessions(
    llm: Optional[TagLLM] = None,
    limit: Optional[int] = None,
    skip_tagged: bool = True
) -> List[AutoTagResult]:
    """
    Auto-taguje wszystkie sesje.
    
    Args:
        llm: Obiekt TagLLM
        limit: Max liczba sesji
        skip_tagged: Pomiń już otagowane sesje
        
    Returns:
        Lista AutoTagResult
    """
    if llm is None:
        llm = GeminiTagLLM()
    
    tag_manager = get_tag_manager()
    results = []
    count = 0
    
    if not ARCHIVE_DIR.exists():
        return results
    
    for folder in sorted(ARCHIVE_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        
        session = folder.name
        
        # Sprawdź czy już ma tagi
        if skip_tagged and tag_manager.get_tags(session):
            continue
        
        result = autotag_session(session, llm, tag_manager)
        results.append(result)
        count += 1
        
        if limit and count >= limit:
            break
    
    return results


# ═══════════════════════════════════════════════════════════════════════════
# QUICK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def quick_autotag(session: str, provider: str = "gemini") -> List[str]:
    """
    Szybkie auto-tagowanie sesji.
    
    Args:
        session: ID sesji
        provider: 'gemini', 'deepseek', 'local', 'heuristic'
        
    Returns:
        Lista tagów
    """
    llms = {
        "gemini": GeminiTagLLM,
        "deepseek": DeepSeekTagLLM,
        "local": LocalTagLLM,
        "heuristic": HeuristicTagger
    }
    
    llm_class = llms.get(provider, GeminiTagLLM)
    llm = llm_class()
    
    result = autotag_session(session, llm)
    return result.tags


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n" + "═" * 50)
    print("🏷️  ALFA AUTOTAG TEST")
    print("═" * 50)
    
    # Test heurystyczny (nie wymaga API)
    print("\n📝 Testing heuristic tagger...")
    heuristic = HeuristicTagger()
    
    test_text = """
    This is a Python project using machine learning.
    We're building an API with database integration.
    The code includes several functions and classes.
    """
    
    tags = heuristic.suggest_tags(test_text)
    print(f"   Suggested tags: {tags}")
    
    # Test z sesją (jeśli podano argument)
    if len(sys.argv) > 1:
        session = sys.argv[1]
        provider = sys.argv[2] if len(sys.argv) > 2 else "heuristic"
        
        print(f"\n🏷️ Auto-tagging session: {session}")
        print(f"   Provider: {provider}")
        
        tags = quick_autotag(session, provider)
        print(f"   Tags: {tags}")
    
    print("\n✅ Test complete!")
