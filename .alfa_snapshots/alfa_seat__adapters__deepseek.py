"""
ALFA_SEAT — DeepSeek Adapter
"""

import os
import logging
from typing import Optional, Dict

from .base import BaseAdapter

logger = logging.getLogger("ALFA.Seat.DeepSeek")


class DeepSeekAdapter(BaseAdapter):
    """DeepSeek adapter."""
    
    name = "DeepSeek R1"
    model_type = "cloud"
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        super().__init__(api_key or os.getenv("DEEPSEEK_API_KEY"))
        self.model = model
        self.base_url = "https://api.deepseek.com/v1"
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            except ImportError:
                logger.warning("OpenAI not installed. Run: pip install openai")
        return self._client
    
    async def _call(self, system: str, user: str) -> str:
        """Make API call to DeepSeek."""
        client = self._get_client()
        if not client:
            return "[DeepSeek] Client not available"
        
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
            logger.error(f"DeepSeek API error: {e}")
            return f"[DeepSeek Error] {str(e)}"
    
    async def plan(self, instruction: str, context: Optional[Dict] = None) -> str:
        system = """You are an AI system architect specializing in detailed planning.
        Create comprehensive execution plans with clear steps and dependencies."""
        
        return await self._call(system, instruction)
    
    async def generate(self, plan: str, context: Optional[Dict] = None) -> str:
        system = """You are a code generation specialist.
        Generate clean, efficient, production-ready code following the plan."""
        
        return await self._call(system, plan)
    
    async def analyze(self, content: str, context: Optional[Dict] = None) -> str:
        system = """You are a deep analysis AI. Provide thorough analysis with:
        - Pattern recognition
        - Logical assessment
        - Risk identification
        - Optimization opportunities
        - Strategic recommendations"""
        
        return await self._call(system, content)
    
    async def health_check(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0
