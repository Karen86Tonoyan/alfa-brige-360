"""
ALFA_MIRROR PRO — OPUS CHUNK ENGINE
Multi-pass hierarchical processing dla tekstów 1GB+.
Poziom: OPUS-LEVEL STRESS-PROOF
"""

from __future__ import annotations

import logging
import hashlib
import json
from pathlib import Path
from typing import List, Optional, Callable, Any, Generator
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .model_limits import (
    ModelProfile,
    ChunkConfig,
    ChunkStrategy,
    get_model_profile,
    get_default_profile,
    calculate_chunk_config,
    estimate_tokens,
)

logger = logging.getLogger("ALFA.Mirror.ChunkEngine")


# ═══════════════════════════════════════════════════════════════════════════
# KONFIGURACJA
# ═══════════════════════════════════════════════════════════════════════════

CHUNK_CACHE_DIR = Path("storage/chunk_cache")
CHUNK_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Chunk:
    """Pojedynczy chunk tekstu."""
    id: str
    index: int
    text: str
    tokens_estimate: int
    start_char: int
    end_char: int
    overlap_start: int = 0
    
    @property
    def length(self) -> int:
        return len(self.text)


@dataclass
class ChunkResult:
    """Wynik przetworzenia chunka."""
    chunk_id: str
    chunk_index: int
    result: str
    success: bool
    error: Optional[str] = None
    processing_time_ms: int = 0


@dataclass
class HierarchicalResult:
    """Wynik hierarchicznego przetwarzania."""
    original_length: int
    chunks_processed: int
    passes: int
    final_result: str
    intermediate_results: List[str] = field(default_factory=list)
    total_time_ms: int = 0
    model_used: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# CHUNK SPLITTER — INTELIGENTNE DZIELENIE
# ═══════════════════════════════════════════════════════════════════════════

class SmartChunkSplitter:
    """
    Inteligentny splitter tekstu.
    
    Features:
    - Szanuje granice akapitów
    - Szanuje granice zdań
    - Overlap dla kontekstu
    - Cache dla dużych tekstów
    """
    
    # Separatory (w kolejności preferencji)
    SEPARATORS = [
        "\n\n\n",       # Podwójny akapit
        "\n\n",         # Akapit
        "\n",           # Nowa linia
        ". ",           # Koniec zdania
        "! ",           # Wykrzyknik
        "? ",           # Pytanie
        "; ",           # Średnik
        ", ",           # Przecinek
        " ",            # Spacja
    ]
    
    def __init__(self, config: ChunkConfig):
        self.config = config
        self._lock = threading.Lock()
    
    def split(self, text: str) -> List[Chunk]:
        """
        Dzieli tekst na chunki.
        
        Args:
            text: Tekst do podziału
            
        Returns:
            Lista Chunk
        """
        if not text or not text.strip():
            return []
        
        # Jeśli mieści się w jednym chunku
        if len(text) <= self.config.chunk_chars:
            return [Chunk(
                id=self._generate_chunk_id(text, 0),
                index=0,
                text=text,
                tokens_estimate=estimate_tokens(text),
                start_char=0,
                end_char=len(text)
            )]
        
        chunks = []
        position = 0
        index = 0
        overlap_chars = int(self.config.overlap_tokens * self.config.model.chars_per_token)
        
        while position < len(text):
            # Określ koniec chunka
            end = min(position + self.config.chunk_chars, len(text))
            
            # Jeśli to nie koniec tekstu, znajdź dobrą granicę
            if end < len(text):
                end = self._find_split_point(text, position, end)
            
            chunk_text = text[position:end]
            
            chunk = Chunk(
                id=self._generate_chunk_id(chunk_text, index),
                index=index,
                text=chunk_text,
                tokens_estimate=estimate_tokens(chunk_text),
                start_char=position,
                end_char=end,
                overlap_start=max(0, position - overlap_chars) if index > 0 else 0
            )
            
            chunks.append(chunk)
            
            # Przesuń pozycję (z overlapem)
            position = end - overlap_chars
            if position <= chunks[-1].start_char:
                position = end  # Avoid infinite loop
            
            index += 1
            
            # Safety limit
            if index > 10000:
                logger.warning("Chunk limit reached (10000)")
                break
        
        logger.info(f"Split {len(text):,} chars into {len(chunks)} chunks")
        return chunks
    
    def _find_split_point(self, text: str, start: int, end: int) -> int:
        """Znajduje najlepszy punkt podziału."""
        # Szukaj w ostatnich 20% chunka
        search_start = end - int(self.config.chunk_chars * 0.2)
        search_start = max(search_start, start)
        
        search_region = text[search_start:end]
        
        # Szukaj separatorów od najlepszego
        for sep in self.SEPARATORS:
            pos = search_region.rfind(sep)
            if pos != -1:
                return search_start + pos + len(sep)
        
        # Fallback: twardy podział
        return end
    
    def _generate_chunk_id(self, text: str, index: int) -> str:
        """Generuje ID chunka."""
        hash_input = f"{text[:100]}{index}{len(text)}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]


# ═══════════════════════════════════════════════════════════════════════════
# CHUNK PROCESSOR — PRZETWARZANIE Z CACHE
# ═══════════════════════════════════════════════════════════════════════════

class ChunkProcessor:
    """
    Przetwarza chunki z cache i retry logic.
    """
    
    def __init__(
        self,
        process_fn: Callable[[str], str],
        model_name: str = "gemini-2.0-flash",
        use_cache: bool = True,
        max_retries: int = 3
    ):
        """
        Args:
            process_fn: Funkcja przetwarzająca chunk → wynik
            model_name: Nazwa modelu (dla cache key)
            use_cache: Czy używać cache
            max_retries: Max retry przy błędach
        """
        self.process_fn = process_fn
        self.model_name = model_name
        self.use_cache = use_cache
        self.max_retries = max_retries
        self._lock = threading.Lock()
    
    def _get_cache_path(self, chunk: Chunk) -> Path:
        """Zwraca ścieżkę cache dla chunka."""
        cache_key = f"{self.model_name}_{chunk.id}"
        return CHUNK_CACHE_DIR / f"{cache_key}.json"
    
    def _load_from_cache(self, chunk: Chunk) -> Optional[str]:
        """Ładuje wynik z cache."""
        if not self.use_cache:
            return None
        
        cache_path = self._get_cache_path(chunk)
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf8"))
                return data.get("result")
            except:
                pass
        return None
    
    def _save_to_cache(self, chunk: Chunk, result: str) -> None:
        """Zapisuje wynik do cache."""
        if not self.use_cache:
            return
        
        cache_path = self._get_cache_path(chunk)
        cache_path.write_text(json.dumps({
            "chunk_id": chunk.id,
            "result": result,
            "cached_at": datetime.now().isoformat()
        }, ensure_ascii=False), encoding="utf8")
    
    def process_chunk(self, chunk: Chunk) -> ChunkResult:
        """
        Przetwarza pojedynczy chunk.
        """
        import time
        start = time.time()
        
        # Check cache
        cached = self._load_from_cache(chunk)
        if cached is not None:
            logger.debug(f"Cache hit for chunk {chunk.index}")
            return ChunkResult(
                chunk_id=chunk.id,
                chunk_index=chunk.index,
                result=cached,
                success=True,
                processing_time_ms=0
            )
        
        # Process with retry
        last_error = None
        for attempt in range(self.max_retries):
            try:
                result = self.process_fn(chunk.text)
                
                # Save to cache
                self._save_to_cache(chunk, result)
                
                elapsed = int((time.time() - start) * 1000)
                return ChunkResult(
                    chunk_id=chunk.id,
                    chunk_index=chunk.index,
                    result=result,
                    success=True,
                    processing_time_ms=elapsed
                )
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Chunk {chunk.index} failed (attempt {attempt + 1}): {e}")
                time.sleep(1 * (attempt + 1))  # Backoff
        
        elapsed = int((time.time() - start) * 1000)
        return ChunkResult(
            chunk_id=chunk.id,
            chunk_index=chunk.index,
            result="",
            success=False,
            error=last_error,
            processing_time_ms=elapsed
        )
    
    def process_all(
        self,
        chunks: List[Chunk],
        parallel: bool = False,
        max_workers: int = 3
    ) -> List[ChunkResult]:
        """
        Przetwarza wszystkie chunki.
        
        Args:
            chunks: Lista chunków
            parallel: Czy przetwarzać równolegle
            max_workers: Max równoległych workerów
        """
        if not parallel:
            results = []
            for chunk in chunks:
                result = self.process_chunk(chunk)
                results.append(result)
                logger.info(f"Processed chunk {chunk.index + 1}/{len(chunks)}")
            return results
        
        # Parallel processing
        results = [None] * len(chunks)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.process_chunk, chunk): chunk.index
                for chunk in chunks
            }
            
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = ChunkResult(
                        chunk_id=chunks[idx].id,
                        chunk_index=idx,
                        result="",
                        success=False,
                        error=str(e)
                    )
                logger.info(f"Completed chunk {idx + 1}/{len(chunks)}")
        
        return results


# ═══════════════════════════════════════════════════════════════════════════
# HIERARCHICAL PROCESSOR — MULTI-PASS SUMMARIZATION
# ═══════════════════════════════════════════════════════════════════════════

class HierarchicalProcessor:
    """
    Multi-pass hierarchical processing.
    
    Algorytm OPUS:
    1. Dziel tekst na chunki
    2. Przetwórz każdy chunk (np. podsumuj)
    3. Połącz wyniki
    4. Jeśli wynik > chunk_size: powtórz od kroku 1
    5. Wygeneruj finalny wynik
    """
    
    def __init__(
        self,
        process_fn: Callable[[str], str],
        model_name: str = "gemini-2.0-flash",
        strategy: ChunkStrategy = ChunkStrategy.BALANCED,
        max_passes: int = 5,
        combine_fn: Optional[Callable[[List[str]], str]] = None
    ):
        """
        Args:
            process_fn: Funkcja przetwarzająca tekst
            model_name: Nazwa modelu
            strategy: Strategia chunkowania
            max_passes: Max liczba przejść
            combine_fn: Funkcja łącząca wyniki (domyślnie: join z separatorami)
        """
        self.process_fn = process_fn
        self.model_name = model_name
        self.strategy = strategy
        self.max_passes = max_passes
        self.combine_fn = combine_fn or self._default_combine
        
        self.config = calculate_chunk_config(model_name, strategy)
    
    def _default_combine(self, results: List[str]) -> str:
        """Domyślne łączenie wyników."""
        return "\n\n---\n\n".join(results)
    
    def process(self, text: str) -> HierarchicalResult:
        """
        Przetwarza tekst hierarchicznie.
        
        Args:
            text: Tekst do przetworzenia
            
        Returns:
            HierarchicalResult z finalnym wynikiem
        """
        import time
        start = time.time()
        
        original_length = len(text)
        current_text = text
        intermediate_results = []
        pass_count = 0
        
        logger.info(f"Starting hierarchical processing: {original_length:,} chars")
        
        while pass_count < self.max_passes:
            pass_count += 1
            logger.info(f"Pass {pass_count}: {len(current_text):,} chars")
            
            # Sprawdź czy mieści się w jednym chunku
            if len(current_text) <= self.config.chunk_chars:
                logger.info(f"Fits in single chunk, processing directly")
                try:
                    final_result = self.process_fn(current_text)
                except Exception as e:
                    logger.error(f"Final processing failed: {e}")
                    final_result = current_text[:self.config.chunk_chars]
                break
            
            # Podziel na chunki
            splitter = SmartChunkSplitter(self.config)
            chunks = splitter.split(current_text)
            
            logger.info(f"Split into {len(chunks)} chunks")
            
            # Przetwórz chunki
            processor = ChunkProcessor(
                self.process_fn,
                self.model_name,
                use_cache=True
            )
            
            results = processor.process_all(chunks)
            
            # Zbierz wyniki
            successful = [r.result for r in results if r.success and r.result]
            failed = [r for r in results if not r.success]
            
            if failed:
                logger.warning(f"{len(failed)} chunks failed in pass {pass_count}")
            
            if not successful:
                logger.error("No successful results, aborting")
                break
            
            # Połącz wyniki
            combined = self.combine_fn(successful)
            intermediate_results.append(combined)
            
            logger.info(f"Combined result: {len(combined):,} chars")
            
            # Jeśli znacząco mniejsze - sukces
            if len(combined) <= len(current_text) * 0.5:
                current_text = combined
            else:
                # Brak postępu - przerwij
                logger.warning("No significant reduction, stopping")
                break
        
        elapsed = int((time.time() - start) * 1000)
        
        return HierarchicalResult(
            original_length=original_length,
            chunks_processed=sum(len(splitter.split(t)) for t in intermediate_results) if intermediate_results else 0,
            passes=pass_count,
            final_result=current_text if pass_count == self.max_passes else locals().get('final_result', current_text),
            intermediate_results=intermediate_results,
            total_time_ms=elapsed,
            model_used=self.model_name
        )


# ═══════════════════════════════════════════════════════════════════════════
# STREAMING PROCESSOR — DLA BARDZO DUŻYCH PLIKÓW
# ═══════════════════════════════════════════════════════════════════════════

def stream_file_chunks(
    file_path: Path,
    chunk_chars: int = 100_000,
    overlap: int = 5_000
) -> Generator[Chunk, None, None]:
    """
    Streamuje chunki z pliku bez ładowania całości do pamięci.
    
    Dla plików 1GB+
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        return
    
    file_size = file_path.stat().st_size
    logger.info(f"Streaming file: {file_path} ({file_size:,} bytes)")
    
    with open(file_path, 'r', encoding='utf8', errors='ignore') as f:
        buffer = ""
        position = 0
        index = 0
        
        while True:
            # Czytaj blok
            new_data = f.read(chunk_chars)
            if not new_data:
                # Ostatni chunk
                if buffer:
                    yield Chunk(
                        id=hashlib.md5(f"{file_path}{index}".encode()).hexdigest()[:12],
                        index=index,
                        text=buffer,
                        tokens_estimate=len(buffer) // 4,
                        start_char=position,
                        end_char=position + len(buffer)
                    )
                break
            
            buffer += new_data
            
            # Jeśli buffer wystarczająco duży
            if len(buffer) >= chunk_chars:
                # Znajdź punkt podziału
                split_point = buffer.rfind('\n\n', chunk_chars - overlap, chunk_chars)
                if split_point == -1:
                    split_point = buffer.rfind('\n', chunk_chars - overlap, chunk_chars)
                if split_point == -1:
                    split_point = chunk_chars
                
                chunk_text = buffer[:split_point]
                
                yield Chunk(
                    id=hashlib.md5(f"{file_path}{index}".encode()).hexdigest()[:12],
                    index=index,
                    text=chunk_text,
                    tokens_estimate=len(chunk_text) // 4,
                    start_char=position,
                    end_char=position + len(chunk_text)
                )
                
                # Przygotuj następny buffer z overlapem
                buffer = buffer[split_point - overlap:]
                position += split_point - overlap
                index += 1


# ═══════════════════════════════════════════════════════════════════════════
# QUICK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def chunk_text(
    text: str,
    model: str = "gemini-2.0-flash",
    strategy: ChunkStrategy = ChunkStrategy.BALANCED
) -> List[Chunk]:
    """Quick: Dzieli tekst na chunki."""
    config = calculate_chunk_config(model, strategy)
    splitter = SmartChunkSplitter(config)
    return splitter.split(text)


def hierarchical_summarize(
    text: str,
    summarize_fn: Callable[[str], str],
    model: str = "gemini-2.0-flash"
) -> str:
    """Quick: Hierarchiczne podsumowanie."""
    processor = HierarchicalProcessor(
        process_fn=summarize_fn,
        model_name=model
    )
    result = processor.process(text)
    return result.final_result


def process_large_file(
    file_path: Path,
    process_fn: Callable[[str], str],
    model: str = "gemini-2.0-flash"
) -> List[str]:
    """Quick: Przetwarza duży plik chunk po chunku."""
    config = calculate_chunk_config(model)
    results = []
    
    for chunk in stream_file_chunks(file_path, config.chunk_chars):
        try:
            result = process_fn(chunk.text)
            results.append(result)
            logger.info(f"Processed file chunk {chunk.index}")
        except Exception as e:
            logger.error(f"Failed chunk {chunk.index}: {e}")
    
    return results


# ═══════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n" + "═" * 70)
    print("🐺 ALFA OPUS CHUNK ENGINE TEST")
    print("═" * 70)
    
    # Symulowany tekst
    test_text = """
    To jest przykładowy tekst do testowania chunk engine.
    
    ## Sekcja 1
    Lorem ipsum dolor sit amet, consectetur adipiscing elit. 
    Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
    
    ## Sekcja 2
    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
    Duis aute irure dolor in reprehenderit in voluptate velit esse.
    
    ## Sekcja 3
    Excepteur sint occaecat cupidatat non proident, sunt in culpa.
    """ * 100  # ~50KB
    
    print(f"\n📄 Test text: {len(test_text):,} chars")
    
    # Test chunk splitter
    from .model_limits import calculate_chunk_config, ChunkStrategy
    
    config = calculate_chunk_config("gemini-2.0-flash", ChunkStrategy.BALANCED)
    splitter = SmartChunkSplitter(config)
    
    chunks = splitter.split(test_text)
    print(f"\n📦 Split into {len(chunks)} chunks:")
    for chunk in chunks[:3]:
        print(f"   Chunk {chunk.index}: {chunk.length:,} chars, ~{chunk.tokens_estimate} tokens")
    
    # Test mock processing
    def mock_summarize(text: str) -> str:
        """Mock summarizer - zwraca 10% tekstu."""
        return text[:len(text) // 10]
    
    processor = HierarchicalProcessor(
        process_fn=mock_summarize,
        model_name="gemini-2.0-flash"
    )
    
    result = processor.process(test_text)
    
    print(f"\n📝 Hierarchical result:")
    print(f"   Original: {result.original_length:,} chars")
    print(f"   Final: {len(result.final_result):,} chars")
    print(f"   Passes: {result.passes}")
    print(f"   Time: {result.total_time_ms}ms")
    
    print("\n✅ Test complete!")
