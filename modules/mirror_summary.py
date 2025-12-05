"""
ALFA MIRROR — SUMMARY
AI-podsumowania sesji.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Protocol, List

logger = logging.getLogger("ALFA.Mirror.Summary")

ARCHIVE_DIR = Path("storage/gemini_mirror")


class Summarizer(Protocol):
    """Protokół dla summarizera."""
    def summarize(self, text: str) -> str:
        ...


def build_session_text(session_dir: Path) -> str:
    """
    Buduje pełny tekst z sesji.
    
    Zbiera:
    - text_*.md
    - function_*.json (jako kontekst)
    """
    texts = []
    
    # Text files first
    for f in sorted(session_dir.glob("text_*.md")):
        try:
            texts.append(f.read_text(encoding="utf8"))
        except Exception:
            pass
    
    # Function calls as context
    for f in sorted(session_dir.glob("function_*.json")):
        try:
            content = f.read_text(encoding="utf8")
            texts.append(f"[Function Call]\n{content}")
        except Exception:
            pass
    
    return "\n\n---\n\n".join(texts)


def summarize_session(session: str, summarizer: Summarizer) -> str:
    """
    Generuje podsumowanie sesji.
    
    Args:
        session: ID sesji
        summarizer: Obiekt z metodą summarize(text) -> str
        
    Returns:
        Tekst podsumowania
    """
    session_dir = ARCHIVE_DIR / session
    
    if not session_dir.exists():
        raise FileNotFoundError(f"Session not found: {session}")
    
    full_text = build_session_text(session_dir)
    
    if not full_text.strip():
        return ""
    
    # Limit text length
    if len(full_text) > 10000:
        full_text = full_text[:10000] + "\n\n[TRUNCATED]"
    
    summary = summarizer.summarize(full_text)
    
    # Save summary
    summary_file = session_dir / "summary.md"
    summary_file.write_text(summary, encoding="utf8")
    
    logger.info(f"Summarized session: {session}")
    return summary


def get_summary(session: str) -> Optional[str]:
    """
    Pobiera istniejące podsumowanie sesji.
    
    Returns:
        Tekst podsumowania lub None
    """
    session_dir = ARCHIVE_DIR / session
    summary_file = session_dir / "summary.md"
    
    if summary_file.exists():
        return summary_file.read_text(encoding="utf8")
    
    return None


def batch_summarize(summarizer: Summarizer, limit: int = 10) -> List[str]:
    """
    Podsumowuje wiele sesji (te bez summary).
    
    Args:
        summarizer: Summarizer instance
        limit: Maksymalna liczba sesji
        
    Returns:
        Lista podsumowanych sesji
    """
    if not ARCHIVE_DIR.exists():
        return []
    
    summarized = []
    
    for folder in sorted(ARCHIVE_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        
        summary_file = folder / "summary.md"
        if summary_file.exists():
            continue
        
        # Check if has text content
        text_files = list(folder.glob("text_*.md"))
        if not text_files:
            continue
        
        try:
            summarize_session(folder.name, summarizer)
            summarized.append(folder.name)
            
            if len(summarized) >= limit:
                break
        except Exception as e:
            logger.error(f"Failed to summarize {folder.name}: {e}")
    
    return summarized


# Adapter dla Gemini Provider

class GeminiSummarizer:
    """Adapter summarizera dla GeminiProvider."""
    
    def __init__(self, provider):
        self.provider = provider
    
    def summarize(self, text: str) -> str:
        prompt = (
            "Streszcz poniższy tekst w 5–7 zdaniach, "
            "w spokojnym, rzeczowym stylu. "
            "Wypisz najważniejsze punkty.\n\n" + text
        )
        return self.provider.generate(prompt)


class DeepSeekSummarizer:
    """Adapter summarizera dla DeepSeekProvider."""
    
    def __init__(self, provider):
        self.provider = provider
    
    def summarize(self, text: str) -> str:
        prompt = (
            "Summarize the following text in 5-7 sentences. "
            "Be concise and factual.\n\n" + text
        )
        return self.provider.generate(prompt)
