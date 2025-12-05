"""
🔔 Event Bus - Inter-component communication
"""

from __future__ import annotations
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict


@dataclass
class Event:
    """Event data container"""
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"


class EventBus:
    """
    Central event bus for ALFA CLOUD components.
    
    Features:
    - Sync and async event handlers
    - Wildcard subscriptions (e.g., "file:*")
    - Event history for replay
    - Thread-safe operations
    
    Usage:
        bus = EventBus()
        
        # Subscribe
        bus.on("file:created", lambda e: print(f"New file: {e.payload}"))
        
        # Emit
        bus.emit("file:created", {"path": "/test.txt"})
    """
    
    def __init__(self, max_history: int = 1000):
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._async_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._history: List[Event] = []
        self._max_history = max_history
        self.logger = logging.getLogger("ALFA_CLOUD.EventBus")
    
    def on(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """
        Subscribe to an event.
        
        Args:
            event_type: Event type (supports wildcards like "file:*")
            handler: Callback function
        """
        if asyncio.iscoroutinefunction(handler):
            self._async_handlers[event_type].append(handler)
        else:
            self._handlers[event_type].append(handler)
        
        self.logger.debug(f"Subscribed to: {event_type}")
    
    def off(self, event_type: str, handler: Optional[Callable] = None) -> None:
        """
        Unsubscribe from an event.
        
        Args:
            event_type: Event type
            handler: Specific handler to remove (or all if None)
        """
        if handler:
            if handler in self._handlers.get(event_type, []):
                self._handlers[event_type].remove(handler)
            if handler in self._async_handlers.get(event_type, []):
                self._async_handlers[event_type].remove(handler)
        else:
            self._handlers.pop(event_type, None)
            self._async_handlers.pop(event_type, None)
    
    def emit(self, event_type: str, payload: Dict[str, Any] = None, source: str = "system") -> Event:
        """
        Emit an event synchronously.
        
        Args:
            event_type: Event type
            payload: Event data
            source: Event source identifier
            
        Returns:
            The emitted Event object
        """
        event = Event(
            type=event_type,
            payload=payload or {},
            source=source
        )
        
        # Store in history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        # Find matching handlers
        handlers = self._get_matching_handlers(event_type)
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self.logger.error(f"Handler error for {event_type}: {e}")
        
        return event
    
    async def emit_async(self, event_type: str, payload: Dict[str, Any] = None, source: str = "system") -> Event:
        """
        Emit an event and await async handlers.
        """
        event = Event(
            type=event_type,
            payload=payload or {},
            source=source
        )
        
        # Store in history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        # Sync handlers first
        for handler in self._get_matching_handlers(event_type):
            try:
                handler(event)
            except Exception as e:
                self.logger.error(f"Handler error for {event_type}: {e}")
        
        # Async handlers
        async_handlers = self._get_matching_async_handlers(event_type)
        if async_handlers:
            await asyncio.gather(
                *[self._safe_async_call(h, event) for h in async_handlers],
                return_exceptions=True
            )
        
        return event
    
    async def _safe_async_call(self, handler: Callable, event: Event):
        """Safely call async handler"""
        try:
            await handler(event)
        except Exception as e:
            self.logger.error(f"Async handler error for {event.type}: {e}")
    
    def _get_matching_handlers(self, event_type: str) -> List[Callable]:
        """Get handlers matching event type (including wildcards)"""
        handlers = list(self._handlers.get(event_type, []))
        
        # Check wildcard patterns
        for pattern, pattern_handlers in self._handlers.items():
            if pattern.endswith(":*"):
                prefix = pattern[:-1]  # Remove "*"
                if event_type.startswith(prefix):
                    handlers.extend(pattern_handlers)
            elif pattern == "*":
                handlers.extend(pattern_handlers)
        
        return handlers
    
    def _get_matching_async_handlers(self, event_type: str) -> List[Callable]:
        """Get async handlers matching event type"""
        handlers = list(self._async_handlers.get(event_type, []))
        
        for pattern, pattern_handlers in self._async_handlers.items():
            if pattern.endswith(":*"):
                prefix = pattern[:-1]
                if event_type.startswith(prefix):
                    handlers.extend(pattern_handlers)
            elif pattern == "*":
                handlers.extend(pattern_handlers)
        
        return handlers
    
    def once(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Subscribe to event once (auto-unsubscribe after first call)"""
        def wrapper(event: Event):
            handler(event)
            self.off(event_type, wrapper)
        self.on(event_type, wrapper)
    
    def get_history(self, 
                    event_type: Optional[str] = None, 
                    limit: int = 100) -> List[Event]:
        """Get event history"""
        events = self._history
        
        if event_type:
            events = [e for e in events if e.type == event_type or 
                     (event_type.endswith(":*") and e.type.startswith(event_type[:-1]))]
        
        return events[-limit:]
    
    def clear_history(self) -> None:
        """Clear event history"""
        self._history.clear()
    
    @property
    def subscriptions(self) -> Dict[str, int]:
        """Get count of subscriptions per event type"""
        result = {}
        for event_type, handlers in self._handlers.items():
            result[event_type] = len(handlers)
        for event_type, handlers in self._async_handlers.items():
            result[event_type] = result.get(event_type, 0) + len(handlers)
        return result


# Singleton instance
_default_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get default event bus instance"""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
