"""
ALFA DEEPSEEK PROVIDER v2.0
Backup provider dla ALFA_CORE.
"""

import requests
import yaml
from pathlib import Path
from typing import Optional
from security.secret_loader import load_key
import os


class DeepSeekProvider:
    """Provider DeepSeek dla ALFA_CORE."""
    
    def __init__(self, config_path: Optional[str] = None):
        # Załaduj config
        if config_path and Path(config_path).exists():
            cfg = yaml.safe_load(open(config_path))
            self.endpoint = cfg.get("endpoint", "https://api.deepseek.com/v1/chat/completions")
            key_file = cfg.get("key_file")
            if key_file:
                self.key = load_key(key_file)
            else:
                self.key = os.environ.get("DEEPSEEK_API_KEY", "")
        else:
            self.endpoint = "https://api.deepseek.com/v1/chat/completions"
            self.key = os.environ.get("DEEPSEEK_API_KEY", "")
    
    def generate(self, text: str, system_prompt: Optional[str] = None) -> str:
        """Generuje odpowiedź od DeepSeek."""
        if not self.key:
            return "[DEEPSEEK ERROR] Brak klucza API"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": text})
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.key}"
                },
                timeout=60
            )
        except requests.RequestException as e:
            return f"[DEEPSEEK CONNECTION_ERROR] {e}"
        
        if response.status_code != 200:
            return f"[DEEPSEEK ERROR] {response.status_code}: {response.text}"
        
        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[DEEPSEEK ERROR] {e}"
    
    def health(self) -> bool:
        """Sprawdza czy DeepSeek działa."""
        return bool(self.key)
