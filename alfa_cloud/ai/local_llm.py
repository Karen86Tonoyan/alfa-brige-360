"""
🤖 ALFA CLOUD LOCAL LLM
Integracja z Ollama dla lokalnego AI
"""

from __future__ import annotations
import json
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, List, Any, AsyncGenerator
import logging

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class LocalLLMConfig:
    """Konfiguracja lokalnego LLM"""
    enabled: bool = True
    provider: str = "ollama"
    endpoint: str = "http://127.0.0.1:11434"
    default_model: str = "llama3"
    models: Dict[str, str] = None
    timeout: float = 120.0
    
    def __post_init__(self):
        if self.models is None:
            self.models = {
                "analysis": "llama3",
                "embedding": "nomic-embed-text",
                "vision": "llava",
                "code": "codellama",
                "fast": "mistral"
            }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCAL LLM CLIENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class LocalLLM:
    """
    🤖 Klient lokalnego LLM (Ollama)
    
    Obsługuje:
    - Generowanie tekstu
    - Streaming
    - Embeddingi
    - Vision (obrazy)
    - Chat z kontekstem
    """
    
    def __init__(self, config: Optional[LocalLLMConfig] = None):
        self.config = config or LocalLLMConfig()
        self.logger = logging.getLogger("ALFA_CLOUD.LocalLLM")
        self._conversation_history: List[Dict[str, str]] = []
    
    @property
    def is_available(self) -> bool:
        """Sprawdza czy Ollama jest dostępne"""
        if not self.config.enabled:
            return False
        
        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.config.endpoint}/api/tags")
                return response.status_code == 200
        except:
            return False
    
    async def list_models(self) -> List[str]:
        """Lista dostępnych modeli"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.config.endpoint}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m.get("name") for m in data.get("models", [])]
        except Exception as e:
            self.logger.error(f"Błąd list_models: {e}")
            return []
    
    async def generate(self, 
                       prompt: str, 
                       model: Optional[str] = None,
                       task: str = "analysis",
                       system: Optional[str] = None,
                       temperature: float = 0.7,
                       max_tokens: int = 2048) -> str:
        """
        Generuje odpowiedź (non-streaming)
        
        Args:
            prompt: Tekst wejściowy
            model: Model do użycia (lub z config dla task)
            task: Typ zadania (analysis, code, fast)
            system: System prompt
            temperature: Temperatura generowania
            max_tokens: Maksymalna długość odpowiedzi
        """
        if not self.config.enabled:
            return "[AI DISABLED]"
        
        # Wybierz model
        model = model or self.config.models.get(task, self.config.default_model)
        
        try:
            import httpx
            
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            if system:
                payload["system"] = system
            
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    f"{self.config.endpoint}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
            
            return data.get("response", "")
            
        except Exception as e:
            self.logger.error(f"Błąd generate: {e}")
            return f"[ERROR: {str(e)}]"
    
    async def stream(self,
                     prompt: str,
                     model: Optional[str] = None,
                     task: str = "analysis",
                     system: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        Generuje odpowiedź ze streamingiem
        
        Yields:
            Fragmenty tekstu
        """
        if not self.config.enabled:
            yield "[AI DISABLED]"
            return
        
        model = model or self.config.models.get(task, self.config.default_model)
        
        try:
            import httpx
            
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": True
            }
            
            if system:
                payload["system"] = system
            
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.config.endpoint}/api/generate",
                    json=payload
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                text = chunk.get("response", "")
                                if text:
                                    yield text
                                if chunk.get("done"):
                                    break
                            except json.JSONDecodeError:
                                pass
                                
        except Exception as e:
            self.logger.error(f"Błąd stream: {e}")
            yield f"[ERROR: {str(e)}]"
    
    async def chat(self,
                   message: str,
                   model: Optional[str] = None,
                   system: Optional[str] = None,
                   reset: bool = False) -> str:
        """
        Chat z zachowaniem kontekstu rozmowy
        
        Args:
            message: Wiadomość użytkownika
            model: Model
            system: System prompt
            reset: Czy zresetować historię
        """
        if reset:
            self._conversation_history = []
        
        model = model or self.config.default_model
        
        # Dodaj wiadomość do historii
        self._conversation_history.append({
            "role": "user",
            "content": message
        })
        
        try:
            import httpx
            
            payload = {
                "model": model,
                "messages": self._conversation_history,
                "stream": False
            }
            
            if system:
                payload["messages"] = [{"role": "system", "content": system}] + payload["messages"]
            
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    f"{self.config.endpoint}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
            
            assistant_message = data.get("message", {}).get("content", "")
            
            # Dodaj odpowiedź do historii
            self._conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
            
        except Exception as e:
            self.logger.error(f"Błąd chat: {e}")
            return f"[ERROR: {str(e)}]"
    
    async def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        """
        Generuje embedding dla tekstu
        
        Args:
            text: Tekst do embedowania
            model: Model embeddings (domyślnie nomic-embed-text)
        
        Returns:
            Wektor embeddings
        """
        model = model or self.config.models.get("embedding", "nomic-embed-text")
        
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.config.endpoint}/api/embeddings",
                    json={"model": model, "prompt": text}
                )
                response.raise_for_status()
                data = response.json()
            
            return data.get("embedding", [])
            
        except Exception as e:
            self.logger.error(f"Błąd embed: {e}")
            return []
    
    async def analyze_image(self, 
                           image_path: str, 
                           prompt: str = "Opisz co widzisz na tym obrazie.",
                           model: Optional[str] = None) -> str:
        """
        Analizuje obraz (vision model)
        
        Args:
            image_path: Ścieżka do obrazu
            prompt: Pytanie o obraz
            model: Model vision (domyślnie llava)
        """
        import base64
        from pathlib import Path
        
        model = model or self.config.models.get("vision", "llava")
        
        # Wczytaj obraz jako base64
        image_data = Path(image_path).read_bytes()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.config.endpoint}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "images": [image_base64],
                        "stream": False
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            return data.get("response", "")
            
        except Exception as e:
            self.logger.error(f"Błąd analyze_image: {e}")
            return f"[ERROR: {str(e)}]"
    
    def clear_history(self):
        """Czyści historię rozmowy"""
        self._conversation_history = []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROMPTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SystemPrompts:
    """Predefiniowane system prompts"""
    
    ALFA_ASSISTANT = """Jesteś ALFA — inteligentnym asystentem AI w systemie ALFA CLOUD OFFLINE.
Twoje zadania:
- Pomagasz w zarządzaniu plikami i danymi
- Analizujesz dokumenty i obrazy
- Odpowiadasz na pytania użytkownika
- Działasz lokalnie, bez wysyłania danych do internetu

Zawsze odpowiadaj po polsku, konkretnie i pomocnie."""

    CODE_ASSISTANT = """Jesteś ekspertem programistą w systemie ALFA CLOUD.
Twoje specjalizacje: Python, Kotlin, JavaScript, SQL.
Zawsze:
- Pisz czysty, czytelny kod
- Dodawaj komentarze
- Sugeruj best practices
- Wskazuj potencjalne problemy"""

    SECURITY_ANALYST = """Jesteś analitykiem bezpieczeństwa w systemie CERBER GUARD.
Twoje zadania:
- Analiza logów i alertów
- Wykrywanie anomalii
- Ocena ryzyka
- Rekomendacje bezpieczeństwa

Odpowiadaj precyzyjnie i technicznie."""

    FILE_ANALYZER = """Analizujesz zawartość plików w chmurze ALFA CLOUD.
Twoje możliwości:
- Podsumowania dokumentów
- Ekstrakcja kluczowych informacji
- Kategoryzacja i tagowanie
- Wyszukiwanie wzorców"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    async def main():
        llm = LocalLLM()
        
        print("🤖 ALFA LOCAL LLM TEST")
        print(f"Available: {llm.is_available}")
        
        if llm.is_available:
            models = await llm.list_models()
            print(f"Models: {models}")
            
            # Test generate
            response = await llm.generate(
                "Powiedz 'Cześć' po polsku",
                system=SystemPrompts.ALFA_ASSISTANT
            )
            print(f"Response: {response}")
            
            # Test stream
            print("\nStreaming: ", end="")
            async for chunk in llm.stream("Napisz haiku o chmurze"):
                print(chunk, end="", flush=True)
            print()
    
    asyncio.run(main())
