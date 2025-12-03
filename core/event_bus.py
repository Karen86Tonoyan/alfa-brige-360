# ═══════════════════════════════════════════════════════════════════════════
# ALFA CORE v2.0 — EVENT BUS — Magistrala Zdarzeń
# ═══════════════════════════════════════════════════════════════════════════
"""
Centralny Event Bus z:
- Publish/Subscribe pattern
- Async event handling
- Event priority & filtering
- Dead letter queue dla nieobsłużonych
- Audit log z timestampami
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from queue import PriorityQueue
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LOG = logging.getLogger("alfa.eventbus")

class Priority(IntEnum):
    """Priorytety zdarzeń — niższy = pilniejszy"""
    CRITICAL = 0   # Cerber, security alerts
    HIGH = 10      # User commands, API calls
    NORMAL = 50    # Standard plugin events
    LOW = 100      # Background tasks, cleanup
    IDLE = 200     # Telemetry, analytics

# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(order=True)
class Event:
    """Zdarzenie systemowe"""
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
    """Subskrypcja na topic"""
    topic_pattern: str
    callback: Callable[[Event], Any]
    subscriber_id: str
    async_handler: bool = False
    priority_filter: Optional[int] = None  # tylko eventy >= ten priorytet

# ═══════════════════════════════════════════════════════════════════════════
# DEAD LETTER QUEUE
# ═══════════════════════════════════════════════════════════════════════════

class DeadLetterQueue:
    """Kolejka dla nieobsłużonych zdarzeń"""
    
    def __init__(self, max_size: int = 1000):
        self._queue: List[tuple[Event, str]] = []
        self._max_size = max_size
        self._lock = threading.Lock()
    
    def push(self, event: Event, reason: str):
        with self._lock:
            if len(self._queue) >= self._max_size:
                self._queue.pop(0)  # FIFO eviction
            self._queue.append((event, reason))
            LOG.warning(f"[DLQ] Event {event.event_id} -> DLQ: {reason}")
    
    def pop(self) -> Optional[tuple[Event, str]]:
        with self._lock:
            return self._queue.pop(0) if self._queue else None
    
    def peek(self, n: int = 10) -> List[tuple[Event, str]]:
        with self._lock:
            return self._queue[-n:]
    
    def size(self) -> int:
        return len(self._queue)

# ═══════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════

class EventAuditLog:
    """Log audytowy zdarzeń"""
    
    def __init__(self, max_entries: int = 5000):
        self._log: List[Dict[str, Any]] = []
        self._max_entries = max_entries
        self._lock = threading.Lock()
    
    def record(self, event: Event, status: str, handler: str = ""):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_id": event.event_id,
            "topic": event.topic,
            "source": event.source,
            "priority": event.priority,
            "status": status,
            "handler": handler
        }
        with self._lock:
            if len(self._log) >= self._max_entries:
                self._log.pop(0)
            self._log.append(entry)
    
    def query(self, 
              topic: Optional[str] = None,
              status: Optional[str] = None,
              limit: int = 100) -> List[Dict]:
        with self._lock:
            results = self._log.copy()
        
        if topic:
            results = [e for e in results if topic in e["topic"]]
        if status:
            results = [e for e in results if e["status"] == status]
        
        return results[-limit:]

# ═══════════════════════════════════════════════════════════════════════════
# EVENT BUS CORE
# ═══════════════════════════════════════════════════════════════════════════

class EventBus:
    """
    Centralna magistrala zdarzeń ALFA System.
    
    Topics:
        system.*      — boot, shutdown, health
        cerber.*      — security events
        user.*        — commands, input
        plugin.*      — load, unload, error
        mcp.*         — MCP server calls
        mail.*        — IMAP, compose, send
        voice.*       — STT, TTS events
        bridge.*      — AI router events
    """
    
    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "EventBus":
        """Singleton pattern"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._queue: PriorityQueue = PriorityQueue()
        self._dlq = DeadLetterQueue()
        self._audit = EventAuditLog()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        
        self._stats = {
            "published": 0,
            "delivered": 0,
            "failed": 0
        }
        
        self._initialized = True
        LOG.info("[EventBus] Initialized (singleton)")
    
    # ─────────────────────────────────────────────────────────────────────
    # SUBSCRIBE / UNSUBSCRIBE
    # ─────────────────────────────────────────────────────────────────────
    
    def subscribe(self,
                  topic: str,
                  callback: Callable[[Event], Any],
                  subscriber_id: str = "",
                  async_handler: bool = False,
                  priority_filter: Optional[int] = None) -> str:
        """
        Subskrybuj na topic.
        
        Args:
            topic: Pattern topiku (wspiera wildcards: user.*, *.error)
            callback: Funkcja do wywołania
            subscriber_id: Identyfikator subskrybenta
            async_handler: Czy callback jest async
            priority_filter: Filtruj eventy (tylko >= ten priorytet)
        
        Returns:
            subscription_id
        """
        if not subscriber_id:
            subscriber_id = f"sub_{len(self._subscriptions)}_{int(time.time())}"
        
        sub = Subscription(
            topic_pattern=topic,
            callback=callback,
            subscriber_id=subscriber_id,
            async_handler=async_handler,
            priority_filter=priority_filter
        )
        
        self._subscriptions[topic].append(sub)
        LOG.debug(f"[EventBus] {subscriber_id} subscribed to '{topic}'")
        return subscriber_id
    
    def unsubscribe(self, topic: str, subscriber_id: str) -> bool:
        """Odsubskrybuj z topiku"""
        if topic in self._subscriptions:
            before = len(self._subscriptions[topic])
            self._subscriptions[topic] = [
                s for s in self._subscriptions[topic]
                if s.subscriber_id != subscriber_id
            ]
            removed = before - len(self._subscriptions[topic])
            if removed > 0:
                LOG.debug(f"[EventBus] {subscriber_id} unsubscribed from '{topic}'")
                return True
        return False
    
    def unsubscribe_all(self, subscriber_id: str) -> int:
        """Usuń wszystkie subskrypcje danego subskrybenta"""
        count = 0
        for topic in list(self._subscriptions.keys()):
            before = len(self._subscriptions[topic])
            self._subscriptions[topic] = [
                s for s in self._subscriptions[topic]
                if s.subscriber_id != subscriber_id
            ]
            count += before - len(self._subscriptions[topic])
        return count
    
    # ─────────────────────────────────────────────────────────────────────
    # PUBLISH
    # ─────────────────────────────────────────────────────────────────────
    
    def publish(self,
                topic: str,
                payload: Any = None,
                source: str = "system",
                priority: int = Priority.NORMAL) -> str:
        """
        Opublikuj zdarzenie.
        
        Args:
            topic: Topic zdarzenia (np. "user.command", "cerber.alert")
            payload: Dane zdarzenia
            source: Źródło (plugin id, moduł)
            priority: Priorytet (Priority.*)
        
        Returns:
            event_id
        """
        event = Event(
            priority=priority,
            topic=topic,
            payload=payload,
            source=source
        )
        
        self._queue.put(event)
        self._stats["published"] += 1
        LOG.debug(f"[EventBus] Published: {event.event_id}")
        
        # Synchronous delivery jeśli nie running worker
        if not self._running:
            self._process_one()
        
        return event.event_id
    
    def emit(self, topic: str, payload: Any = None, **kwargs) -> str:
        """Alias dla publish()"""
        return self.publish(topic, payload, **kwargs)
    
    # ─────────────────────────────────────────────────────────────────────
    # PROCESSING
    # ─────────────────────────────────────────────────────────────────────
    
    def _match_topic(self, pattern: str, topic: str) -> bool:
        """Sprawdź czy topic pasuje do patternu (wspiera wildcards)"""
        if pattern == topic:
            return True
        if pattern == "*":
            return True
        
        # Wildcard matching
        if "*" in pattern:
            parts_p = pattern.split(".")
            parts_t = topic.split(".")
            
            if len(parts_p) != len(parts_t) and "*" not in parts_p:
                return False
            
            for p, t in zip(parts_p, parts_t):
                if p == "*":
                    continue
                if p != t:
                    return False
            return True
        
        return False
    
    def _get_subscribers(self, event: Event) -> List[Subscription]:
        """Znajdź wszystkich subskrybentów dla eventu"""
        subscribers = []
        
        for pattern, subs in self._subscriptions.items():
            if self._match_topic(pattern, event.topic):
                for sub in subs:
                    # Priority filter
                    if sub.priority_filter is not None:
                        if event.priority < sub.priority_filter:
                            continue
                    subscribers.append(sub)
        
        return subscribers
    
    def _deliver(self, event: Event, sub: Subscription) -> bool:
        """Dostarcz event do subskrybenta"""
        try:
            if sub.async_handler:
                if self._async_loop:
                    asyncio.run_coroutine_threadsafe(
                        sub.callback(event),
                        self._async_loop
                    )
                else:
                    # Fallback: run sync
                    result = sub.callback(event)
                    if asyncio.iscoroutine(result):
                        asyncio.run(result)
            else:
                sub.callback(event)
            
            self._stats["delivered"] += 1
            self._audit.record(event, "delivered", sub.subscriber_id)
            return True
            
        except Exception as e:
            LOG.error(f"[EventBus] Delivery failed to {sub.subscriber_id}: {e}")
            self._stats["failed"] += 1
            self._audit.record(event, "failed", sub.subscriber_id)
            return False
    
    def _process_one(self) -> bool:
        """Przetwórz jeden event z kolejki"""
        if self._queue.empty():
            return False
        
        event = self._queue.get()
        subscribers = self._get_subscribers(event)
        
        if not subscribers:
            self._dlq.push(event, "no_subscribers")
            self._audit.record(event, "no_subscribers")
            return True
        
        delivered = 0
        for sub in subscribers:
            if self._deliver(event, sub):
                delivered += 1
        
        if delivered == 0:
            self._dlq.push(event, "all_failed")
        
        return True
    
    def _worker_loop(self):
        """Worker thread loop"""
        LOG.info("[EventBus] Worker started")
        while self._running:
            try:
                if not self._queue.empty():
                    self._process_one()
                else:
                    time.sleep(0.01)  # 10ms idle
            except Exception as e:
                LOG.error(f"[EventBus] Worker error: {e}")
        LOG.info("[EventBus] Worker stopped")
    
    # ─────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────
    
    def start(self, async_loop: Optional[asyncio.AbstractEventLoop] = None):
        """Uruchom EventBus worker thread"""
        if self._running:
            return
        
        self._running = True
        self._async_loop = async_loop
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="EventBus-Worker"
        )
        self._worker_thread.start()
        
        # Emit boot event
        self.publish("system.eventbus.started", source="eventbus", priority=Priority.HIGH)
    
    def stop(self, timeout: float = 5.0):
        """Zatrzymaj EventBus"""
        if not self._running:
            return
        
        self.publish("system.eventbus.stopping", source="eventbus", priority=Priority.CRITICAL)
        self._running = False
        
        if self._worker_thread:
            self._worker_thread.join(timeout=timeout)
            self._worker_thread = None
        
        LOG.info(f"[EventBus] Stopped. Stats: {self._stats}")
    
    def flush(self):
        """Przetwórz wszystkie zaległe eventy"""
        while not self._queue.empty():
            self._process_one()
    
    # ─────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────
    
    def stats(self) -> Dict[str, Any]:
        """Zwróć statystyki"""
        return {
            **self._stats,
            "queue_size": self._queue.qsize(),
            "dlq_size": self._dlq.size(),
            "subscriptions": sum(len(s) for s in self._subscriptions.values())
        }
    
    def topics(self) -> Set[str]:
        """Zwróć wszystkie zarejestrowane topics"""
        return set(self._subscriptions.keys())
    
    def audit_log(self, **filters) -> List[Dict]:
        """Pobierz audit log"""
        return self._audit.query(**filters)
    
    def dead_letters(self, n: int = 10) -> List[tuple]:
        """Pobierz ostatnie dead letters"""
        return self._dlq.peek(n)
    
    def replay_dead_letter(self) -> Optional[str]:
        """Wyślij ponownie najstarszy dead letter"""
        item = self._dlq.pop()
        if item:
            event, reason = item
            self._queue.put(event)
            LOG.info(f"[EventBus] Replayed dead letter: {event.event_id}")
            return event.event_id
        return None

# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE / SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════

def get_bus() -> EventBus:
    """Pobierz singleton EventBus"""
    return EventBus()

def subscribe(topic: str, callback: Callable[[Event], Any], **kwargs) -> str:
    """Convenience: subscribe do globalnego busa"""
    return get_bus().subscribe(topic, callback, **kwargs)

def publish(topic: str, payload: Any = None, **kwargs) -> str:
    """Convenience: publish do globalnego busa"""
    return get_bus().publish(topic, payload, **kwargs)

def emit(topic: str, payload: Any = None, **kwargs) -> str:
    """Alias dla publish"""
    return publish(topic, payload, **kwargs)

# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    bus = EventBus()
    
    # Sample handlers
    def on_user_command(event: Event):
        print(f"[Handler] User command: {event.payload}")
    
    def on_system_event(event: Event):
        print(f"[Handler] System: {event.topic} -> {event.payload}")
    
    # Subscribe
    bus.subscribe("user.*", on_user_command, subscriber_id="cli")
    bus.subscribe("system.*", on_system_event, subscriber_id="monitor")
    
    # Start worker
    bus.start()
    
    # Publish events
    bus.publish("system.boot", {"version": "2.0"}, priority=Priority.HIGH)
    bus.publish("user.command", {"cmd": "help"}, source="cli")
    bus.publish("plugin.loaded", {"name": "mail"}, priority=Priority.LOW)
    
    time.sleep(0.5)
    
    print("\n=== Stats ===")
    print(bus.stats())
    
    print("\n=== Audit Log ===")
    for entry in bus.audit_log(limit=5):
        print(entry)
    
    bus.stop()
