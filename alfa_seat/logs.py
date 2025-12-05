"""
ALFA_SEAT — WebSocket LogBus
Real-time log streaming to connected clients.
"""

import asyncio
import logging
from datetime import datetime
from typing import Set, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("ALFA.Seat.Logs")


@dataclass
class LogEntry:
    """Single log entry."""
    timestamp: str
    level: str
    source: str
    message: str
    
    def to_json(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "source": self.source,
            "message": self.message
        }
    
    def __str__(self) -> str:
        return f"[{self.timestamp}] [{self.level}] [{self.source}] {self.message}"


class LogBus:
    """
    WebSocket-based log broadcasting system.
    
    Usage:
        await LOG_BUS.publish("Pipeline started", source="executor")
        await LOG_BUS.info("Model loaded", source="registry")
        await LOG_BUS.error("Connection failed", source="adapter")
    """
    
    def __init__(self):
        self.connections: Set = set()
        self._buffer: list = []
        self._buffer_size: int = 100
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket) -> None:
        """Add new WebSocket connection."""
        self.connections.add(websocket)
        logger.info(f"LogBus: Client connected. Total: {len(self.connections)}")
        
        # Send buffered logs to new client
        for entry in self._buffer[-20:]:
            try:
                await websocket.send_json(entry.to_json())
            except:
                pass
    
    async def disconnect(self, websocket) -> None:
        """Remove WebSocket connection."""
        self.connections.discard(websocket)
        logger.info(f"LogBus: Client disconnected. Total: {len(self.connections)}")
    
    async def publish(
        self, 
        message: str, 
        level: str = "INFO",
        source: str = "system"
    ) -> None:
        """Publish log message to all connected clients."""
        entry = LogEntry(
            timestamp=datetime.now().strftime("%H:%M:%S.%f")[:-3],
            level=level,
            source=source,
            message=message
        )
        
        # Buffer
        async with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) > self._buffer_size:
                self._buffer = self._buffer[-self._buffer_size:]
        
        # Broadcast
        dead_connections = set()
        for ws in self.connections:
            try:
                await ws.send_json(entry.to_json())
            except Exception:
                dead_connections.add(ws)
        
        # Cleanup dead connections
        self.connections -= dead_connections
        
        # Also log locally
        logger.log(
            getattr(logging, level, logging.INFO),
            f"[{source}] {message}"
        )
    
    async def info(self, message: str, source: str = "system") -> None:
        await self.publish(message, "INFO", source)
    
    async def warning(self, message: str, source: str = "system") -> None:
        await self.publish(message, "WARNING", source)
    
    async def error(self, message: str, source: str = "system") -> None:
        await self.publish(message, "ERROR", source)
    
    async def debug(self, message: str, source: str = "system") -> None:
        await self.publish(message, "DEBUG", source)
    
    async def pipeline(self, stage: str, status: str, details: str = "") -> None:
        """Log pipeline stage execution."""
        msg = f"[{stage}] {status}"
        if details:
            msg += f" — {details}"
        await self.publish(msg, "INFO", "pipeline")


# Global singleton
LOG_BUS = LogBus()
