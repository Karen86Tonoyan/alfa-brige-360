# ═══════════════════════════════════════════════════════════════════════════
# ALFA BRIDGE PLUGIN
# ═══════════════════════════════════════════════════════════════════════════
"""
Multi-AI Router: Ollama, DeepSeek, Gemini, Grok, OpenAI.

Commands: ai, chat, model, switch
"""

import logging
from typing import Optional, Dict, Any, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.plugin_engine import Plugin, PluginManifest

LOG = logging.getLogger("alfa.plugin.bridge")

class BridgePlugin(Plugin):
    """ALFA Bridge Plugin — Multi-AI Router."""
    
    PROVIDERS = {
        "ollama": {"url": "http://localhost:11434", "model": "llama3"},
        "deepseek": {"url": "https://api.deepseek.com", "model": "deepseek-chat"},
        "gemini": {"url": "https://generativelanguage.googleapis.com", "model": "gemini-pro"},
        "grok": {"url": "https://api.x.ai/v1", "model": "grok-beta"},
        "openai": {"url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    }
    
    def __init__(self, manifest: PluginManifest, engine):
        super().__init__(manifest, engine)
        self._provider = self.get_setting("default_provider", "ollama")
        self._fallback_chain = self.get_setting("fallback_chain", ["ollama", "deepseek"])
    
    def on_load(self) -> bool:
        LOG.info("Bridge plugin loading...")
        self.subscribe("bridge.*", self._on_bridge_event)
        return True
    
    def on_start(self) -> bool:
        LOG.info(f"Bridge plugin starting with provider: {self._provider}")
        self.emit("started", {"provider": self._provider})
        return True
    
    def on_stop(self):
        LOG.info("Bridge plugin stopping...")
        self.emit("stopped")
    
    def _on_bridge_event(self, event):
        """Handle bridge events."""
        if event.topic == "bridge.query" and event.payload:
            self.query(event.payload.get("prompt", ""))
    
    async def query(self, prompt: str, provider: str = None) -> Optional[str]:
        """Query AI provider."""
        provider = provider or self._provider
        
        if provider not in self.PROVIDERS:
            LOG.error(f"Unknown provider: {provider}")
            return None
        
        config = self.PROVIDERS[provider]
        
        try:
            if provider == "ollama":
                return await self._query_ollama(prompt, config)
            else:
                LOG.warning(f"Provider not implemented: {provider}")
                return None
        except Exception as e:
            LOG.error(f"Query failed: {e}")
            # Try fallback
            for fallback in self._fallback_chain:
                if fallback != provider:
                    LOG.info(f"Trying fallback: {fallback}")
                    return await self.query(prompt, fallback)
            return None
    
    async def _query_ollama(self, prompt: str, config: Dict) -> str:
        """Query Ollama API."""
        import httpx
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{config['url']}/api/chat",
                json={
                    "model": config["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
    
    def on_command(self, command: str, args: str) -> Optional[str]:
        if command == "ai" or command == "model":
            return f"Provider: {self._provider}\nModel: {self.PROVIDERS[self._provider]['model']}"
        
        elif command == "switch":
            if args in self.PROVIDERS:
                self._provider = args
                return f"Switched to: {args}"
            return f"Unknown provider. Available: {', '.join(self.PROVIDERS.keys())}"
        
        elif command == "chat":
            if not args:
                return "Usage: chat <prompt>"
            
            # Sync wrapper for async query
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(self.query(args))
            return result or "No response"
        
        return None
