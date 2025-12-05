"""
ALFA_SEAT — Model Adapters
Base adapter and implementations for each AI model.
"""

from .base import BaseAdapter
from .gpt import GPTAdapter
from .claude import ClaudeAdapter
from .gemini import GeminiAdapter
from .deepseek import DeepSeekAdapter
from .ollama import OllamaAdapter

__all__ = [
    "BaseAdapter",
    "GPTAdapter",
    "ClaudeAdapter",
    "GeminiAdapter",
    "DeepSeekAdapter",
    "OllamaAdapter",
]
