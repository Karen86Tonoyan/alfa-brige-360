"""
ALFA_SEAT — Base Adapter
Abstract base class for all model adapters.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger("ALFA.Seat.Adapter")


class BaseAdapter(ABC):
    """
    Base adapter for AI models.
    
    All model adapters must implement:
    - plan(): Create execution plan
    - generate(): Generate code/content
    - analyze(): Analyze content
    """
    
    name: str = "base"
    model_type: str = "unknown"  # cloud / local
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._initialized = False
    
    @abstractmethod
    async def plan(self, instruction: str, context: Optional[Dict] = None) -> str:
        """
        Create execution plan from instruction.
        
        Args:
            instruction: What to plan
            context: Additional context
            
        Returns:
            Execution plan as text
        """
        pass
    
    @abstractmethod
    async def generate(self, plan: str, context: Optional[Dict] = None) -> str:
        """
        Generate code/content from plan.
        
        Args:
            plan: Execution plan
            context: Additional context
            
        Returns:
            Generated content
        """
        pass
    
    @abstractmethod
    async def analyze(self, content: str, context: Optional[Dict] = None) -> str:
        """
        Analyze content and provide insights.
        
        Args:
            content: Content to analyze
            context: Additional context
            
        Returns:
            Analysis result
        """
        pass
    
    async def health_check(self) -> bool:
        """Check if adapter is operational."""
        return True
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} type={self.model_type}>"
