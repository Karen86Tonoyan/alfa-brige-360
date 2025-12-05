"""
ALFA DELTA v1 — QUEUE
Asynchroniczna kolejka wiadomości.
"""

from typing import Optional, Dict, Any, Callable
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger("ALFA.Delta.Queue")


class MessageStatus(Enum):
    """Status wiadomości w kolejce."""
    PENDING = auto()
    PROCESSING = auto()
    SENT = auto()
    FAILED = auto()


@dataclass
class QueuedMessage:
    """Wiadomość w kolejce."""
    id: str
    to: str
    text: str
    attachments: list = field(default_factory=list)
    priority: int = 0
    status: MessageStatus = MessageStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    created_at: float = field(default_factory=time.time)
    error: Optional[str] = None
    
    def __lt__(self, other):
        """Porównanie dla priority queue."""
        return self.priority > other.priority


class MessageQueue:
    """
    Kolejka wiadomości z retry logic.
    """
    
    def __init__(
        self,
        sender: object,
        max_workers: int = 2,
        retry_delay: float = 5.0
    ):
        """
        Args:
            sender: DeltaSender do wysyłania
            max_workers: Liczba workerów
            retry_delay: Opóźnienie retry w sekundach
        """
        self.sender = sender
        self.max_workers = max_workers
        self.retry_delay = retry_delay
        
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._messages: Dict[str, QueuedMessage] = {}
        self._running = False
        self._threads: list = []
        self._lock = threading.Lock()
        self._id_counter = 0
        
        logger.info(f"MessageQueue initialized (workers: {max_workers})")
    
    def _generate_id(self) -> str:
        """Generuje ID wiadomości."""
        with self._lock:
            self._id_counter += 1
            return f"msg_{self._id_counter}_{int(time.time())}"
    
    def enqueue(
        self,
        to: str,
        text: str,
        attachments: Optional[list] = None,
        priority: int = 0
    ) -> str:
        """
        Dodaje wiadomość do kolejki.
        
        Args:
            to: Odbiorca
            text: Treść
            attachments: Załączniki
            priority: Priorytet
            
        Returns:
            ID wiadomości
        """
        msg_id = self._generate_id()
        
        msg = QueuedMessage(
            id=msg_id,
            to=to,
            text=text,
            attachments=attachments or [],
            priority=priority
        )
        
        with self._lock:
            self._messages[msg_id] = msg
            self._queue.put(msg)
        
        logger.debug(f"Enqueued message: {msg_id} to {to}")
        return msg_id
    
    def start(self) -> None:
        """Uruchamia przetwarzanie kolejki."""
        if self._running:
            return
        
        self._running = True
        
        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            self._threads.append(t)
        
        logger.info("MessageQueue started")
    
    def stop(self) -> None:
        """Zatrzymuje przetwarzanie."""
        self._running = False
        for t in self._threads:
            t.join(timeout=5.0)
        self._threads = []
        logger.info("MessageQueue stopped")
    
    def _worker(self) -> None:
        """Worker przetwarzający wiadomości."""
        while self._running:
            try:
                msg = self._queue.get(timeout=1.0)
                self._process_message(msg)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    def _process_message(self, msg: QueuedMessage) -> None:
        """Przetwarza pojedynczą wiadomość."""
        msg.status = MessageStatus.PROCESSING
        msg.attempts += 1
        
        try:
            success = self.sender.send(
                to=msg.to,
                text=msg.text,
                attachments=msg.attachments if msg.attachments else None
            )
            
            if success:
                msg.status = MessageStatus.SENT
                logger.info(f"Message sent: {msg.id}")
            else:
                raise RuntimeError("Send returned False")
                
        except Exception as e:
            msg.error = str(e)
            
            if msg.attempts < msg.max_attempts:
                # Retry
                msg.status = MessageStatus.PENDING
                time.sleep(self.retry_delay)
                self._queue.put(msg)
                logger.warning(f"Retrying message: {msg.id} (attempt {msg.attempts})")
            else:
                msg.status = MessageStatus.FAILED
                logger.error(f"Message failed: {msg.id} - {e}")
    
    def get_status(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """Pobiera status wiadomości."""
        msg = self._messages.get(msg_id)
        if not msg:
            return None
        
        return {
            "id": msg.id,
            "status": msg.status.name,
            "to": msg.to,
            "attempts": msg.attempts,
            "error": msg.error
        }
    
    def cancel(self, msg_id: str) -> bool:
        """Anuluje wiadomość (jeśli jeszcze nie wysłana)."""
        msg = self._messages.get(msg_id)
        if not msg:
            return False
        
        if msg.status == MessageStatus.PENDING:
            msg.status = MessageStatus.FAILED
            msg.error = "Cancelled"
            return True
        
        return False
    
    def clear_completed(self) -> int:
        """Usuwa zakończone wiadomości."""
        with self._lock:
            completed = [
                mid for mid, msg in self._messages.items()
                if msg.status in (MessageStatus.SENT, MessageStatus.FAILED)
            ]
            for mid in completed:
                del self._messages[mid]
            return len(completed)
    
    def status(self) -> Dict[str, Any]:
        """Status kolejki."""
        counts = {status.name: 0 for status in MessageStatus}
        for msg in self._messages.values():
            counts[msg.status.name] += 1
        
        return {
            "running": self._running,
            "workers": len(self._threads),
            "queue_size": self._queue.qsize(),
            "total_messages": len(self._messages),
            "by_status": counts
        }
