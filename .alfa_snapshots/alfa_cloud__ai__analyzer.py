"""
📊 ALFA CLOUD ANALYZER
Analizator plików i danych z wykorzystaniem lokalnego AI
"""

from __future__ import annotations
import os
import json
import mimetypes
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

from alfa_cloud.ai.local_llm import LocalLLM, SystemPrompts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA CLASSES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class AnalysisResult:
    """Wynik analizy"""
    file_path: str
    file_type: str
    analysis: str
    summary: Optional[str] = None
    keywords: List[str] = None
    sentiment: Optional[str] = None
    language: Optional[str] = None
    confidence: float = 0.0
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.keywords is None:
            self.keywords = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "analysis": self.analysis,
            "summary": self.summary,
            "keywords": self.keywords,
            "sentiment": self.sentiment,
            "language": self.language,
            "confidence": self.confidence,
            "timestamp": self.timestamp
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ANALYZER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Analyzer:
    """
    📊 Analizator plików i danych
    
    Wykorzystuje lokalne AI (Ollama) do:
    - Analizy treści plików tekstowych
    - Summaryzacji dokumentów
    - Ekstrakcji słów kluczowych
    - Analizy sentymentu
    - Rozpoznawania języka
    - Analizy obrazów (z modelem vision)
    """
    
    # Obsługiwane typy plików
    TEXT_EXTENSIONS = {'.txt', '.md', '.json', '.yaml', '.yml', '.csv', 
                       '.py', '.js', '.ts', '.html', '.css', '.xml',
                       '.log', '.ini', '.cfg', '.conf'}
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    
    def __init__(self, llm: Optional[LocalLLM] = None):
        self.llm = llm or LocalLLM()
        self.logger = logging.getLogger("ALFA_CLOUD.Analyzer")
    
    async def analyze_file(self, file_path: str) -> AnalysisResult:
        """
        Analizuje plik na podstawie typu
        """
        path = Path(file_path)
        
        if not path.exists():
            return AnalysisResult(
                file_path=file_path,
                file_type="unknown",
                analysis="[ERROR: Plik nie istnieje]"
            )
        
        # Określ typ pliku
        ext = path.suffix.lower()
        mime_type, _ = mimetypes.guess_type(str(path))
        
        # Analizuj według typu
        if ext in self.TEXT_EXTENSIONS or (mime_type and mime_type.startswith('text/')):
            return await self._analyze_text_file(path)
        
        elif ext in self.IMAGE_EXTENSIONS or (mime_type and mime_type.startswith('image/')):
            return await self._analyze_image_file(path)
        
        else:
            return AnalysisResult(
                file_path=file_path,
                file_type=mime_type or "binary",
                analysis=f"Nie można przeanalizować pliku typu: {ext}"
            )
    
    async def _analyze_text_file(self, path: Path) -> AnalysisResult:
        """Analizuje plik tekstowy"""
        try:
            # Wczytaj treść
            content = path.read_text(encoding='utf-8', errors='ignore')
            
            # Ogranicz długość dla AI
            max_chars = 8000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n[... tekst skrócony ...]"
            
            # Generuj analizę
            prompt = f"""Przeanalizuj poniższy tekst z pliku "{path.name}":

---
{content}
---

Podaj:
1. PODSUMOWANIE (2-3 zdania)
2. SŁOWA KLUCZOWE (5-10)
3. TYP TREŚCI (np. kod, dokumentacja, log, notatki)
4. JĘZYK (polski, angielski, mieszany)
5. GŁÓWNE TEMATY

Odpowiedz w formacie JSON."""

            analysis = await self.llm.generate(
                prompt,
                system=SystemPrompts.FILE_ANALYZER,
                task="analysis"
            )
            
            # Spróbuj sparsować JSON
            summary = None
            keywords = []
            language = None
            
            try:
                # Znajdź JSON w odpowiedzi
                if '{' in analysis:
                    json_start = analysis.index('{')
                    json_end = analysis.rindex('}') + 1
                    json_str = analysis[json_start:json_end]
                    data = json.loads(json_str)
                    
                    summary = data.get("PODSUMOWANIE") or data.get("summary")
                    keywords = data.get("SŁOWA KLUCZOWE") or data.get("keywords") or []
                    language = data.get("JĘZYK") or data.get("language")
            except:
                pass
            
            return AnalysisResult(
                file_path=str(path),
                file_type=path.suffix,
                analysis=analysis,
                summary=summary,
                keywords=keywords if isinstance(keywords, list) else [],
                language=language,
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"Błąd analizy tekstu: {e}")
            return AnalysisResult(
                file_path=str(path),
                file_type=path.suffix,
                analysis=f"[ERROR: {str(e)}]"
            )
    
    async def _analyze_image_file(self, path: Path) -> AnalysisResult:
        """Analizuje plik obrazu"""
        try:
            analysis = await self.llm.analyze_image(
                str(path),
                prompt="Opisz szczegółowo co widzisz na tym obrazie. Podaj obiekty, kolory, kompozycję i nastrój."
            )
            
            return AnalysisResult(
                file_path=str(path),
                file_type="image",
                analysis=analysis,
                confidence=0.7
            )
            
        except Exception as e:
            self.logger.error(f"Błąd analizy obrazu: {e}")
            return AnalysisResult(
                file_path=str(path),
                file_type="image",
                analysis=f"[ERROR: {str(e)}]"
            )
    
    async def summarize(self, text: str, max_sentences: int = 3) -> str:
        """
        Generuje podsumowanie tekstu
        """
        prompt = f"""Napisz zwięzłe podsumowanie poniższego tekstu w maksymalnie {max_sentences} zdaniach:

{text}

PODSUMOWANIE:"""

        return await self.llm.generate(prompt, task="fast")
    
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Ekstrahuje słowa kluczowe
        """
        prompt = f"""Wyodrębnij {max_keywords} najważniejszych słów kluczowych z poniższego tekstu.
Zwróć tylko listę słów, oddzielonych przecinkami:

{text}

SŁOWA KLUCZOWE:"""

        response = await self.llm.generate(prompt, task="fast")
        
        # Parsuj odpowiedź
        keywords = [k.strip() for k in response.split(',')]
        return keywords[:max_keywords]
    
    async def detect_language(self, text: str) -> str:
        """
        Wykrywa język tekstu
        """
        prompt = f"""Wykryj język poniższego tekstu. 
Odpowiedz jednym słowem (np. "polski", "angielski", "niemiecki"):

{text[:500]}

JĘZYK:"""

        response = await self.llm.generate(prompt, task="fast")
        return response.strip().lower()
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analizuje sentyment tekstu
        """
        prompt = f"""Przeanalizuj sentyment poniższego tekstu.
Odpowiedz w formacie JSON z polami: sentiment (positive/negative/neutral), score (0-1), keywords:

{text}

JSON:"""

        response = await self.llm.generate(prompt, task="analysis")
        
        try:
            if '{' in response:
                json_start = response.index('{')
                json_end = response.rindex('}') + 1
                return json.loads(response[json_start:json_end])
        except:
            pass
        
        return {"sentiment": "neutral", "score": 0.5, "raw": response}
    
    async def compare_files(self, file1: str, file2: str) -> str:
        """
        Porównuje dwa pliki tekstowe
        """
        path1 = Path(file1)
        path2 = Path(file2)
        
        if not path1.exists() or not path2.exists():
            return "[ERROR: Jeden z plików nie istnieje]"
        
        content1 = path1.read_text(encoding='utf-8', errors='ignore')[:4000]
        content2 = path2.read_text(encoding='utf-8', errors='ignore')[:4000]
        
        prompt = f"""Porównaj dwa poniższe teksty i opisz różnice:

=== PLIK 1: {path1.name} ===
{content1}

=== PLIK 2: {path2.name} ===
{content2}

ANALIZA RÓŻNIC:"""

        return await self.llm.generate(prompt, task="analysis")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI PACKAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = ['LocalLLM', 'LocalLLMConfig', 'Analyzer', 'AnalysisResult', 'SystemPrompts']
