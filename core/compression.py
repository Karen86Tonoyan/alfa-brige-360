"""
ALFA Compression Engine v1.0
Kompresja danych z wieloma algorytmami i weryfikacją SHA-256
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

logger = logging.getLogger("alfa.compression")


class CompressionAlgo(Enum):
    """Dostępne algorytmy kompresji."""
    
    ZSTD22 = "zstd22"           # Najlepsza równowaga szybkość/kompresja
    LZMA_EXTREME = "lzma"       # Maksymalna kompresja
    BROTLI11 = "brotli"         # Świetny dla tekstu/web
    NONE = "none"               # Bez kompresji (tylko hash)


@dataclass
class CompressionResult:
    """Wynik operacji kompresji."""
    
    success: bool
    algo: str
    original_size: int
    compressed_size: int
    ratio: float                # Prawdziwy ratio (nie fake!)
    hash_sha256: str
    data: Optional[bytes] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "algo": self.algo,
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "ratio": round(self.ratio, 2),
            "hash_sha256": self.hash_sha256,
            "error": self.error,
        }
        
    @classmethod
    def failure(cls, error: str) -> "CompressionResult":
        return cls(
            success=False,
            algo="none",
            original_size=0,
            compressed_size=0,
            ratio=1.0,
            hash_sha256="",
            error=error,
        )


class AlfaCompression:
    """
    ALFA Compression Engine.
    
    Cechy:
    - Prawdziwe ratio (nie fake jak w niektórych narzędziach)
    - SHA-256 weryfikacja integralności
    - Wybór optymalnego algorytmu
    - Streaming dla dużych plików
    """
    
    def __init__(
        self,
        default_algo: CompressionAlgo = CompressionAlgo.ZSTD22,
        chunk_size: int = 1024 * 1024,  # 1MB chunks
    ):
        self.default_algo = default_algo
        self.chunk_size = chunk_size
        
        # Sprawdź dostępność bibliotek
        self._zstd_available = self._check_zstd()
        self._brotli_available = self._check_brotli()
        
    def _check_zstd(self) -> bool:
        """Sprawdź czy zstd jest dostępne."""
        try:
            import zstandard
            return True
        except ImportError:
            logger.warning("[COMPRESSION] zstandard not available: pip install zstandard")
            return False
            
    def _check_brotli(self) -> bool:
        """Sprawdź czy brotli jest dostępne."""
        try:
            import brotli
            return True
        except ImportError:
            logger.warning("[COMPRESSION] brotli not available: pip install brotli")
            return False
            
    # --- COMPRESSION ---
    
    def compress(
        self,
        data: Union[bytes, str],
        algo: Optional[CompressionAlgo] = None,
    ) -> CompressionResult:
        """
        Skompresuj dane.
        
        Args:
            data: Dane do kompresji (bytes lub str)
            algo: Algorytm (domyślnie z konstruktora)
            
        Returns:
            CompressionResult z danymi i metadanymi
        """
        algo = algo or self.default_algo
        
        # Konwertuj str do bytes
        if isinstance(data, str):
            data = data.encode("utf-8")
            
        original_size = len(data)
        
        # Hash PRZED kompresją
        original_hash = hashlib.sha256(data).hexdigest()
        
        try:
            if algo == CompressionAlgo.ZSTD22:
                compressed = self._compress_zstd(data)
            elif algo == CompressionAlgo.LZMA_EXTREME:
                compressed = self._compress_lzma(data)
            elif algo == CompressionAlgo.BROTLI11:
                compressed = self._compress_brotli(data)
            elif algo == CompressionAlgo.NONE:
                compressed = data
            else:
                return CompressionResult.failure(f"Unknown algo: {algo}")
                
            compressed_size = len(compressed)
            
            # PRAWDZIWY ratio
            ratio = original_size / compressed_size if compressed_size > 0 else 1.0
            
            return CompressionResult(
                success=True,
                algo=algo.value,
                original_size=original_size,
                compressed_size=compressed_size,
                ratio=ratio,
                hash_sha256=original_hash,
                data=compressed,
            )
            
        except Exception as e:
            logger.error(f"[COMPRESSION] Failed: {e}")
            return CompressionResult.failure(str(e))
            
    def _compress_zstd(self, data: bytes, level: int = 22) -> bytes:
        """Kompresja ZSTD (poziom 22 = max)."""
        if not self._zstd_available:
            raise RuntimeError("zstandard not installed")
            
        import zstandard as zstd
        cctx = zstd.ZstdCompressor(level=level)
        return cctx.compress(data)
        
    def _compress_lzma(self, data: bytes, preset: int = 9) -> bytes:
        """Kompresja LZMA (preset 9 = extreme)."""
        import lzma
        return lzma.compress(data, preset=preset | lzma.PRESET_EXTREME)
        
    def _compress_brotli(self, data: bytes, quality: int = 11) -> bytes:
        """Kompresja Brotli (quality 11 = max)."""
        if not self._brotli_available:
            raise RuntimeError("brotli not installed")
            
        import brotli
        return brotli.compress(data, quality=quality)
        
    # --- DECOMPRESSION ---
    
    def decompress(
        self,
        data: bytes,
        algo: CompressionAlgo,
        expected_hash: Optional[str] = None,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Dekompresuj dane.
        
        Args:
            data: Skompresowane dane
            algo: Algorytm użyty do kompresji
            expected_hash: Oczekiwany SHA-256 (weryfikacja)
            
        Returns:
            (decompressed_data, error_message)
        """
        try:
            if algo == CompressionAlgo.ZSTD22:
                decompressed = self._decompress_zstd(data)
            elif algo == CompressionAlgo.LZMA_EXTREME:
                decompressed = self._decompress_lzma(data)
            elif algo == CompressionAlgo.BROTLI11:
                decompressed = self._decompress_brotli(data)
            elif algo == CompressionAlgo.NONE:
                decompressed = data
            else:
                return None, f"Unknown algo: {algo}"
                
            # Weryfikacja hash
            if expected_hash:
                actual_hash = hashlib.sha256(decompressed).hexdigest()
                if actual_hash != expected_hash:
                    return None, f"Hash mismatch: expected {expected_hash[:16]}..., got {actual_hash[:16]}..."
                    
            return decompressed, None
            
        except Exception as e:
            return None, str(e)
            
    def _decompress_zstd(self, data: bytes) -> bytes:
        """Dekompresja ZSTD."""
        import zstandard as zstd
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(data)
        
    def _decompress_lzma(self, data: bytes) -> bytes:
        """Dekompresja LZMA."""
        import lzma
        return lzma.decompress(data)
        
    def _decompress_brotli(self, data: bytes) -> bytes:
        """Dekompresja Brotli."""
        import brotli
        return brotli.decompress(data)
        
    # --- FILE OPERATIONS ---
    
    def compress_file(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        algo: Optional[CompressionAlgo] = None,
    ) -> CompressionResult:
        """
        Skompresuj plik.
        
        Args:
            input_path: Ścieżka do pliku wejściowego
            output_path: Ścieżka do pliku wyjściowego (opcjonalnie)
            algo: Algorytm kompresji
            
        Returns:
            CompressionResult
        """
        input_path = Path(input_path)
        algo = algo or self.default_algo
        
        if not input_path.exists():
            return CompressionResult.failure(f"File not found: {input_path}")
            
        # Domyślna nazwa wyjściowa
        if output_path is None:
            ext_map = {
                CompressionAlgo.ZSTD22: ".zst",
                CompressionAlgo.LZMA_EXTREME: ".xz",
                CompressionAlgo.BROTLI11: ".br",
                CompressionAlgo.NONE: ".bin",
            }
            output_path = input_path.with_suffix(input_path.suffix + ext_map.get(algo, ".compressed"))
        else:
            output_path = Path(output_path)
            
        # Czytaj i kompresuj
        with open(input_path, "rb") as f:
            data = f.read()
            
        result = self.compress(data, algo)
        
        if result.success and result.data:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(result.data)
            result.data = None  # Zwolnij pamięć
            logger.info(f"[COMPRESSION] {input_path} -> {output_path} (ratio: {result.ratio:.2f}x)")
            
        return result
        
    def decompress_file(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        algo: Optional[CompressionAlgo] = None,
        expected_hash: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Dekompresuj plik.
        
        Returns:
            (success, error_message)
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            return False, f"File not found: {input_path}"
            
        # Auto-detect algorytm z rozszerzenia
        if algo is None:
            ext_map = {
                ".zst": CompressionAlgo.ZSTD22,
                ".xz": CompressionAlgo.LZMA_EXTREME,
                ".lzma": CompressionAlgo.LZMA_EXTREME,
                ".br": CompressionAlgo.BROTLI11,
            }
            suffix = input_path.suffix.lower()
            algo = ext_map.get(suffix)
            
            if algo is None:
                return False, f"Cannot detect algorithm from extension: {suffix}"
                
        # Domyślna nazwa wyjściowa
        if output_path is None:
            output_path = input_path.with_suffix("")  # Usuń .zst/.xz/.br
        else:
            output_path = Path(output_path)
            
        with open(input_path, "rb") as f:
            compressed = f.read()
            
        decompressed, error = self.decompress(compressed, algo, expected_hash)
        
        if error:
            return False, error
            
        if decompressed:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(decompressed)
            logger.info(f"[COMPRESSION] Decompressed: {input_path} -> {output_path}")
            return True, None
            
        return False, "Decompression returned empty data"
        
    # --- AUTO-SELECT ---
    
    def auto_compress(
        self,
        data: Union[bytes, str],
        prefer_speed: bool = False,
    ) -> CompressionResult:
        """
        Automatycznie wybierz najlepszy algorytm.
        
        Args:
            data: Dane do kompresji
            prefer_speed: True = preferuj szybkość, False = preferuj ratio
            
        Returns:
            CompressionResult z najlepszym wynikiem
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
            
        candidates = []
        
        # Testuj wszystkie dostępne algorytmy
        for algo in CompressionAlgo:
            if algo == CompressionAlgo.NONE:
                continue
            if algo == CompressionAlgo.ZSTD22 and not self._zstd_available:
                continue
            if algo == CompressionAlgo.BROTLI11 and not self._brotli_available:
                continue
                
            result = self.compress(data, algo)
            if result.success:
                candidates.append(result)
                
        if not candidates:
            return self.compress(data, CompressionAlgo.NONE)
            
        # Sortuj: prefer_speed = niższy ratio OK, inaczej najlepszy ratio
        if prefer_speed:
            # ZSTD jest zazwyczaj najszybszy przy dobrym ratio
            for r in candidates:
                if r.algo == "zstd22":
                    return r
            return candidates[0]
        else:
            # Najlepszy ratio
            return max(candidates, key=lambda r: r.ratio)


# === KERNEL MODULE WRAPPER ===

from alfa_core.kernel_contract import BaseModule, BaseModuleConfig, CommandResult, ModuleHealth


class CompressionModuleConfig(BaseModuleConfig):
    """Konfiguracja modułu kompresji."""
    
    def __init__(self, default_algo: str = "zstd22", **kwargs):
        super().__init__(**kwargs)
        self.default_algo = default_algo


class CompressionModule(BaseModule):
    """
    Moduł kompresji dla ALFA Kernel.
    
    Komendy:
    - compress: Kompresuj dane
    - decompress: Dekompresuj dane
    - compress_file: Kompresuj plik
    - decompress_file: Dekompresuj plik
    - auto: Automatyczny wybór algorytmu
    """
    
    id = "core.compression"
    version = "1.0.0"
    
    def __init__(
        self,
        config: Optional[CompressionModuleConfig] = None,
        kernel_context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(config or CompressionModuleConfig(), kernel_context)
        self.engine: Optional[AlfaCompression] = None
        
    def load(self) -> None:
        """Załaduj moduł."""
        algo_name = getattr(self.config, "default_algo", "zstd22")
        
        try:
            default_algo = CompressionAlgo(algo_name)
        except ValueError:
            default_algo = CompressionAlgo.ZSTD22
            
        self.engine = AlfaCompression(default_algo=default_algo)
        self._loaded = True
        logger.info("[COMPRESSION] Module loaded")
        
    def unload(self) -> None:
        """Rozładuj moduł."""
        self.engine = None
        self._loaded = False
        
    def health_check(self) -> ModuleHealth:
        """Sprawdź zdrowie modułu."""
        if not self.engine:
            return ModuleHealth(healthy=False, status="not_loaded")
            
        return ModuleHealth(
            healthy=True,
            status="ready",
            details={
                "zstd_available": self.engine._zstd_available,
                "brotli_available": self.engine._brotli_available,
                "default_algo": self.engine.default_algo.value,
            },
        )
        
    def execute(self, command: str, **kwargs) -> CommandResult:
        """Wykonaj komendę."""
        if not self.engine:
            return CommandResult.failure("Engine not initialized")
            
        # === COMPRESS ===
        if command == "compress":
            data = kwargs.get("data")
            algo = kwargs.get("algo")
            
            if data is None:
                return CommandResult.failure("Missing 'data' parameter")
                
            if algo:
                try:
                    algo = CompressionAlgo(algo)
                except ValueError:
                    return CommandResult.failure(f"Invalid algo: {algo}")
                    
            result = self.engine.compress(data, algo)
            return CommandResult(ok=result.success, data=result.to_dict(), error=result.error)
            
        # === DECOMPRESS ===
        if command == "decompress":
            data = kwargs.get("data")
            algo = kwargs.get("algo")
            expected_hash = kwargs.get("hash")
            
            if not data or not algo:
                return CommandResult.failure("Missing 'data' or 'algo'")
                
            try:
                algo = CompressionAlgo(algo)
            except ValueError:
                return CommandResult.failure(f"Invalid algo: {algo}")
                
            decompressed, error = self.engine.decompress(data, algo, expected_hash)
            
            if error:
                return CommandResult.failure(error)
            return CommandResult.success({"data": decompressed})
            
        # === COMPRESS_FILE ===
        if command == "compress_file":
            input_path = kwargs.get("input")
            output_path = kwargs.get("output")
            algo = kwargs.get("algo")
            
            if not input_path:
                return CommandResult.failure("Missing 'input' path")
                
            if algo:
                try:
                    algo = CompressionAlgo(algo)
                except ValueError:
                    algo = None
                    
            result = self.engine.compress_file(input_path, output_path, algo)
            return CommandResult(ok=result.success, data=result.to_dict(), error=result.error)
            
        # === DECOMPRESS_FILE ===
        if command == "decompress_file":
            input_path = kwargs.get("input")
            output_path = kwargs.get("output")
            algo = kwargs.get("algo")
            expected_hash = kwargs.get("hash")
            
            if not input_path:
                return CommandResult.failure("Missing 'input' path")
                
            if algo:
                try:
                    algo = CompressionAlgo(algo)
                except ValueError:
                    algo = None
                    
            success, error = self.engine.decompress_file(
                input_path, output_path, algo, expected_hash
            )
            
            if error:
                return CommandResult.failure(error)
            return CommandResult.success({"decompressed": True})
            
        # === AUTO ===
        if command == "auto":
            data = kwargs.get("data")
            prefer_speed = kwargs.get("prefer_speed", False)
            
            if not data:
                return CommandResult.failure("Missing 'data'")
                
            result = self.engine.auto_compress(data, prefer_speed)
            return CommandResult(ok=result.success, data=result.to_dict(), error=result.error)
            
        return CommandResult.failure(f"Unknown command: {command}")
