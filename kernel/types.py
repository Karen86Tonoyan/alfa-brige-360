"""
ALFA_CORE_KERNEL v3.0 — TYPES
Typy i struktury danych dla kernela.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class ProviderType(Enum):
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    LOCAL = "local"
    OPENAI = "openai"


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class RequestPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Message:
    """Pojedyncza wiadomość w konwersacji."""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Request:
    """Żądanie do kernela."""
    id: str
    prompt: str
    system_prompt: Optional[str] = None
    provider: Optional[str] = None
    priority: RequestPriority = RequestPriority.NORMAL
    context: List[Message] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Response:
    """Odpowiedź z kernela."""
    request_id: str
    text: str
    provider: str
    model: str
    success: bool = True
    error: Optional[str] = None
    latency_ms: float = 0.0
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProviderConfig:
    """Konfiguracja providera."""
    name: str
    enabled: bool = True
    priority: int = 0
    timeout: int = 45
    max_retries: int = 3
    config_file: Optional[str] = None
    key_file: Optional[str] = None


@dataclass
class KernelConfig:
    """Konfiguracja kernela."""
    version: str = "3.0"
    default_provider: str = "gemini"
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    security_enabled: bool = True
    memory_enabled: bool = True
    logging_level: str = "INFO"
