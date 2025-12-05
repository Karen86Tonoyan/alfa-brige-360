"""
ALFA VOICE v1 — TTS (Text-to-Speech)
Konwersja tekstu na mowę z Piper.
"""

from typing import Optional, Dict, Any
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger("ALFA.TTS")


class TTS:
    """
    Text-to-Speech z Piper.
    """
    
    def __init__(
        self,
        piper_path: Optional[str] = None,
        model_path: Optional[str] = None,
        output_format: str = "wav"
    ):
        """
        Args:
            piper_path: Ścieżka do piper.exe
            model_path: Ścieżka do modelu .onnx
            output_format: Format wyjściowy (wav/mp3/ogg)
        """
        self.piper_path = piper_path or self._find_piper()
        self.model_path = model_path
        self.output_format = output_format
        
        self._available = self._check_availability()
        
        if self._available:
            logger.info(f"TTS initialized (piper: {self.piper_path})")
        else:
            logger.warning("TTS not available - Piper not found")
    
    def _find_piper(self) -> Optional[str]:
        """Szuka piper w standardowych lokalizacjach."""
        locations = [
            Path.home() / ".local" / "bin" / "piper",
            Path.home() / "piper" / "piper.exe",
            Path("C:/piper/piper.exe"),
            Path("/usr/bin/piper"),
            Path("/usr/local/bin/piper"),
        ]
        
        for loc in locations:
            if loc.exists():
                return str(loc)
        
        return None
    
    def _check_availability(self) -> bool:
        """Sprawdza czy TTS jest dostępny."""
        if not self.piper_path:
            return False
        
        piper_file = Path(self.piper_path)
        return piper_file.exists()
    
    def synthesize(
        self,
        text: str,
        output_path: Optional[str] = None,
        voice: Optional[str] = None
    ) -> Optional[str]:
        """
        Syntezuje mowę z tekstu.
        
        Args:
            text: Tekst do syntezy
            output_path: Ścieżka wyjściowa (opcjonalna)
            voice: Model głosu (opcjonalny)
            
        Returns:
            Ścieżka do pliku audio lub None
        """
        if not self._available:
            logger.error("TTS not available")
            return None
        
        if not output_path:
            output_path = tempfile.mktemp(suffix=f".{self.output_format}")
        
        try:
            model = voice or self.model_path
            
            # Build command
            cmd = [self.piper_path]
            
            if model:
                cmd.extend(["--model", model])
            
            cmd.extend(["--output_file", output_path])
            
            # Run piper
            process = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if process.returncode != 0:
                logger.error(f"Piper error: {process.stderr}")
                return None
            
            # Convert to OGG if needed (for Delta Chat)
            if self.output_format == "ogg" and output_path.endswith(".wav"):
                output_path = self._convert_to_ogg(output_path)
            
            logger.info(f"Synthesized: {len(text)} chars -> {output_path}")
            return output_path
            
        except subprocess.TimeoutExpired:
            logger.error("TTS timeout")
            return None
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None
    
    def _convert_to_ogg(self, wav_path: str) -> str:
        """Konwertuje WAV do OGG (dla Delta Chat)."""
        ogg_path = wav_path.replace(".wav", ".ogg")
        
        try:
            # Try ffmpeg
            subprocess.run(
                ["ffmpeg", "-y", "-i", wav_path, "-c:a", "libopus", ogg_path],
                capture_output=True,
                timeout=30
            )
            return ogg_path
        except:
            # Fallback - return wav
            return wav_path
    
    def is_available(self) -> bool:
        """Czy TTS jest dostępny."""
        return self._available
    
    def status(self) -> Dict[str, Any]:
        """Status TTS."""
        return {
            "available": self._available,
            "piper_path": self.piper_path,
            "model_path": self.model_path,
            "output_format": self.output_format
        }


# Fallback dla środowisk bez Piper
class SimpleTTS:
    """
    Prosty TTS fallback (używa pyttsx3 jeśli dostępny).
    """
    
    def __init__(self):
        self._engine = None
        self._available = False
        
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._available = True
            logger.info("SimpleTTS initialized (pyttsx3)")
        except ImportError:
            logger.warning("pyttsx3 not available")
    
    def synthesize(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """Syntezuje mowę."""
        if not self._available or not self._engine:
            return None
        
        try:
            if output_path:
                self._engine.save_to_file(text, output_path)
                self._engine.runAndWait()
                return output_path
            else:
                self._engine.say(text)
                self._engine.runAndWait()
                return None
        except Exception as e:
            logger.error(f"SimpleTTS error: {e}")
            return None
    
    def is_available(self) -> bool:
        return self._available
