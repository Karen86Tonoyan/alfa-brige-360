"""
ALFA GEMINI PROVIDER v2.0
Czysty HTTP, zero SDK, pełna kontrola.
"""

import json
import requests
import yaml
from pathlib import Path
from typing import Optional
from security.secret_loader import load_gemini_key


class GeminiProvider:
    """Provider Gemini dla ALFA_CORE."""
    
    def __init__(self, config_path: Optional[str] = None):
        # Załaduj config
        if config_path and Path(config_path).exists():
            cfg = yaml.safe_load(open(config_path))
            self.model = cfg.get("model", "gemini-1.5-flash")
        else:
            self.model = "gemini-1.5-flash"
        
        # Załaduj klucz
        self.key = load_gemini_key()
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
    
    def generate(self, text: str, system_prompt: Optional[str] = None) -> str:
        """Generuje odpowiedź od Gemini."""
        contents = []
        
        # System prompt jako pierwsza wiadomość
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"SYSTEM: {system_prompt}"}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. System instruction loaded."}]
            })
        
        # User prompt
        contents.append({
            "role": "user",
            "parts": [{"text": text}]
        })
        
        payload = {
            "contents": contents,
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 4096,
                "topP": 0.95,
                "topK": 40
            }
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.key
                },
                timeout=45
            )
        except requests.RequestException as e:
            return f"[GEMINI CONNECTION_ERROR] {e}"
        
        if response.status_code != 200:
            return f"[GEMINI ERROR] {response.status_code}: {response.text}"
        
        try:
            data = response.json()
        except Exception:
            return "[GEMINI ERROR] Invalid JSON response"
        
        # 🔥 MIRROR: Archiwizacja odpowiedzi
        try:
            from modules.mirror_engine import mirror_gemini_response
            mirror_gemini_response(data)
        except ImportError:
            pass  # Mirror not available
        except Exception as mirror_err:
            pass  # Don't fail on mirror errors
        
        # Wyciągnij tekst z odpowiedzi
        try:
            candidate = data["candidates"][0]
            parts = candidate["content"]["parts"]
            part = parts[0]
            
            if "text" in part:
                return part["text"]
            
            if "functionCall" in part:
                return "[ALFA_INTENT] FUNCTION_CALL: " + json.dumps(part["functionCall"])
            
            return "[GEMINI ERROR] No text in response"
        except (KeyError, IndexError):
            return f"[GEMINI ERROR] Unexpected response: {json.dumps(data)[:500]}"
    
    def health(self) -> bool:
        """Sprawdza czy Gemini działa."""
        try:
            resp = self.generate("ping")
            return "[ERROR]" not in resp
        except Exception:
            return False
