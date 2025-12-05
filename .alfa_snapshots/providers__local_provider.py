"""
ALFA LOCAL PROVIDER v1.0
Lokalne modele przez Ollama / LM Studio.
"""

from __future__ import annotations

import requests
import yaml
import logging
from pathlib import Path
from typing import Optional, Literal

logger = logging.getLogger("ALFA.LocalProvider")

ModeType = Literal["fast", "balanced", "creative", "secure"]


class LocalProvider:
    """
    Provider dla lokalnych modeli LLM.
    Obsługuje:
    - Ollama (domyślnie)
    - LM Studio
    - text-generation-webui
    """
    
    name = "local"
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None
    ):
        # Defaults
        self.endpoint = endpoint or "http://localhost:11434/api/generate"
        self.model = model or "llama3.2"
        self.timeout = 120
        self.backend = "ollama"  # ollama, lmstudio, tgwui
        
        # Load config if available
        if config_path:
            config_file = Path(config_path)
            if config_file.exists():
                try:
                    cfg = yaml.safe_load(config_file.read_text())
                    self.endpoint = cfg.get("endpoint", self.endpoint)
                    self.model = cfg.get("model", self.model)
                    self.timeout = cfg.get("timeout", self.timeout)
                    self.backend = cfg.get("backend", self.backend)
                except Exception as e:
                    logger.warning(f"Failed to load config: {e}")
        
        logger.info(f"LocalProvider initialized: {self.backend} @ {self.endpoint}")
    
    def generate(self, text: str, system_prompt: Optional[str] = None, mode: ModeType = "balanced") -> str:
        """
        Generuje odpowiedź od lokalnego modelu.
        
        Args:
            text: Prompt użytkownika
            system_prompt: System prompt
            mode: Tryb generowania
            
        Returns:
            Odpowiedź modelu
        """
        if self.backend == "ollama":
            return self._generate_ollama(text, system_prompt, mode)
        elif self.backend == "lmstudio":
            return self._generate_lmstudio(text, system_prompt, mode)
        else:
            return self._generate_ollama(text, system_prompt, mode)
    
    def _generate_ollama(self, text: str, system_prompt: Optional[str], mode: ModeType) -> str:
        """Generowanie przez Ollama API."""
        
        # Temperature based on mode
        temps = {"fast": 0.3, "balanced": 0.7, "creative": 0.9, "secure": 0.4}
        temperature = temps.get(mode, 0.7)
        
        prompt = text
        if system_prompt:
            prompt = f"{system_prompt}\n\n{text}"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout
            )
        except requests.ConnectionError:
            return "[LOCAL ERROR] Ollama not running. Start with: ollama serve"
        except requests.RequestException as e:
            return f"[LOCAL CONNECTION_ERROR] {e}"
        
        if response.status_code != 200:
            return f"[LOCAL ERROR] {response.status_code}: {response.text}"
        
        try:
            data = response.json()
            return data.get("response", "[LOCAL ERROR] No response in data")
        except Exception as e:
            return f"[LOCAL ERROR] {e}"
    
    def _generate_lmstudio(self, text: str, system_prompt: Optional[str], mode: ModeType) -> str:
        """Generowanie przez LM Studio API (OpenAI-compatible)."""
        
        temps = {"fast": 0.3, "balanced": 0.7, "creative": 0.9, "secure": 0.4}
        temperature = temps.get(mode, 0.7)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": text})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
            "stream": False
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout
            )
        except requests.ConnectionError:
            return "[LOCAL ERROR] LM Studio not running"
        except requests.RequestException as e:
            return f"[LOCAL CONNECTION_ERROR] {e}"
        
        if response.status_code != 200:
            return f"[LOCAL ERROR] {response.status_code}: {response.text}"
        
        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[LOCAL ERROR] {e}"
    
    def health(self) -> bool:
        """Sprawdza czy lokalny model jest dostępny."""
        try:
            if self.backend == "ollama":
                # Check Ollama tags endpoint
                resp = requests.get(
                    "http://localhost:11434/api/tags",
                    timeout=5
                )
                return resp.status_code == 200
            else:
                # Try a minimal request
                resp = requests.get(
                    self.endpoint.replace("/generate", "/tags").replace("/v1/chat/completions", "/v1/models"),
                    timeout=5
                )
                return resp.status_code in (200, 404)  # 404 = endpoint exists but different path
        except:
            return False
    
    def list_models(self) -> list:
        """Lista dostępnych modeli (Ollama)."""
        if self.backend != "ollama":
            return []
        
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except:
            pass
        
        return []
    
    def status(self) -> dict:
        """Status providera."""
        return {
            "backend": self.backend,
            "endpoint": self.endpoint,
            "model": self.model,
            "available": self.health(),
            "models": self.list_models() if self.backend == "ollama" else [],
        }
