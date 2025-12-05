"""
ALFA_CORE_KERNEL v3.0 — DISPATCHER
Dispatcher zarządza kolejką zadań i ich wykonaniem.
"""

from typing import Optional, Dict, Any, Callable, List
import logging
import asyncio
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("ALFA.Dispatcher")


class TaskStatus(Enum):
    """Status zadania."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class Task:
    """Zadanie do wykonania."""
    id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: int = 0
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def __lt__(self, other):
        """Porównanie dla priority queue (wyższy priorytet = pierwszy)."""
        return self.priority > other.priority


class Dispatcher:
    """
    Dispatcher zarządza wykonaniem zadań asynchronicznie.
    """
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._tasks: Dict[str, Task] = {}
        self._executor: Optional[ThreadPoolExecutor] = None
        self._running = False
        self._lock = threading.Lock()
        self._task_counter = 0
        
        logger.info(f"Dispatcher created (max_workers: {max_workers})")
    
    def _generate_task_id(self) -> str:
        """Generuje unikalny ID zadania."""
        with self._lock:
            self._task_counter += 1
            return f"task_{self._task_counter}_{int(time.time())}"
    
    def submit(
        self,
        func: Callable,
        *args,
        priority: int = 0,
        task_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Dodaje zadanie do kolejki.
        
        Args:
            func: Funkcja do wykonania
            *args: Argumenty pozycyjne
            priority: Priorytet (wyższy = wykonany szybciej)
            task_id: Opcjonalny ID zadania
            **kwargs: Argumenty nazwane
            
        Returns:
            ID zadania
        """
        task_id = task_id or self._generate_task_id()
        
        task = Task(
            id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority
        )
        
        with self._lock:
            self._tasks[task_id] = task
            self._queue.put(task)
        
        logger.debug(f"Task submitted: {task_id} (priority: {priority})")
        
        # Auto-start jeśli nie działa
        if self._running and self._executor:
            self._process_next()
        
        return task_id
    
    def start(self) -> None:
        """Uruchamia dispatcher."""
        if self._running:
            logger.warning("Dispatcher already running")
            return
        
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._running = True
        
        # Rozpocznij przetwarzanie
        threading.Thread(target=self._worker_loop, daemon=True).start()
        
        logger.info("Dispatcher started")
    
    def stop(self) -> None:
        """Zatrzymuje dispatcher."""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        logger.info("Dispatcher stopped")
    
    def _worker_loop(self) -> None:
        """Główna pętla przetwarzania."""
        while self._running:
            try:
                # Pobierz zadanie z timeout
                try:
                    task = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                self._execute_task(task)
                
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
    
    def _process_next(self) -> None:
        """Przetwarza następne zadanie z kolejki."""
        if not self._executor or self._queue.empty():
            return
        
        try:
            task = self._queue.get_nowait()
            self._executor.submit(self._execute_task, task)
        except queue.Empty:
            pass
    
    def _execute_task(self, task: Task) -> None:
        """Wykonuje pojedyncze zadanie."""
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        
        try:
            logger.debug(f"Executing task: {task.id}")
            result = task.func(*task.args, **task.kwargs)
            task.result = result
            task.status = TaskStatus.COMPLETED
            logger.debug(f"Task completed: {task.id}")
            
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            logger.error(f"Task failed: {task.id} - {e}")
        
        finally:
            task.completed_at = time.time()
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Zwraca zadanie po ID."""
        return self._tasks.get(task_id)
    
    def get_result(self, task_id: str, timeout: float = 30.0) -> Any:
        """
        Czeka na wynik zadania.
        
        Args:
            task_id: ID zadania
            timeout: Maksymalny czas oczekiwania
            
        Returns:
            Wynik zadania lub None
        """
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        start = time.time()
        while task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            if time.time() - start > timeout:
                logger.warning(f"Task timeout: {task_id}")
                return None
            time.sleep(0.1)
        
        if task.status == TaskStatus.COMPLETED:
            return task.result
        elif task.status == TaskStatus.FAILED:
            raise RuntimeError(task.error)
        
        return None
    
    def cancel(self, task_id: str) -> bool:
        """Anuluje zadanie."""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            logger.info(f"Task cancelled: {task_id}")
            return True
        
        return False
    
    def clear_completed(self) -> int:
        """Usuwa zakończone zadania."""
        with self._lock:
            completed = [
                tid for tid, task in self._tasks.items()
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            for tid in completed:
                del self._tasks[tid]
            
            logger.info(f"Cleared {len(completed)} completed tasks")
            return len(completed)
    
    def status(self) -> Dict[str, Any]:
        """Status dispatchera."""
        task_counts = {status.name: 0 for status in TaskStatus}
        for task in self._tasks.values():
            task_counts[task.status.name] += 1
        
        return {
            "running": self._running,
            "max_workers": self.max_workers,
            "queue_size": self._queue.qsize(),
            "total_tasks": len(self._tasks),
            "task_counts": task_counts
        }


# Async support
class AsyncDispatcher:
    """Asynchroniczna wersja Dispatcher."""
    
    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tasks: Dict[str, asyncio.Task] = {}
        self._task_counter = 0
    
    def _generate_task_id(self) -> str:
        self._task_counter += 1
        return f"async_task_{self._task_counter}"
    
    async def submit(
        self,
        coro,
        task_id: Optional[str] = None
    ) -> str:
        """Dodaje coroutine do wykonania."""
        task_id = task_id or self._generate_task_id()
        
        async def wrapped():
            async with self._semaphore:
                return await coro
        
        self._tasks[task_id] = asyncio.create_task(wrapped())
        return task_id
    
    async def get_result(self, task_id: str) -> Any:
        """Czeka na wynik."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        return await task
    
    def status(self) -> Dict[str, Any]:
        return {
            "max_concurrent": self.max_concurrent,
            "active_tasks": len([t for t in self._tasks.values() if not t.done()]),
            "total_tasks": len(self._tasks)
        }
