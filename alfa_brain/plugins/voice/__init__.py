# ═══════════════════════════════════════════════════════════════════════════
# ALFA VOICE PLUGIN
# ═══════════════════════════════════════════════════════════════════════════
"""
Speech-to-Text (STT) and Text-to-Speech (TTS) daemon.

Commands: voice, listen, speak, mute
"""

import logging
import threading
from typing import Optional, Callable

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.plugin_engine import Plugin, PluginManifest

LOG = logging.getLogger("alfa.plugin.voice")

class VoicePlugin(Plugin):
    """ALFA Voice Plugin — STT/TTS daemon."""
    
    def __init__(self, manifest: PluginManifest, engine):
        super().__init__(manifest, engine)
        self._muted = False
        self._listening = False
        self._on_speech: Optional[Callable] = None
    
    def on_load(self) -> bool:
        LOG.info("Voice plugin loading...")
        self.subscribe("voice.*", self._on_voice_event)
        return True
    
    def on_start(self) -> bool:
        LOG.info("Voice plugin starting...")
        self.emit("started")
        return True
    
    def on_stop(self):
        LOG.info("Voice plugin stopping...")
        self._listening = False
        self.emit("stopped")
    
    def _on_voice_event(self, event):
        """Handle voice events."""
        if event.topic == "voice.speak" and event.payload:
            self.speak(event.payload.get("text", ""))
    
    def speak(self, text: str):
        """Speak text using TTS."""
        if self._muted:
            LOG.debug(f"Muted: {text[:50]}")
            return
        
        # TODO: Implement actual TTS
        LOG.info(f"[TTS] {text}")
    
    def on_command(self, command: str, args: str) -> Optional[str]:
        if command == "voice":
            return f"Voice: {'muted' if self._muted else 'active'}, listening: {self._listening}"
        
        elif command == "listen":
            self._listening = True
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
