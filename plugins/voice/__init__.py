# ═══════════════════════════════════════════════════════════════════════════
# ALFA VOICE PLUGIN v1.0.0
# ═══════════════════════════════════════════════════════════════════════════
"""
ALFA Voice: Speech-to-Text and Text-to-Speech daemon.

Features:
- Whisper STT (local)
- Edge TTS / Piper TTS
- Wake word detection
- Voice commands

Usage:
    Loaded automatically by PluginLoader.
    Commands: voice, listen, speak, mute
"""

import os
import sys
import logging
import threading
import queue
import time
from pathlib import Path
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins import Plugin, PluginManifest

# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class VoiceEvent:
    """Voice event data"""
    type: str  # "speech", "wakeword", "silence"
    text: str = ""
    confidence: float = 0.0
    duration_ms: int = 0

# ═══════════════════════════════════════════════════════════════════════════
# VOICE PLUGIN
# ═══════════════════════════════════════════════════════════════════════════

class VoicePlugin(Plugin):
    """
    ALFA Voice Plugin - STT/TTS daemon.
    """
    
    def __init__(self, manifest: PluginManifest, path: Path):
        super().__init__(manifest, path)
        
        self._stt_engine = None
        self._tts_engine = None
        self._listen_thread: Optional[threading.Thread] = None
        self._running = False
        self._muted = False
        self._speech_queue: queue.Queue = queue.Queue()
        self._on_speech: Optional[Callable[[str], None]] = None
    
    # ─────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────
    
    def on_load(self) -> bool:
        """Initialize voice plugin"""
        self.logger.info("Loading ALFA Voice plugin...")
        
        # Initialize STT engine
        stt_engine = self.get_setting("stt_engine", "whisper")
        if stt_engine == "whisper":
            self._init_whisper()
        
        # Initialize TTS engine
        tts_engine = self.get_setting("tts_engine", "pyttsx3")
        if tts_engine == "pyttsx3":
            self._init_pyttsx3()
        elif tts_engine == "edge":
            self._init_edge_tts()
        
        # Subscribe to events
        self.subscribe_event("voice.listen", self._handle_listen)
        self.subscribe_event("voice.speak", self._handle_speak)
        self.subscribe_event("voice.wakeword", self._handle_wakeword)
        
        self.logger.info("ALFA Voice plugin loaded")
        return True
    
    def on_start(self) -> bool:
        """Start voice daemon"""
        self.logger.info("Starting ALFA Voice daemon...")
        
        # Start TTS queue processor
        self._running = True
        
        # Start listening if auto_listen enabled
        if self.get_setting("auto_listen", False):
            self._start_listening()
        
        self.emit_event("started")
        return True
    
    def on_stop(self):
        """Stop voice daemon"""
        self.logger.info("Stopping ALFA Voice daemon...")
        
        self._running = False
        
        if self._listen_thread:
            self._listen_thread.join(timeout=5.0)
        
        self.emit_event("stopped")
    
    # ─────────────────────────────────────────────────────────────────────
    # ENGINE INITIALIZATION
    # ─────────────────────────────────────────────────────────────────────
    
    def _init_whisper(self):
        """Initialize Whisper STT"""
        try:
            import whisper
            
            model_name = self.get_setting("stt_model", "base")
            self.logger.info(f"Loading Whisper model: {model_name}")
            self._stt_engine = whisper.load_model(model_name)
            self.logger.info("Whisper STT ready")
            
        except ImportError:
            self.logger.warning("Whisper not installed: pip install openai-whisper")
        except Exception as e:
            self.logger.error(f"Whisper init error: {e}")
    
    def _init_pyttsx3(self):
        """Initialize pyttsx3 TTS"""
        try:
            import pyttsx3
            
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty("rate", 180)
            self.logger.info("pyttsx3 TTS ready")
            
        except ImportError:
            self.logger.warning("pyttsx3 not installed: pip install pyttsx3")
        except Exception as e:
            self.logger.error(f"pyttsx3 init error: {e}")
    
    def _init_edge_tts(self):
        """Initialize Edge TTS (async)"""
        # Edge TTS requires async, will be used via speak_async()
        self.logger.info("Edge TTS configured (async)")
    
    # ─────────────────────────────────────────────────────────────────────
    # SPEECH-TO-TEXT
    # ─────────────────────────────────────────────────────────────────────
    
    def _start_listening(self):
        """Start background listening thread"""
        if self._listen_thread and self._listen_thread.is_alive():
            return
        
        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="VoiceListener"
        )
        self._listen_thread.start()
    
    def _listen_loop(self):
        """Background listening loop"""
        try:
            import pyaudio
            import wave
            import tempfile
            
            p = pyaudio.PyAudio()
            
            # Audio settings
            RATE = 16000
            CHUNK = 1024
            CHANNELS = 1
            FORMAT = pyaudio.paInt16
            
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            self.logger.info("Listening started...")
            
            frames = []
            silence_count = 0
            threshold = self.get_setting("silence_threshold", 500)
            silence_duration = self.get_setting("silence_duration", 2.0)
            max_silence = int(silence_duration * RATE / CHUNK)
            
            while self._running:
                if self._muted:
                    time.sleep(0.1)
                    continue
                
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
                
                # Simple silence detection
                import audioop
                rms = audioop.rms(data, 2)
                
                if rms < threshold:
                    silence_count += 1
                else:
                    silence_count = 0
                
                # Process after silence
                if silence_count > max_silence and len(frames) > max_silence * 2:
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        wf = wave.open(f.name, "wb")
                        wf.setnchannels(CHANNELS)
                        wf.setsampwidth(p.get_sample_size(FORMAT))
                        wf.setframerate(RATE)
                        wf.writeframes(b"".join(frames))
                        wf.close()
                        
                        # Transcribe
                        text = self._transcribe(f.name)
                        os.unlink(f.name)
                        
                        if text:
                            self._process_speech(text)
                    
                    frames = []
                    silence_count = 0
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            self.logger.error(f"Listen loop error: {e}")
    
    def _transcribe(self, audio_path: str) -> str:
        """Transcribe audio file using Whisper"""
        if not self._stt_engine:
            return ""
        
        try:
            result = self._stt_engine.transcribe(
                audio_path,
                language="pl",
                fp16=False
            )
            return result.get("text", "").strip()
        except Exception as e:
            self.logger.error(f"Transcribe error: {e}")
            return ""
    
    def _process_speech(self, text: str):
        """Process recognized speech"""
        wakeword = self.get_setting("wakeword", "alfa").lower()
        
        # Check for wakeword
        if text.lower().startswith(wakeword):
            command = text[len(wakeword):].strip()
            self.emit_event("wakeword_detected", {"command": command})
            
            if self._on_speech:
                self._on_speech(command)
        else:
            self.emit_event("speech_recognized", {"text": text})
    
    # ─────────────────────────────────────────────────────────────────────
    # TEXT-TO-SPEECH
    # ─────────────────────────────────────────────────────────────────────
    
    def speak(self, text: str):
        """Speak text using TTS"""
        if self._muted:
            self.logger.debug(f"Muted, not speaking: {text[:50]}")
            return
        
        if self._tts_engine:
            try:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
            except Exception as e:
                self.logger.error(f"TTS error: {e}")
        else:
            self.logger.warning("No TTS engine available")
    
    async def speak_async(self, text: str, output_file: str = None):
        """Speak using Edge TTS (async)"""
        try:
            import edge_tts
            
            voice = self.get_setting("tts_voice", "pl-PL-ZofiaNeural")
            communicate = edge_tts.Communicate(text, voice)
            
            if output_file:
                await communicate.save(output_file)
            else:
                # Play directly
                import tempfile
                import subprocess
                
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    await communicate.save(f.name)
                    # Play with default player
                    if sys.platform == "win32":
                        os.startfile(f.name)
                    else:
                        subprocess.run(["mpv", "--no-video", f.name])
                    
        except ImportError:
            self.logger.warning("edge-tts not installed: pip install edge-tts")
        except Exception as e:
            self.logger.error(f"Edge TTS error: {e}")
    
    # ─────────────────────────────────────────────────────────────────────
    # EVENT HANDLERS
    # ─────────────────────────────────────────────────────────────────────
    
    def _handle_listen(self, event):
        """Handle voice.listen event"""
        self._start_listening()
    
    def _handle_speak(self, event):
        """Handle voice.speak event"""
        text = event.payload.get("text", "") if event.payload else ""
        if text:
            self.speak(text)
    
    def _handle_wakeword(self, event):
        """Handle voice.wakeword event"""
        # Custom wakeword handling
        pass
    
    # ─────────────────────────────────────────────────────────────────────
    # COMMANDS
    # ─────────────────────────────────────────────────────────────────────
    
    def on_command(self, command: str, args: str) -> Optional[str]:
        """Handle CLI commands"""
        
        if command == "voice":
            status = "muted" if self._muted else "active"
            listening = self._listen_thread and self._listen_thread.is_alive()
            return f"""ALFA Voice Status:
  Status: {status}
  Listening: {listening}
  STT Engine: {self.get_setting('stt_engine')}
  TTS Engine: {self.get_setting('tts_engine')}
  Wake word: {self.get_setting('wakeword')}"""
        
        elif command == "listen":
            self._start_listening()
            return "Listening started..."
        
        elif command == "speak":
            if args:
                self.speak(args)
                return f"Speaking: {args}"
            return "Usage: speak <text>"
        
        elif command == "mute":
            self._muted = not self._muted
            return f"Voice {'muted' if self._muted else 'unmuted'}"
        
        return None
    
    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────
    
    def set_speech_callback(self, callback: Callable[[str], None]):
        """Set callback for recognized speech"""
        self._on_speech = callback
    
    def mute(self):
        """Mute voice output"""
        self._muted = True
    
    def unmute(self):
        """Unmute voice output"""
        self._muted = False
    
    def is_listening(self) -> bool:
        """Check if listening is active"""
        return self._listen_thread is not None and self._listen_thread.is_alive()
