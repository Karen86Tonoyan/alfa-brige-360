"""
ALFA_SEAT — Claude Adapter (Anthropic)
"""

import os
import logging
from typing import Optional, Dict

from .base import BaseAdapter

logger = logging.getLogger("ALFA.Seat.Claude")


class ClaudeAdapter(BaseAdapter):
    """Anthropic Claude adapter."""
    
    name = "Claude 3.5 Sonnet"
    model_type = "cloud"
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        super().__init__(api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("Anthropic not installed. Run: pip install anthropic")
        return self._client
    
    async def _call(self, system: str, user: str) -> str:
        """Make API call to Anthropic."""
        client = self._get_client()
        if not client:
            return "[Claude] Anthropic not available"
        
        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return f"[Claude Error] {str(e)}"
    
    async def plan(self, instruction: str, context: Optional[Dict] = None) -> str:
        system = """You are a world-class software architect.
        Create a comprehensive, detailed execution plan.
        Consider edge cases, scalability, and maintainability.
        Structure your response as a clear, numbered action plan."""
        
        return await self._call(system, instruction)
    
    async def generate(self, plan: str, context: Optional[Dict] = None) -> str:
        system = """You are an expert developer writing production code.
        Follow the plan precisely. Write clean, well-documented code.
        Include comprehensive error handling and type hints."""
        
        return await self._call(system, plan)
    
    async def analyze(self, content: str, context: Optional[Dict] = None) -> str:
        system = """You are a senior technical lead reviewing code.
        Provide thorough analysis covering:
        - Architecture and design patterns
        - Code quality and maintainability
        - Security vulnerabilities
        - Performance optimizations
        - Test coverage suggestions"""
        
        return await self._call(system, content)
    
    async def health_check(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0
