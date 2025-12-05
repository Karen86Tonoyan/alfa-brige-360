"""
ALFA VOICE v1 — AUDIO UTILS
Narzędzia do przetwarzania audio.
"""

from typing import Optional, Tuple
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("ALFA.AudioUtils")


def convert_audio(
    input_path: str,
    output_path: str,
    sample_rate: int = 16000,
    channels: int = 1
) -> bool:
    """
    Konwertuje audio do standardowego formatu.
    
    Args:
        input_path: Plik wejściowy
        output_path: Plik wyjściowy
        sample_rate: Częstotliwość próbkowania
        channels: Liczba kanałów (1=mono)
        
    Returns:
        True jeśli sukces
    """
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-ar", str(sample_rate),
            "-ac", str(channels),
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"Audio conversion error: {e}")
        return False


def convert_to_ogg(input_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Konwertuje audio do OGG Opus (dla Delta Chat).
    
    Args:
        input_path: Plik wejściowy
        output_path: Plik wyjściowy (opcjonalny)
        
    Returns:
        Ścieżka do pliku OGG lub None
    """
    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".ogg"))
    
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-c:a", "libopus",
            "-b:a", "48k",
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        
        if result.returncode == 0:
            return output_path
        
        logger.error(f"OGG conversion failed: {result.stderr}")
        return None
        
    except Exception as e:
        logger.error(f"OGG conversion error: {e}")
        return None


def get_audio_duration(file_path: str) -> Optional[float]:
    """
    Pobiera długość pliku audio w sekundach.
    
    Args:
        file_path: Ścieżka do pliku
        
    Returns:
        Długość w sekundach lub None
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return float(result.stdout.strip())
        
        return None
        
    except Exception as e:
        logger.error(f"Duration check error: {e}")
        return None


def get_audio_info(file_path: str) -> Optional[dict]:
    """
    Pobiera informacje o pliku audio.
    
    Returns:
        Dict z informacjami lub None
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            
            format_info = data.get("format", {})
            streams = data.get("streams", [])
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
            
            return {
                "duration": float(format_info.get("duration", 0)),
                "format": format_info.get("format_name"),
                "size": int(format_info.get("size", 0)),
                "codec": audio_stream.get("codec_name"),
                "sample_rate": int(audio_stream.get("sample_rate", 0)),
                "channels": audio_stream.get("channels"),
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Audio info error: {e}")
        return None


def split_audio(
    input_path: str,
    output_dir: str,
    segment_duration: float = 30.0
) -> list:
    """
    Dzieli audio na segmenty.
    
    Args:
        input_path: Plik wejściowy
        output_dir: Katalog wyjściowy
        segment_duration: Długość segmentu w sekundach
        
    Returns:
        Lista ścieżek do segmentów
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    input_file = Path(input_path)
    base_name = input_file.stem
    suffix = input_file.suffix
    
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-f", "segment",
            "-segment_time", str(segment_duration),
            "-c", "copy",
            str(output_dir / f"{base_name}_%03d{suffix}")
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        
        if result.returncode == 0:
            segments = sorted(output_dir.glob(f"{base_name}_*{suffix}"))
            return [str(s) for s in segments]
        
        return []
        
    except Exception as e:
        logger.error(f"Audio split error: {e}")
        return []


def merge_audio(input_paths: list, output_path: str) -> bool:
    """
    Łączy pliki audio.
    
    Args:
        input_paths: Lista plików do połączenia
        output_path: Plik wyjściowy
        
    Returns:
        True jeśli sukces
    """
    if not input_paths:
        return False
    
    try:
        # Create concat file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for path in input_paths:
                f.write(f"file '{path}'\n")
            concat_file = f.name
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        
        # Cleanup
        Path(concat_file).unlink()
        
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"Audio merge error: {e}")
        return False


def is_ffmpeg_available() -> bool:
    """Sprawdza czy ffmpeg jest dostępny."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False
