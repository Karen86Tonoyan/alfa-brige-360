"""
ALFA CORE MANAGER v2.0
Centralny dispatcher - łączy providerów, security, routing.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from providers.gemini_provider import GeminiProvider
from providers.deepseek_provider import DeepSeekProvider
from security.cerber import Cerber


class CoreManager:
    """Główny manager ALFA_CORE."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self._load_config(config_path)
        self.security = Cerber()
        self.providers: Dict[str, Any] = {}
        
        self._init_providers()
        self.default_provider = self.config.get("default_provider", "gemini")
    
    def _load_config(self, path: str) -> dict:
        """Ładuje konfigurację."""
        config_file = Path(path)
        if config_file.exists():
            return yaml.safe_load(config_file.read_text())
        
        # Default config
        return {
            "version": "2.0",
            "default_provider": "gemini",
            "providers": {
                "gemini": {"enabled": True},
                "deepseek": {"enabled": False}
            }
        }
    
    def _init_providers(self):
        """Inicjalizuje providerów."""
        providers_cfg = self.config.get("providers", {})
        
        # Gemini
        if providers_cfg.get("gemini", {}).get("enabled", True):
            try:
                self.providers["gemini"] = GeminiProvider("config/gemini.yaml")
                print("[CORE] ✅ Gemini provider loaded")
            except Exception as e:
                print(f"[CORE] ❌ Gemini failed: {e}")
        
        # DeepSeek
        if providers_cfg.get("deepseek", {}).get("enabled", False):
            try:
                self.providers["deepseek"] = DeepSeekProvider("config/deepseek.yaml")
                print("[CORE] ✅ DeepSeek provider loaded")
            except Exception as e:
                print(f"[CORE] ⚠️ DeepSeek failed: {e}")
    
    def start(self):
        """Uruchamia ALFA_CORE."""
        print("=" * 50)
        print("🔥 ALFA_CORE v2.0 – ONLINE")
        print(f"   Default provider: {self.default_provider}")
        print(f"   Loaded providers: {list(self.providers.keys())}")
        print(f"   Security: Cerber ACTIVE")
        print("=" * 50)
    
    def dispatch(self, prompt: str, provider: Optional[str] = None) -> str:
        """
        Wysyła prompt do providera.
        
        Args:
            prompt: Tekst do wysłania
            provider: Opcjonalnie wybór providera (gemini/deepseek)
        
        Returns:
            Odpowiedź od AI
        """
        # Security check
        try:
            self.security.check(prompt)
        except Exception as e:
            return str(e)
        
        # Wybierz providera
        provider_name = provider or self.default_provider
        selected = self.providers.get(provider_name)
        
        if not selected:
            # Fallback
            if self.providers:
                provider_name = list(self.providers.keys())[0]
                selected = self.providers[provider_name]
            else:
                return "[ERROR] No providers available"
        
        # Generuj odpowiedź
        return selected.generate(prompt)
    
    def status(self) -> dict:
        """Zwraca status systemu."""
        return {
            "version": self.config.get("version", "2.0"),
            "default_provider": self.default_provider,
            "providers": list(self.providers.keys()),
            "security": self.security.status()
        }
