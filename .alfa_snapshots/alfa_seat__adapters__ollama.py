"""
ALFA_SEAT — Ollama Adapter (Local Models)
"""

import os
import logging
import httpx
from typing import Optional, Dict

from .base import BaseAdapter

logger = logging.getLogger("ALFA.Seat.Ollama")


class OllamaAdapter(BaseAdapter):
    """Ollama local model adapter."""
    
    model_type = "local"
    
    def __init__(self, model: str = "mistral", base_url: Optional[str] = None):
        super().__init__()
        self.model = model
        self.name = f"Ollama ({model})"
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    async def _call(self, prompt: str) -> str:
        """Make API call to Ollama."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                response.raise_for_status()
                return response.json().get("response", "")
        except httpx.ConnectError:
            logger.warning(f"Ollama not running at {self.base_url}")
            return f"[Ollama] Server not available at {self.base_url}"
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return f"[Ollama Error] {str(e)}"
    
    async def plan(self, instruction: str, context: Optional[Dict] = None) -> str:
        prompt = f"""You are a software architect. Create a detailed execution plan.

TASK:
{instruction}

Provide a structured plan with numbered steps."""
        
        return await self._call(prompt)
    
    async def generate(self, plan: str, context: Optional[Dict] = None) -> str:
        prompt = f"""You are a developer. Generate code based on this plan:

PLAN:
{plan}

Generate clean, working code with comments."""
        
        return await self._call(prompt)
    
    async def analyze(self, content: str, context: Optional[Dict] = None) -> str:
        prompt = f"""You are a code reviewer. Analyze this code:

CODE:
{content}

Provide analysis on quality, bugs, and improvements."""
        
        return await self._call(prompt)
    
    async def health_check(self) -> bool:
        """Check if Ollama is running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False
