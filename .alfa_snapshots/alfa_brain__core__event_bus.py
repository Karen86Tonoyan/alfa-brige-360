# ═══════════════════════════════════════════════════════════════════════════
# ALFA_BRAIN v2.0 — EVENT BUS
# ═══════════════════════════════════════════════════════════════════════════
"""
Magistrala zdarzeń dla komunikacji między modułami.

Features:
- Publish/Subscribe pattern
- Priority queue
- Dead letter queue
- Audit logging

Usage:
    from core.event_bus import EventBus, get_bus, publish, subscribe
    
    bus = get_bus()
    bus.subscribe("user.*", handler)
    bus.publish("user.command", {"cmd": "help"})
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from queue import PriorityQueue
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict

LOG = logging.getLogger("alfa.eventbus")

# ═══════════════════════════════════════════════════════════════════════════
# PRIORITY
# ═══════════════════════════════════════════════════════════════════════════

class Priority(IntEnum):
    CRITICAL = 0
    HIGH = 10
    NORMAL = 50
    LOW = 100
    IDLE = 200

# ═══════════════════════════════════════════════════════════════════════════
# EVENT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(order=True)
class Event:
    priority: int = field(compare=True)
    timestamp: float = field(compare=False, default_factory=time.time)
    topic: str = field(compare=False, default="")
    payload: Any = field(compare=False, default=None)
    source: str = field(compare=False, default="unknown")
    event_id: str = field(compare=False, default="")
    
    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"{self.topic}:{int(self.timestamp * 1000)}"

@dataclass
class Subscription:
    topic_pattern: str
    callback: Callable[[Event], Any]
    subscriber_id: str
    async_handler: bool = False

# ═══════════════════════════════════════════════════════════════════════════
# EVENT BUS
# ═══════════════════════════════════════════════════════════════════════════

class EventBus:
    """Central event bus for ALFA system."""
    
    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "EventBus":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._queue: PriorityQueue = PriorityQueue()
        self._dlq: List[tuple] = []
        self._audit: List[Dict] = []
        self._running = False
        self._worker: Optional[threading.Thread] = None
        self._stats = {"published": 0, "delivered": 0, "failed": 0}
        
        self._initialized = True
        LOG.info("[EventBus] Initialized")
    
    def subscribe(self, topic: str, callback: Callable, subscriber_id: str = "") -> str:
        """Subscribe to topic pattern"""
        if not subscriber_id:
            subscriber_id = f"sub_{len(self._subscriptions)}_{int(time.time())}"
        
        sub = Subscription(topic, callback, subscriber_id)
        self._subscriptions[topic].append(sub)
        LOG.debug(f"[EventBus] {subscriber_id} -> {topic}")
        return subscriber_id
    
    def unsubscribe_all(self, subscriber_id: str) -> int:
        """Remove all subscriptions for subscriber"""
        count = 0
        for topic in list(self._subscriptions.keys()):
            before = len(self._subscriptions[topic])
            self._subscriptions[topic] = [
                s for s in self._subscriptions[topic] if s.subscriber_id != subscriber_id
            ]
            count += before - len(self._subscriptions[topic])
        return count
    
    def publish(self, topic: str, payload: Any = None, source: str = "system", priority: int = Priority.NORMAL) -> str:
        """Publish event"""
        event = Event(priority=priority, topic=topic, payload=payload, source=source)
        self._queue.put(event)
        self._stats["published"] += 1
        
        if not self._running:
            self._process_one()
        
        return event.event_id
    
    def _match_topic(self, pattern: str, topic: str) -> bool:
        if pattern == topic or pattern == "*":
            return True
        if "*" in pattern:
            parts_p = pattern.split(".")
            parts_t = topic.split(".")
            for p, t in zip(parts_p, parts_t):
                if p == "*":
                    continue
                if p != t:
                    return False
            return len(parts_p) == len(parts_t) or parts_p[-1] == "*"
        return False
    
    def _process_one(self) -> bool:
        if self._queue.empty():
            return False
        
        event = self._queue.get()
        delivered = 0
        
        for pattern, subs in self._subscriptions.items():
            if self._match_topic(pattern, event.topic):
                for sub in subs:
                    try:
                        sub.callback(event)
                        delivered += 1
                        self._stats["delivered"] += 1
                    except Exception as e:
                        LOG.error(f"Delivery failed: {e}")
                        self._stats["failed"] += 1
        
        if delivered == 0:
            self._dlq.append((event, "no_subscribers"))
            if len(self._dlq) > 1000:
                self._dlq.pop(0)
        
        self._audit.append({
            "timestamp": datetime.now().isoformat(),
            "event_id": event.event_id,
            "topic": event.topic,
            "delivered": delivered
        })
        if len(self._audit) > 5000:
            self._audit.pop(0)
        
        return True
    
    def _worker_loop(self):
        LOG.info("[EventBus] Worker started")
        while self._running:
            if not self._queue.empty():
                self._process_one()
            else:
                time.sleep(0.01)
        LOG.info("[EventBus] Worker stopped")
    
    def start(self):
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="EventBus")
        self._worker.start()
    
    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._worker:
            self._worker.join(timeout=5.0)
        LOG.info(f"[EventBus] Stopped. Stats: {self._stats}")
    
    def stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "queue_size": self._queue.qsize(),
            "dlq_size": len(self._dlq),
            "subscriptions": sum(len(s) for s in self._subscriptions.values())
        }
    
    def topics(self) -> Set[str]:
        return set(self._subscriptions.keys())
    
    def audit_log(self, limit: int = 100) -> List[Dict]:
        return self._audit[-limit:]
    
    def dead_letters(self, n: int = 10) -> List[tuple]:
        return self._dlq[-n:]

# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE
# ═══════════════════════════════════════════════════════════════════════════

def get_bus() -> EventBus:
    return EventBus()

def subscribe(topic: str, callback: Callable, **kwargs) -> str:
    return get_bus().subscribe(topic, callback, **kwargs)

def publish(topic: str, payload: Any = None, **kwargs) -> str:
    return get_bus().publish(topic, payload, **kwargs)

def emit(topic: str, payload: Any = None, **kwargs) -> str:
    return publish(topic, payload, **kwargs)

__all__ = ["EventBus", "Event", "Priority", "get_bus", "subscribe", "publish", "emit"]
