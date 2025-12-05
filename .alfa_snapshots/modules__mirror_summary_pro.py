"""
ALFA_MIRROR PRO — HIERARCHICAL SUMMARY
Podsumowania z chunkowaniem dla dużych sesji.
Poziom: OPUS-READY
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("ALFA.Mirror.Summary")


# ═══════════════════════════════════════════════════════════════════════════
# KONFIGURACJA
# ═══════════════════════════════════════════════════════════════════════════

ARCHIVE_DIR = Path("storage/gemini_mirror")
CHUNK_SIZE = 3000  # znaków na chunk (bezpieczne dla Gemini)
MAX_CHUNKS = 20  # max chunków do przetworzenia


# ═══════════════════════════════════════════════════════════════════════════
# PROTOKOŁY — SUMMARIZER
# ═══════════════════════════════════════════════════════════════════════════

class Summarizer(Protocol):
    """Protokół dla sumaryzatorów."""
    
    def summarize(self, text: str, style: str = "balanced") -> str:
        """
        Generuje podsumowanie tekstu.
        
        Args:
            text: Tekst do podsumowania
            style: Styl podsumowania ('brief', 'balanced', 'detailed')
            
        Returns:
            Podsumowanie
        """
        ...


@dataclass
class SummaryResult:
    """Wynik podsumowania sesji."""
    session: str
    summary: str
    chunks_processed: int
    total_chars: int
    created_at: str
    style: str
    
    def to_dict(self) -> dict:
        return {
            "session": self.session,
            "summary": self.summary,
            "chunks_processed": self.chunks_processed,
            "total_chars": self.total_chars,
            "created_at": self.created_at,
            "style": self.style
        }


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTERY — GEMINI / DEEPSEEK / LOCAL
# ═══════════════════════════════════════════════════════════════════════════

class GeminiSummarizer:
    """Adapter dla GeminiProvider."""
    
    name = "gemini"
    
    def __init__(self, provider=None):
        """
        Args:
            provider: Instancja GeminiProvider (lub None = lazy load)
        """
        self._provider = provider
    
    @property
    def provider(self):
        if self._provider is None:
            from providers.gemini_provider import GeminiProvider
            self._provider = GeminiProvider()
        return self._provider
    
    def summarize(self, text: str, style: str = "balanced") -> str:
        prompts = {
            "brief": (
                "Streszcz poniższy tekst w 2-3 zdaniach. "
                "Wydobądź tylko kluczową informację:\n\n"
            ),
            "balanced": (
                "Streszcz poniższy tekst w 5-7 zdaniach, "
                "w spokojnym, rzeczowym stylu. "
                "Zachowaj najważniejsze punkty:\n\n"
            ),
            "detailed": (
                "Przygotuj szczegółowe podsumowanie poniższego tekstu. "
                "Wypisz kluczowe punkty, wnioski i tematy. "
                "Zachowaj strukturę i kontekst:\n\n"
            )
        }
        
        prompt = prompts.get(style, prompts["balanced"]) + text
        return self.provider.generate(prompt)


class DeepSeekSummarizer:
    """Adapter dla DeepSeekProvider."""
    
    name = "deepseek"
    
    def __init__(self, provider=None):
        self._provider = provider
    
    @property
    def provider(self):
        if self._provider is None:
            from providers.deepseek_provider import DeepSeekProvider
            self._provider = DeepSeekProvider()
        return self._provider
    
    def summarize(self, text: str, style: str = "balanced") -> str:
        prompts = {
            "brief": "Streszcz w 2-3 zdaniach:\n\n",
            "balanced": "Streszcz w 5-7 zdaniach:\n\n",
            "detailed": "Szczegółowe podsumowanie z punktami:\n\n"
        }
        
        prompt = prompts.get(style, prompts["balanced"]) + text
        return self.provider.generate(prompt)


class LocalSummarizer:
    """Adapter dla LocalProvider (Ollama)."""
    
    name = "local"
    
    def __init__(self, provider=None):
        self._provider = provider
    
    @property
    def provider(self):
        if self._provider is None:
            from providers.local_provider import LocalProvider
            self._provider = LocalProvider()
        return self._provider
    
    def summarize(self, text: str, style: str = "balanced") -> str:
        # Krótszy prompt dla lokalnych modeli
        prompt = f"Summarize this text in {3 if style == 'brief' else 5} sentences:\n\n{text}"
        return self.provider.generate(prompt)


# ═══════════════════════════════════════════════════════════════════════════
# FUNKCJE POMOCNICZE
# ═══════════════════════════════════════════════════════════════════════════

def build_session_text(session_dir: Path) -> str:
    """
    Buduje pełny tekst sesji z plików text_*.md.
    
    Args:
        session_dir: Folder sesji
        
    Returns:
        Połączony tekst wszystkich plików
    """
    texts = []
    
    # Zbierz wszystkie pliki tekstowe
    for f in sorted(session_dir.glob("text_*.md")):
        try:
            content = f.read_text(encoding="utf8")
            texts.append(content)
        except Exception as e:
            logger.warning(f"Cannot read {f}: {e}")
    
    # Dołącz też raw.json jeśli małe
    raw_file = session_dir / "raw.json"
    if raw_file.exists() and raw_file.stat().st_size < 50000:
        try:
            import json
            data = json.loads(raw_file.read_text(encoding="utf8"))
            # Wyciągnij tekst z candidates
            if "candidates" in data:
                for c in data["candidates"]:
                    if "content" in c and "parts" in c["content"]:
                        for part in c["content"]["parts"]:
                            if "text" in part:
                                texts.append(part["text"])
        except:
            pass
    
    return "\n\n---\n\n".join(texts)


def build_session_chunks(
    session_dir: Path,
    chunk_size: int = CHUNK_SIZE
) -> List[str]:
    """
    Dzieli tekst sesji na chunki.
    
    Args:
        session_dir: Folder sesji
        chunk_size: Rozmiar chunka w znakach
        
    Returns:
        Lista chunków
    """
    text = build_session_text(session_dir)
    
    if not text.strip():
        return []
    
    # Inteligentne dzielenie - szukaj granic akapitów
    chunks = []
    current = ""
    
    paragraphs = text.split("\n\n")
    
    for para in paragraphs:
        if len(current) + len(para) < chunk_size:
            current += para + "\n\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            current = para + "\n\n"
    
    if current.strip():
        chunks.append(current.strip())
    
    # Limit chunków
    if len(chunks) > MAX_CHUNKS:
        logger.warning(f"Too many chunks ({len(chunks)}), limiting to {MAX_CHUNKS}")
        chunks = chunks[:MAX_CHUNKS]
    
    return chunks


# ═══════════════════════════════════════════════════════════════════════════
# GŁÓWNA FUNKCJA — HIERARCHICAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

def summarize_session(
    session: str,
    summarizer: Summarizer,
    style: str = "balanced",
    force: bool = False
) -> SummaryResult:
    """
    Generuje hierarchiczne podsumowanie sesji.
    
    Algorytm:
    1. Podziel tekst na chunki
    2. Wygeneruj podsumowanie każdego chunka
    3. Połącz podsumowania i wygeneruj finalne
    
    Args:
        session: ID sesji (nazwa folderu)
        summarizer: Obiekt implementujący protokół Summarizer
        style: Styl podsumowania
        force: Czy nadpisać istniejące podsumowanie
        
    Returns:
        SummaryResult z finalnym podsumowaniem
        
    Raises:
        FileNotFoundError: Gdy sesja nie istnieje
    """
    session_dir = ARCHIVE_DIR / session
    
    if not session_dir.exists():
        raise FileNotFoundError(f"Session not found: {session_dir}")
    
    summary_file = session_dir / "summary.md"
    
    # Sprawdź czy już istnieje
    if summary_file.exists() and not force:
        logger.info(f"Summary already exists for {session}")
        return SummaryResult(
            session=session,
            summary=summary_file.read_text(encoding="utf8"),
            chunks_processed=0,
            total_chars=0,
            created_at=datetime.fromtimestamp(summary_file.stat().st_mtime).isoformat(),
            style=style
        )
    
    # Buduj chunki
    chunks = build_session_chunks(session_dir)
    
    if not chunks:
        logger.warning(f"No text content in session {session}")
        return SummaryResult(
            session=session,
            summary="[Brak treści tekstowej w tej sesji]",
            chunks_processed=0,
            total_chars=0,
            created_at=datetime.now().isoformat(),
            style=style
        )
    
    total_chars = sum(len(c) for c in chunks)
    logger.info(f"Processing {len(chunks)} chunks ({total_chars} chars)")
    
    # Jeśli mały tekst - podsumuj bezpośrednio
    if len(chunks) == 1:
        logger.info("Single chunk - direct summarization")
        final_summary = summarizer.summarize(chunks[0], style)
    else:
        # Hierarchiczne podsumowanie
        logger.info("Multi-chunk - hierarchical summarization")
        
        # Krok 1: Podsumuj każdy chunk
        partial_summaries = []
        for i, chunk in enumerate(chunks):
            logger.debug(f"Summarizing chunk {i + 1}/{len(chunks)}")
            try:
                partial = summarizer.summarize(chunk, "brief")
                partial_summaries.append(partial)
            except Exception as e:
                logger.warning(f"Failed to summarize chunk {i}: {e}")
                partial_summaries.append(f"[Chunk {i} - błąd podsumowania]")
        
        # Krok 2: Połącz i wygeneruj finalne podsumowanie
        combined = "\n\n".join(partial_summaries)
        
        meta_prompt = (
            "Poniżej znajdują się częściowe podsumowania dłuższego tekstu. "
            "Stwórz jedno spójne, finalne podsumowanie:\n\n" + combined
        )
        
        final_summary = summarizer.summarize(meta_prompt, style)
    
    # Zapisz podsumowanie
    try:
        summary_file.write_text(final_summary, encoding="utf8")
        logger.info(f"✅ Summary saved: {summary_file}")
    except Exception as e:
        logger.error(f"Cannot save summary: {e}")
    
    return SummaryResult(
        session=session,
        summary=final_summary,
        chunks_processed=len(chunks),
        total_chars=total_chars,
        created_at=datetime.now().isoformat(),
        style=style
    )


def summarize_all_sessions(
    summarizer: Summarizer,
    style: str = "balanced",
    limit: Optional[int] = None
) -> List[SummaryResult]:
    """
    Generuje podsumowania dla wszystkich sesji bez summary.md.
    
    Args:
        summarizer: Obiekt Summarizer
        style: Styl podsumowania
        limit: Max liczba sesji do przetworzenia
        
    Returns:
        Lista SummaryResult
    """
    results = []
    count = 0
    
    if not ARCHIVE_DIR.exists():
        return results
    
    for folder in sorted(ARCHIVE_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        
        summary_file = folder / "summary.md"
        if summary_file.exists():
            continue
        
        try:
            result = summarize_session(folder.name, summarizer, style)
            results.append(result)
            count += 1
            
            if limit and count >= limit:
                break
                
        except Exception as e:
            logger.error(f"Failed to summarize {folder.name}: {e}")
    
    return results


# ═══════════════════════════════════════════════════════════════════════════
# QUICK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def quick_summarize(session: str, provider: str = "gemini") -> str:
    """
    Szybkie podsumowanie sesji.
    
    Args:
        session: ID sesji
        provider: 'gemini', 'deepseek', lub 'local'
        
    Returns:
        Tekst podsumowania
    """
    summarizers = {
        "gemini": GeminiSummarizer,
        "deepseek": DeepSeekSummarizer,
        "local": LocalSummarizer
    }
    
    summarizer_class = summarizers.get(provider, GeminiSummarizer)
    summarizer = summarizer_class()
    
    result = summarize_session(session, summarizer)
    return result.summary


def get_session_summary(session: str) -> Optional[str]:
    """
    Pobiera istniejące podsumowanie sesji.
    
    Returns:
        Tekst podsumowania lub None
    """
    summary_file = ARCHIVE_DIR / session / "summary.md"
    
    if summary_file.exists():
        return summary_file.read_text(encoding="utf8")
    
    return None


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    if len(sys.argv) > 1:
        session = sys.argv[1]
        provider = sys.argv[2] if len(sys.argv) > 2 else "gemini"
        
        print(f"\n📝 Summarizing session: {session}")
        print(f"   Provider: {provider}")
        
        try:
            summary = quick_summarize(session, provider)
            print(f"\n{'═' * 50}")
            print("SUMMARY:")
            print('═' * 50)
            print(summary)
        except FileNotFoundError:
            print(f"❌ Session not found: {session}")
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("Usage: python mirror_summary_pro.py <session_id> [provider]")
        print("       provider: gemini, deepseek, local")
