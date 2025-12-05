"""
ALFA_SEAT — Gemini Adapter (Google)
"""

import os
import logging
from typing import Optional, Dict

from .base import BaseAdapter

logger = logging.getLogger("ALFA.Seat.Gemini")


class GeminiAdapter(BaseAdapter):
    """Google Gemini adapter."""
    
    name = "Gemini 2.0 Flash"
    model_type = "cloud"
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash-exp"):
        super().__init__(api_key or os.getenv("GEMINI_API_KEY"))
        self.model = model
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(self.model)
            except ImportError:
                logger.warning("Google GenAI not installed. Run: pip install google-generativeai")
        return self._client
    
    async def _call(self, prompt: str) -> str:
        """Make API call to Gemini."""
        client = self._get_client()
        if not client:
            return "[Gemini] Google GenAI not available"
        
        try:
            response = await client.generate_content_async(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"[Gemini Error] {str(e)}"
    
    async def plan(self, instruction: str, context: Optional[Dict] = None) -> str:
        prompt = f"""You are a software architect. Create a detailed execution plan.

INSTRUCTION:
{instruction}

Create a structured plan with:
1. Overview
2. Components needed
3. Step-by-step implementation
4. Testing strategy
5. Potential challenges"""
        
        return await self._call(prompt)
    
    async def generate(self, plan: str, context: Optional[Dict] = None) -> str:
        prompt = f"""You are a senior developer. Generate production-quality code.

PLAN:
{plan}

Generate complete, working code with:
- Clear structure
- Error handling
- Comments
- Type hints where applicable"""
        
        return await self._call(prompt)
    
    async def analyze(self, content: str, context: Optional[Dict] = None) -> str:
        prompt = f"""You are a code reviewer and QA specialist.

CODE TO ANALYZE:
{content}

Provide analysis covering:
1. Code quality assessment
2. Bug detection
3. Security review
4. Performance analysis
5. Improvement suggestions
6. Test cases to add"""
        
        return await self._call(prompt)
    
    async def health_check(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0
