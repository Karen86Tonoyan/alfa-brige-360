"""
ALFA Delta Router v1.0
Integracja Delta Chat z CoreManager i Cerber
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

import yaml

from .delta_listener import DeltaListener, DeltaMessage
from .delta_sender import DeltaSender, VoiceGenerator

if TYPE_CHECKING:
    from alfa_core.kernel import AlfaKernel

logger = logging.getLogger("alfa.delta.router")


@dataclass
class DeltaTask:
    """Zadanie do przetworzenia z Delta Chat."""
    message: DeltaMessage
    priority: int = 5
    voice_enabled: bool = True
    
    
@dataclass 
class DeltaResponse:
    """Odpowiedź do wysłania przez Delta Chat."""
    to: str
    subject: str
    body: str
    voice_path: Optional[Path] = None
    reply_to_id: Optional[str] = None
    

class DeltaRouter:
    """
    Router Delta Chat - łączy Listener, Sender, Kernel i Cerber.
    
    Flow:
    1. Listener odbiera wiadomość
    2. Router sprawdza Cerber (bezpieczeństwo)
    3. Kernel przetwarza (dispatch do odpowiedniego modułu AI)
    4. Voice generuje audio (opcjonalnie)
    5. Sender wysyła odpowiedź
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        kernel: Optional["AlfaKernel"] = None,
    ):
        self.config = self._load_config(config_path)
        self.kernel = kernel
        
        # Komponenty
        self.listener: Optional[DeltaListener] = None
        self.sender: Optional[DeltaSender] = None
        self.voice: Optional[VoiceGenerator] = None
        
        # Queue dla asynchronicznego przetwarzania
        self._task_queue: asyncio.Queue[DeltaTask] = asyncio.Queue()
        self._running = False
        
        # Callbacks
        self._pre_process: Optional[Callable[[DeltaMessage], bool]] = None
        self._post_process: Optional[Callable[[DeltaResponse], None]] = None
        
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Załaduj konfigurację."""
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
            
        path = Path(config_path)
        
        if not path.exists():
            logger.warning(f"[DELTA] Config not found: {path}, using defaults")
            return self._default_config()
            
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
            
        # Rozwiń zmienne środowiskowe
        return self._expand_env(raw.get("delta", {}))
        
    def _expand_env(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Rozwiń ${VAR} w konfiguracji."""
        def expand(value):
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                return os.environ.get(env_var, value)
            elif isinstance(value, dict):
                return {k: expand(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [expand(v) for v in value]
            return value
            
        return expand(config)
        
    def _default_config(self) -> Dict[str, Any]:
        """Domyślna konfiguracja."""
        return {
            "enabled": False,
            "imap": {
                "host": "localhost",
                "port": 993,
                "username": "",
                "password": "",
                "ssl": True,
                "folder": "INBOX",
                "poll_interval": 5,
            },
            "smtp": {
                "host": "localhost",
                "port": 587,
                "username": "",
                "password": "",
                "starttls": True,
            },
            "voice": {
                "enabled": True,
                "format": "ogg",
                "tts_engine": "edge",
            },
            "security": {
                "allowed_senders": [],
                "cerber_filter": True,
                "max_message_size": 10485760,
            },
            "processing": {
                "timeout": 30,
                "retry_count": 3,
                "queue_size": 100,
            },
        }
        
    # --- Initialization ---
    
    def init(self) -> bool:
        """Zainicjalizuj komponenty."""
        if not self.config.get("enabled", False):
            logger.info("[DELTA] Router disabled in config")
            return False
            
        imap_cfg = self.config.get("imap", {})
        smtp_cfg = self.config.get("smtp", {})
        voice_cfg = self.config.get("voice", {})
        security_cfg = self.config.get("security", {})
        
        # Listener
        self.listener = DeltaListener(
            host=imap_cfg.get("host", ""),
            port=imap_cfg.get("port", 993),
            username=imap_cfg.get("username", ""),
            password=imap_cfg.get("password", ""),
            ssl=imap_cfg.get("ssl", True),
            folder=imap_cfg.get("folder", "INBOX"),
            poll_interval=imap_cfg.get("poll_interval", 5),
            allowed_senders=security_cfg.get("allowed_senders", []),
        )
        
        # Sender
        self.sender = DeltaSender(
            host=smtp_cfg.get("host", ""),
            port=smtp_cfg.get("port", 587),
            username=smtp_cfg.get("username", ""),
            password=smtp_cfg.get("password", ""),
            starttls=smtp_cfg.get("starttls", True),
        )
        
        # Voice
        if voice_cfg.get("enabled", False):
            self.voice = VoiceGenerator(
                engine=voice_cfg.get("tts_engine", "edge"),
            )
            
        # Zarejestruj handler
        self.listener.register_handler(self._on_message_received)
        
        logger.info("[DELTA] Router initialized")
        return True
        
    # --- Message Processing ---
    
    def _on_message_received(self, message: DeltaMessage) -> None:
        """Handler dla nowej wiadomości."""
        logger.info(f"[DELTA] Received from {message.sender}: {message.body[:100]}...")
        
        # Pre-process callback (np. Cerber)
        if self._pre_process:
            if not self._pre_process(message):
                logger.warning(f"[DELTA] Message rejected by pre-processor")
                return
                
        # Dodaj do kolejki
        task = DeltaTask(
            message=message,
            voice_enabled=self.config.get("voice", {}).get("enabled", False),
        )
        
        try:
            self._task_queue.put_nowait(task)
        except asyncio.QueueFull:
            logger.error("[DELTA] Task queue full, dropping message")
            
    async def _process_task(self, task: DeltaTask) -> Optional[DeltaResponse]:
        """Przetwórz zadanie i wygeneruj odpowiedź."""
        message = task.message
        
        # === CERBER FILTER ===
        if self.config.get("security", {}).get("cerber_filter", True):
            if self.kernel:
                cerber_result = self.kernel.dispatch(
                    "security.cerber",
                    "filter",
                    source="delta",
                    content=message.body,
                    sender=message.sender,
                )
                if not cerber_result.ok:
                    logger.warning(f"[DELTA] Cerber rejected: {cerber_result.error}")
                    return None
                    
        # === AI PROCESSING ===
        response_text = ""
        
        if self.kernel:
            # Dispatch do AI przez kernel
            result = self.kernel.dispatch(
                "ai.chat",
                "generate",
                prompt=message.body,
                context={
                    "source": "delta",
                    "sender": message.sender,
                    "subject": message.subject,
                },
            )
            
            if result.ok:
                response_text = result.data.get("response", "")
            else:
                response_text = f"[ALFA] Błąd przetwarzania: {result.error}"
        else:
            # Fallback bez kernela
            response_text = f"[ALFA] Otrzymałem: {message.body[:200]}..."
            
        # === VOICE GENERATION ===
        voice_path = None
        
        if task.voice_enabled and self.voice and response_text:
            voice_path = self.voice.generate(response_text)
            if voice_path:
                logger.info(f"[DELTA] Voice generated: {voice_path}")
                
        # === RESPONSE ===
        return DeltaResponse(
            to=message.sender,
            subject=f"Re: {message.subject}",
            body=response_text,
            voice_path=voice_path,
            reply_to_id=message.uid,
        )
        
    async def _send_response(self, response: DeltaResponse) -> bool:
        """Wyślij odpowiedź."""
        if not self.sender:
            return False
            
        # Post-process callback
        if self._post_process:
            self._post_process(response)
            
        if response.voice_path:
            return self.sender.send_with_voice(
                to=response.to,
                subject=response.subject,
                body=response.body,
                voice_path=response.voice_path,
                reply_to_id=response.reply_to_id,
            )
        else:
            return self.sender.send_text(
                to=response.to,
                subject=response.subject,
                body=response.body,
                reply_to_id=response.reply_to_id,
            )
            
    # --- Main Loop ---
    
    async def start(self) -> None:
        """Uruchom router (async)."""
        if not self.listener:
            raise RuntimeError("Router not initialized. Call init() first.")
            
        self._running = True
        logger.info("[DELTA] Router starting...")
        
        # Uruchom listener w tle
        listener_task = asyncio.create_task(self.listener.start_listening())
        
        # Przetwarzaj kolejkę
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0,
                )
                
                response = await self._process_task(task)
                
                if response:
                    await self._send_response(response)
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"[DELTA] Processing error: {e}")
                
        listener_task.cancel()
        
    def stop(self) -> None:
        """Zatrzymaj router."""
        self._running = False
        if self.listener:
            self.listener.stop_listening()
        logger.info("[DELTA] Router stopped")
        
    # --- Sync API ---
    
    def process_one(self) -> Optional[DeltaResponse]:
        """Przetwórz jedną wiadomość (sync)."""
        if not self.listener:
            return None
            
        messages = self.listener.poll_once()
        
        for message in messages:
            self._on_message_received(message)
            
        if not self._task_queue.empty():
            task = self._task_queue.get_nowait()
            return asyncio.run(self._process_task(task))
            
        return None
        
    # --- Callbacks ---
    
    def set_pre_processor(self, callback: Callable[[DeltaMessage], bool]) -> None:
        """Ustaw callback przed przetworzeniem (np. Cerber)."""
        self._pre_process = callback
        
    def set_post_processor(self, callback: Callable[[DeltaResponse], None]) -> None:
        """Ustaw callback po przetworzeniu."""
        self._post_process = callback


# === KERNEL MODULE WRAPPER ===

from alfa_core.kernel_contract import BaseModule, BaseModuleConfig, CommandResult, ModuleHealth


class DeltaModuleConfig(BaseModuleConfig):
    """Konfiguracja modułu Delta."""
    
    def __init__(self, config_path: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.config_path = config_path


class DeltaModule(BaseModule):
    """
    Moduł Delta jako plugin dla ALFA Kernel.
    
    Komendy:
    - start: Uruchom router
    - stop: Zatrzymaj router
    - status: Status routera
    - send: Wyślij wiadomość
    - poll: Jednorazowe odpytanie
    """
    
    id = "comms.delta"
    version = "1.0.0"
    
    def __init__(
        self,
        config: Optional[DeltaModuleConfig] = None,
        kernel_context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(config or DeltaModuleConfig(), kernel_context)
        self.router: Optional[DeltaRouter] = None
        
    def load(self) -> None:
        """Załaduj moduł."""
        kernel = self.kernel
        config_path = getattr(self.config, "config_path", None)
        
        self.router = DeltaRouter(config_path=config_path, kernel=kernel)
        self._loaded = self.router.init()
        
        if self._loaded:
            logger.info("[DELTA] Module loaded")
        else:
            logger.warning("[DELTA] Module loaded but disabled in config")
            
    def unload(self) -> None:
        """Rozładuj moduł."""
        if self.router:
            self.router.stop()
        self._loaded = False
        logger.info("[DELTA] Module unloaded")
        
    def health_check(self) -> ModuleHealth:
        """Sprawdź zdrowie modułu."""
        return ModuleHealth(
            healthy=self._loaded,
            status="running" if self._loaded else "disabled",
            details={
                "listener_connected": bool(self.router and self.router.listener and self.router.listener._connection),
                "queue_size": self.router._task_queue.qsize() if self.router else 0,
            },
        )
        
    def execute(self, command: str, **kwargs) -> CommandResult:
        """Wykonaj komendę."""
        if not self.router:
            return CommandResult.failure("Router not initialized")
            
        # === START ===
        if command == "start":
            # Async start - wymaga event loop
            return CommandResult.success({"message": "Use async start() for full operation"})
            
        # === STOP ===
        if command == "stop":
            self.router.stop()
            return CommandResult.success({"stopped": True})
            
        # === STATUS ===
        if command == "status":
            health = self.health_check()
            return CommandResult.success(health.details)
            
        # === SEND ===
        if command == "send":
            to = kwargs.get("to")
            subject = kwargs.get("subject", "ALFA Message")
            body = kwargs.get("body", "")
            
            if not to or not body:
                return CommandResult.failure("Missing 'to' or 'body'")
                
            if self.router.sender:
                ok = self.router.sender.send_text(to, subject, body)
                return CommandResult.success({"sent": ok})
            return CommandResult.failure("Sender not initialized")
            
        # === POLL ===
        if command == "poll":
            response = self.router.process_one()
            if response:
                return CommandResult.success({
                    "processed": True,
                    "to": response.to,
                    "subject": response.subject,
                })
            return CommandResult.success({"processed": False, "message": "No new messages"})
            
        return CommandResult.failure(f"Unknown command: {command}")
