"""
ALFA_SEAT — GPT Adapter (OpenAI)
"""

import os
import logging
from typing import Optional, Dict

from .base import BaseAdapter

logger = logging.getLogger("ALFA.Seat.GPT")


class GPTAdapter(BaseAdapter):
    """OpenAI GPT adapter."""
    
    name = "GPT-4"
    model_type = "cloud"
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo"):
        super().__init__(api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("OpenAI not installed. Run: pip install openai")
        return self._client
    
    async def _call(self, system: str, user: str) -> str:
        """Make API call to OpenAI."""
        client = self._get_client()
        if not client:
            return "[GPT] OpenAI not available"
        
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                temperature=0.7,
                max_tokens=4096
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"GPT API error: {e}")
            return f"[GPT Error] {str(e)}"
    
    async def plan(self, instruction: str, context: Optional[Dict] = None) -> str:
        system = """You are a software architect. Create a detailed execution plan.
        Be specific about steps, components, and dependencies.
        Format as numbered list."""
        
        return await self._call(system, instruction)
    
    async def generate(self, plan: str, context: Optional[Dict] = None) -> str:
        system = """You are a senior developer. Generate production-quality code.
        Follow the plan exactly. Include comments and error handling."""
        
        return await self._call(system, plan)
    
    async def analyze(self, content: str, context: Optional[Dict] = None) -> str:
        system = """You are a code reviewer. Analyze the code for:
        - Bugs and potential issues
        - Performance improvements
        - Security concerns
        - Best practices"""
        
        return await self._call(system, content)
    
    async def health_check(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0
