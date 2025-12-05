"""
ALFA_CORE_KERNEL v3.0 — EVENT BUS
System eventów dla komunikacji między komponentami.
"""

import asyncio
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger("ALFA.EventBus")


class EventType(Enum):
    # Kernel events
    KERNEL_START = "kernel.start"
    KERNEL_STOP = "kernel.stop"
    KERNEL_ERROR = "kernel.error"
    
    # Request events
    REQUEST_RECEIVED = "request.received"
    REQUEST_PROCESSED = "request.processed"
    REQUEST_FAILED = "request.failed"
    
    # Provider events
    PROVIDER_LOADED = "provider.loaded"
    PROVIDER_FAILED = "provider.failed"
    PROVIDER_SWITCHED = "provider.switched"
    
    # Security events
    SECURITY_BLOCK = "security.block"
    SECURITY_WARN = "security.warn"
    
    # Memory events
    MEMORY_SAVE = "memory.save"
    MEMORY_LOAD = "memory.load"
    
    # Delta events
    DELTA_MESSAGE_IN = "delta.message.in"
    DELTA_MESSAGE_OUT = "delta.message.out"


@dataclass
class Event:
    """Pojedyncze zdarzenie w systemie."""
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.now)


class EventBus:
    """
    Centralny bus eventów ALFA_KERNEL.
    Umożliwia luźne powiązanie komponentów.
    """
    
    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {}
        self._async_handlers: Dict[EventType, List[Callable]] = {}
        self._history: List[Event] = []
        self._max_history = 1000
    
    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """Subskrybuje handler do typu eventu."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to {event_type.value}")
    
    def subscribe_async(self, event_type: EventType, handler: Callable) -> None:
        """Subskrybuje async handler."""
        if event_type not in self._async_handlers:
            self._async_handlers[event_type] = []
        self._async_handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        """Odsubskrybowuje handler."""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
    
    def emit(self, event: Event) -> None:
        """Emituje event synchronicznie."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.type.value}: {e}")
    
    async def emit_async(self, event: Event) -> None:
        """Emituje event asynchronicznie."""
        self._history.append(event)
        
        # Sync handlers
        for handler in self._handlers.get(event.type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Sync handler error: {e}")
        
        # Async handlers
        for handler in self._async_handlers.get(event.type, []):
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Async handler error: {e}")
    
    def emit_simple(self, event_type: EventType, data: Dict = None, source: str = "kernel") -> None:
        """Uproszczona emisja eventu."""
        event = Event(type=event_type, data=data or {}, source=source)
        self.emit(event)
    
    def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """Zwraca historię eventów."""
        if event_type:
            filtered = [e for e in self._history if e.type == event_type]
            return filtered[-limit:]
        return self._history[-limit:]
    
    def clear_history(self) -> None:
        """Czyści historię."""
        self._history = []


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Zwraca globalną instancję event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
