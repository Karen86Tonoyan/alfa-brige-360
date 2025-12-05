"""
ALFA VOICE v1 — STT (Speech-to-Text)
Konwersja mowy na tekst z Whisper.
"""

from typing import Optional, Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger("ALFA.STT")


class STT:
    """
    Speech-to-Text z Whisper.
    """
    
    def __init__(
        self,
        model_size: str = "base",
        language: str = "pl",
        device: str = "cpu"
    ):
        """
        Args:
            model_size: Rozmiar modelu (tiny/base/small/medium/large)
            language: Język (pl/en/auto)
            device: Urządzenie (cpu/cuda)
        """
        self.model_size = model_size
        self.language = language
        self.device = device
        
        self._model = None
        self._available = False
        
        self._load_model()
    
    def _load_model(self) -> None:
        """Ładuje model Whisper."""
        try:
            import whisper
            logger.info(f"Loading Whisper model: {self.model_size}")
            self._model = whisper.load_model(self.model_size, device=self.device)
            self._available = True
            logger.info("Whisper model loaded")
        except ImportError:
            logger.warning("Whisper not available - pip install openai-whisper")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> Optional[str]:
        """
        Transkrybuje audio na tekst.
        
        Args:
            audio_path: Ścieżka do pliku audio
            language: Język (opcjonalny)
            
        Returns:
            Transkrypcja lub None
        """
        if not self._available or not self._model:
            logger.error("STT not available")
            return None
        
        audio_file = Path(audio_path)
        if not audio_file.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None
        
        try:
            lang = language or self.language
            if lang == "auto":
                lang = None
            
            result = self._model.transcribe(
                str(audio_file),
                language=lang,
                fp16=False if self.device == "cpu" else True
            )
            
            text = result.get("text", "").strip()
            logger.info(f"Transcribed: {len(text)} chars from {audio_path}")
            return text
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    def transcribe_with_segments(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Transkrybuje z segmentami czasowymi.
        
        Returns:
            Dict z text i segments lub None
        """
        if not self._available or not self._model:
            return None
        
        try:
            lang = language or self.language
            if lang == "auto":
                lang = None
            
            result = self._model.transcribe(
                audio_path,
                language=lang,
                fp16=False if self.device == "cpu" else True
            )
            
            return {
                "text": result.get("text", "").strip(),
                "language": result.get("language"),
                "segments": [
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"].strip()
                    }
                    for seg in result.get("segments", [])
                ]
            }
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    def is_available(self) -> bool:
        """Czy STT jest dostępny."""
        return self._available
    
    def status(self) -> Dict[str, Any]:
        """Status STT."""
        return {
            "available": self._available,
            "model_size": self.model_size,
            "language": self.language,
            "device": self.device
        }


class SimpleSTT:
    """
    Prosty STT fallback (używa SpeechRecognition).
    """
    
    def __init__(self, language: str = "pl-PL"):
        self.language = language
        self._recognizer = None
        self._available = False
        
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._available = True
            logger.info("SimpleSTT initialized (speech_recognition)")
        except ImportError:
            logger.warning("speech_recognition not available")
    
    def transcribe(self, audio_path: str) -> Optional[str]:
        """Transkrybuje audio."""
        if not self._available or not self._recognizer:
            return None
        
        try:
            import speech_recognition as sr
            
            with sr.AudioFile(audio_path) as source:
                audio = self._recognizer.record(source)
            
            # Try Google Speech Recognition
            text = self._recognizer.recognize_google(audio, language=self.language)
            return text
            
        except Exception as e:
            logger.error(f"SimpleSTT error: {e}")
            return None
    
    def is_available(self) -> bool:
        return self._available
