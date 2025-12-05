"""
ALFA / GEMINI API CLIENT v2.0
Native Google GenerativeAI API z pełną obsługą function_call.
Naprawione parsowanie niespójnych odpowiedzi Google.
Zero chmury. Czysta stal.
"""

import os
import json
import requests
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("ALFA.Gemini")

# Import maskowania z SecretStore
try:
    from alfa_core.security.secret_store import mask_key, get_api_key
    SECURE_STORE_AVAILABLE = True
except ImportError:
    SECURE_STORE_AVAILABLE = False
    def mask_key(key: str, visible_chars: int = 4) -> str:
        """Fallback mask function."""
        if not key:
            return "[EMPTY]"
        if len(key) <= visible_chars * 2:
            return "*" * len(key)
        return key[:visible_chars] + "*" * (len(key) - visible_chars * 2) + key[-visible_chars:]
    
    def get_api_key(name: str) -> Optional[str]:
        """Fallback - just use env."""
        return os.environ.get(name)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "gemini.yaml"

# Dostępne modele Gemini (2024/2025)
GEMINI_MODELS = [
    "gemini-2.0-flash-exp",       # Najnowszy, experimental
    "gemini-2.0-pro-exp",         # Pro experimental
    "gemini-2.0-flash",           # Stable flash
    "gemini-2.0-flash-lite",      # Lekki flash
    "gemini-1.5-pro-latest",      # Pro stable
    "gemini-1.5-flash-latest",    # Flash stable
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]

# Domyślne ustawienia bezpieczeństwa (blokujemy tylko BLOCK_NONE dla ALFA)
DEFAULT_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]


@dataclass
class GeminiConfig:
    """Konfiguracja klienta Gemini."""
    api_key: str = ""
    model: str = "gemini-2.0-flash"
    temperature: float = 0.7
    max_tokens: int = 8192
    timeout: int = 60
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    safety_settings: List[Dict] = field(default_factory=lambda: DEFAULT_SAFETY_SETTINGS)


def load_config() -> GeminiConfig:
    """Załaduj konfigurację Gemini z pliku YAML."""
    cfg_dict = {}
    
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg_dict = yaml.safe_load(f) or {}
    
    # Rozwiń zmienne środowiskowe dla api_key
    api_key = cfg_dict.get("api_key", "")
    if api_key.startswith("${") and api_key.endswith("}"):
        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, "")
    elif not api_key:
        # Fallback do env
        api_key = os.environ.get("GEMINI_API_KEY", "")
    
    return GeminiConfig(
        api_key=api_key,
        model=cfg_dict.get("engine", cfg_dict.get("model", "gemini-2.0-flash")),
        temperature=cfg_dict.get("temperature", 0.7),
        max_tokens=cfg_dict.get("max_tokens", 8192),
        timeout=cfg_dict.get("timeout", 60),
        base_url=cfg_dict.get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
    )


class GeminiAPI:
    """
    Natywny klient Google Gemini API.
    Obsługuje niespójne odpowiedzi Google i function_call.
    """
    
    def __init__(self, config: Optional[GeminiConfig] = None):
        self.config = config or load_config()
        self._validate_config()
        # Log zamaskowany klucz
        logger.info(f"[GeminiAPI] Initialized with key: {mask_key(self.config.api_key)}")
    
    def _validate_config(self):
        """Waliduj konfigurację."""
        if not self.config.api_key:
            raise ValueError("Brak GEMINI_API_KEY w config lub zmiennej środowiskowej")
    
    def _build_url(self, model: Optional[str] = None) -> str:
        """Zbuduj URL endpointu."""
        model_name = model or self.config.model
        return f"{self.config.base_url}/models/{model_name}:generateContent"
    
    def _build_stream_url(self, model: Optional[str] = None) -> str:
        """Zbuduj URL dla streamingu."""
        model_name = model or self.config.model
        return f"{self.config.base_url}/models/{model_name}:streamGenerateContent"
    
    def _extract_text(self, result: Dict[str, Any]) -> str:
        """
        Bezpieczne wyciąganie tekstu z odpowiedzi Gemini.
        Google zwraca różne struktury w zależności od modelu i trybu.
        
        Obsługuje:
        - candidates[0].content.parts[0].text (standard)
        - candidates[0].content.parts[0].functionCall (function calling)
        - candidates[0].text (legacy)
        - Puste odpowiedzi z powodu safety
        """
        try:
            candidates = result.get("candidates", [])
            if not candidates:
                # Sprawdź promptFeedback dla safety block
                feedback = result.get("promptFeedback", {})
                block_reason = feedback.get("blockReason", "")
                if block_reason:
                    logger.warning(f"[Gemini] Prompt zablokowany: {block_reason}")
                    return f"[BLOCKED: {block_reason}]"
                return "[NO_RESPONSE]"
            
            candidate = candidates[0]
            
            # Sprawdź finish reason
            finish_reason = candidate.get("finishReason", "")
            if finish_reason == "SAFETY":
                logger.warning("[Gemini] Odpowiedź zablokowana przez safety")
                return "[BLOCKED: SAFETY]"
            
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                # Legacy format lub pusty
                if "text" in candidate:
                    return candidate["text"].strip()
                return ""
            
            # Zbierz tekst ze wszystkich parts
            texts = []
            for part in parts:
                if "text" in part:
                    texts.append(part["text"])
                elif "functionCall" in part:
                    # Function call - zwróć jako JSON
                    fc = part["functionCall"]
                    texts.append(f"[FUNCTION_CALL: {fc.get('name', 'unknown')}({json.dumps(fc.get('args', {}))})]")
                elif "executableCode" in part:
                    # Code execution response
                    code = part["executableCode"]
                    texts.append(f"```{code.get('language', 'python')}\n{code.get('code', '')}\n```")
                elif "codeExecutionResult" in part:
                    result_part = part["codeExecutionResult"]
                    texts.append(f"[CODE_RESULT: {result_part.get('output', '')}]")
            
            return "\n".join(texts).strip()
            
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"[Gemini] Błąd parsowania odpowiedzi: {e}")
            logger.debug(f"[Gemini] Raw response: {json.dumps(result, indent=2)[:500]}")
            return "[PARSE_ERROR]"
    
    def query(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
    ) -> str:
        """
        Wysyła prompt do Gemini i zwraca odpowiedź.
        
        Args:
            prompt: Treść zapytania
            system_prompt: Opcjonalny system prompt
            model: Opcjonalny model
            temperature: Opcjonalna temperatura
            max_tokens: Opcjonalny limit tokenów
            tools: Opcjonalne definicje funkcji (function calling)
            
        Returns:
            Odpowiedź modelu jako string
        """
        url = self._build_url(model)
        
        # Buduj contents
        contents = []
        
        # System instruction (jeśli podany)
        system_instruction = None
        if system_prompt:
            system_instruction = {"parts": [{"text": system_prompt}]}
        
        # User message
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        # Buduj payload
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature or self.config.temperature,
                "maxOutputTokens": max_tokens or self.config.max_tokens,
            },
            "safetySettings": self.config.safety_settings,
        }
        
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        
        if tools:
            payload["tools"] = tools
        
        headers = {
            "Content-Type": "application/json",
        }
        
        params = {"key": self.config.api_key}
        
        try:
            r = requests.post(
                url,
                json=payload,
                headers=headers,
                params=params,
                timeout=self.config.timeout
            )
            r.raise_for_status()
            data = r.json()
            return self._extract_text(data)
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", error_msg)
            except Exception:
                pass
            logger.error(f"[Gemini] API Error: {error_msg}")
            raise RuntimeError(f"Gemini API Error: {error_msg}") from e
        except requests.exceptions.Timeout:
            logger.error("[Gemini] Request timeout")
            raise RuntimeError("Gemini API Timeout") from None
        except Exception as e:
            logger.error(f"[Gemini] Unexpected error: {e}")
            raise
    
    def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Generator[str, None, None]:
        """
        Streamingowa wersja zapytania Gemini.
        Generuje fragmenty odpowiedzi.
        """
        url = self._build_stream_url(model)
        
        contents = []
        system_instruction = None
        
        if system_prompt:
            system_instruction = {"parts": [{"text": system_prompt}]}
        
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature or self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            },
            "safetySettings": self.config.safety_settings,
        }
        
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        
        headers = {"Content-Type": "application/json"}
        params = {"key": self.config.api_key, "alt": "sse"}
        
        try:
            with requests.post(
                url,
                json=payload,
                headers=headers,
                params=params,
                stream=True,
                timeout=self.config.timeout,
            ) as r:
                r.raise_for_status()
                
                for line in r.iter_lines():
                    if not line:
                        continue
                    
                    line_str = line.decode("utf-8")
                    
                    if line_str.startswith("data: "):
                        json_str = line_str[6:]
                        if json_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(json_str)
                            text = self._extract_text(chunk)
                            if text and not text.startswith("["):
                                yield text
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"[Gemini] Stream error: {e}")
            raise
    
    def health(self) -> bool:
        """Sprawdza czy Gemini API działa."""
        try:
            resp = self.query("ping", system_prompt="Odpowiedz jednym słowem: pong")
            return "pong" in resp.lower()
        except Exception as e:
            logger.error(f"[Gemini] Health check failed: {e}")
            return False
    
    @staticmethod
    def models() -> List[str]:
        """Lista dostępnych modeli Gemini."""
        return GEMINI_MODELS.copy()


# === SINGLETON INSTANCE ===
_gemini_instance: Optional[GeminiAPI] = None


def get_gemini() -> GeminiAPI:
    """Pobierz singleton instancję GeminiAPI."""
    global _gemini_instance
    if _gemini_instance is None:
        _gemini_instance = GeminiAPI()
    return _gemini_instance


# === LEGACY COMPATIBILITY FUNCTIONS ===
def gemini_query(
    prompt: str,
    system_prompt: Optional[str] = None,
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """Legacy wrapper - używa nowego API."""
    return get_gemini().query(
        prompt,
        system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )


def gemini_stream(
    prompt: str,
    system_prompt: Optional[str] = None,
    *,
    model: Optional[str] = None,
) -> Generator[str, None, None]:
    """Legacy wrapper - używa nowego API."""
    return get_gemini().stream(prompt, system_prompt, model=model)


def gemini_health() -> bool:
    """Legacy wrapper - sprawdza health."""
    return get_gemini().health()


def gemini_models() -> List[str]:
    """Legacy wrapper - lista modeli."""
    return GeminiAPI.models()


# === CLI TEST ===
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    print("[ALFA/Gemini v2.0] Test połączenia...")
    
    try:
        api = GeminiAPI()
        print(f"[INFO] Model: {api.config.model}")
        print(f"[INFO] Endpoint: {api.config.base_url}")
        
        if api.health():
            print("[OK] Gemini ONLINE")
            
            # Test zapytania
            if len(sys.argv) > 1:
                query = " ".join(sys.argv[1:])
                print(f"\n[QUERY] {query}")
                response = api.query(query)
                print(f"[RESPONSE]\n{response}")
        else:
            print("[BŁĄD] Gemini OFFLINE lub nieprawidłowy klucz API")
            
    except ValueError as e:
        print(f"[BŁĄD] Konfiguracja: {e}")
    except Exception as e:
        print(f"[BŁĄD] {e}")
