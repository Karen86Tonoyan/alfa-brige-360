"""
ALFA_CORE_KERNEL v3.0 — CORE MANAGER
Centralny dyspozytor łączący providery, eventy, security i routing.
"""

from typing import Optional, Dict, Any, Callable
import logging
import time
import asyncio
from dataclasses import dataclass

from .types import MessageType, MessagePriority, KernelMessage, ProviderStatus
from .event_bus import EventBus
from .provider_registry import ProviderRegistry

logger = logging.getLogger("ALFA.CoreManager")


@dataclass
class KernelConfig:
    """Konfiguracja kernela."""
    default_provider: str = "gemini"
    enable_security: bool = True
    enable_memory: bool = True
    enable_voice: bool = False
    max_retries: int = 3
    timeout: float = 30.0


class CoreManager:
    """
    Centralny manager ALFA_CORE_KERNEL.
    Koordynuje: Providery, Eventy, Security, Memory, Voice.
    """
    
    def __init__(self, config: Optional[KernelConfig] = None):
        self.config = config or KernelConfig()
        
        # Core components
        self.event_bus = EventBus()
        self.provider_registry = ProviderRegistry(self.event_bus)
        
        # Optional components (lazy load)
        self._security = None
        self._memory = None
        self._voice = None
        self._autoswitch = None
        
        # State
        self._initialized = False
        self._start_time = time.time()
        
        # Event handlers
        self._setup_event_handlers()
        
        logger.info("CoreManager created")
    
    def _setup_event_handlers(self) -> None:
        """Rejestruje handlery eventów."""
        self.event_bus.subscribe("provider:error", self._on_provider_error)
        self.event_bus.subscribe("security:threat", self._on_security_threat)
        self.event_bus.subscribe("kernel:shutdown", self._on_shutdown)
    
    def _on_provider_error(self, data: Dict[str, Any]) -> None:
        """Handler błędu providera."""
        provider_name = data.get("provider", "unknown")
        error = data.get("error", "unknown")
        logger.warning(f"Provider error: {provider_name} - {error}")
        
        # Spróbuj failover
        if self._autoswitch:
            logger.info("Triggering autoswitch failover...")
    
    def _on_security_threat(self, data: Dict[str, Any]) -> None:
        """Handler zagrożenia bezpieczeństwa."""
        threat_type = data.get("type", "unknown")
        severity = data.get("severity", "low")
        logger.warning(f"Security threat: {threat_type} (severity: {severity})")
    
    def _on_shutdown(self, data: Dict[str, Any]) -> None:
        """Handler wyłączenia."""
        logger.info("Kernel shutdown requested")
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        Inicjalizuje kernel.
        """
        try:
            logger.info("Initializing ALFA_CORE_KERNEL...")
            
            # Load security if enabled
            if self.config.enable_security:
                self._load_security()
            
            # Load memory if enabled
            if self.config.enable_memory:
                self._load_memory()
            
            # Load voice if enabled
            if self.config.enable_voice:
                self._load_voice()
            
            # Check providers
            healthy = self.provider_registry.get_healthy()
            logger.info(f"Healthy providers: {healthy}")
            
            self._initialized = True
            self.event_bus.emit("kernel:initialized", {"timestamp": time.time()})
            
            logger.info("ALFA_CORE_KERNEL initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Kernel initialization failed: {e}")
            return False
    
    def _load_security(self) -> None:
        """Ładuje moduł security."""
        try:
            from ..security.cerber import Cerber
            self._security = Cerber()
            logger.info("Security module loaded")
        except ImportError as e:
            logger.warning(f"Security module not available: {e}")
    
    def _load_memory(self) -> None:
        """Ładuje moduł memory."""
        try:
            from ..memory.alpha_memory import AlphaMemory
            self._memory = AlphaMemory()
            logger.info("Memory module loaded")
        except ImportError as e:
            logger.warning(f"Memory module not available: {e}")
    
    def _load_voice(self) -> None:
        """Ładuje moduł voice."""
        try:
            from ..voice.tts import TTS
            self._voice = TTS()
            logger.info("Voice module loaded")
        except ImportError as e:
            logger.warning(f"Voice module not available: {e}")
    
    def dispatch(
        self,
        prompt: str,
        provider_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> str:
        """
        Główna metoda dyspozycji - wysyła prompt do providera.
        
        Args:
            prompt: Tekst promptu
            provider_name: Nazwa providera (lub None dla default/autoswitch)
            system_prompt: System prompt
            priority: Priorytet wiadomości
            
        Returns:
            Odpowiedź od providera
        """
        if not self._initialized:
            logger.warning("Kernel not initialized, auto-initializing...")
            self.initialize()
        
        # Security check
        if self._security:
            is_safe, reason = self._security.validate(prompt)
            if not is_safe:
                self.event_bus.emit("security:blocked", {
                    "reason": reason,
                    "prompt_preview": prompt[:50]
                })
                return f"[BLOCKED] Security check failed: {reason}"
        
        # Store in memory
        if self._memory:
            self._memory.add("user", prompt)
        
        # Get provider
        if provider_name:
            provider = self.provider_registry.get(provider_name)
        elif self._autoswitch:
            # Use autoswitch
            response = self._autoswitch.generate(prompt, system_prompt)
            if self._memory:
                self._memory.add("assistant", response)
            return response
        else:
            # Use primary provider
            provider = self.provider_registry.get_primary()
        
        if not provider:
            return "[ERROR] No provider available"
        
        # Generate response
        try:
            if system_prompt:
                response = provider.generate(prompt, system_prompt)
            else:
                response = provider.generate(prompt)
            
            # Store response
            if self._memory:
                self._memory.add("assistant", response)
            
            # Emit success event
            self.event_bus.emit("dispatch:success", {
                "provider": getattr(provider, 'name', 'unknown'),
                "prompt_len": len(prompt),
                "response_len": len(response)
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Dispatch failed: {e}")
            self.event_bus.emit("dispatch:error", {"error": str(e)})
            return f"[ERROR] {str(e)}"
    
    async def dispatch_async(
        self,
        prompt: str,
        provider_name: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """Asynchroniczna wersja dispatch."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.dispatch(prompt, provider_name, system_prompt)
        )
    
    def register_provider(
        self,
        name: str,
        provider: object,
        priority: int = 0,
        is_fallback: bool = False
    ) -> None:
        """Rejestruje providera."""
        self.provider_registry.register(name, provider, priority, is_fallback)
    
    def setup_autoswitch(self, providers: list) -> None:
        """Konfiguruje autoswitch z listą providerów."""
        from ..providers.autoswitch import AutoSwitch
        self._autoswitch = AutoSwitch(providers)
        logger.info(f"AutoSwitch configured with {len(providers)} providers")
    
    def status(self) -> Dict[str, Any]:
        """Zwraca status kernela."""
        uptime = time.time() - self._start_time
        return {
            "initialized": self._initialized,
            "uptime_seconds": round(uptime, 2),
            "config": {
                "default_provider": self.config.default_provider,
                "security_enabled": self.config.enable_security,
                "memory_enabled": self.config.enable_memory,
                "voice_enabled": self.config.enable_voice
            },
            "components": {
                "security": self._security is not None,
                "memory": self._memory is not None,
                "voice": self._voice is not None,
                "autoswitch": self._autoswitch is not None
            },
            "providers": self.provider_registry.status(),
            "event_bus": self.event_bus.status()
        }
    
    def shutdown(self) -> None:
        """Zamyka kernel."""
        logger.info("Shutting down ALFA_CORE_KERNEL...")
        self.event_bus.emit("kernel:shutdown", {"timestamp": time.time()})
        self._initialized = False
        logger.info("Kernel shutdown complete")


# Singleton instance
_kernel: Optional[CoreManager] = None


def get_kernel(config: Optional[KernelConfig] = None) -> CoreManager:
    """Zwraca singleton kernela."""
    global _kernel
    if _kernel is None:
        _kernel = CoreManager(config)
    return _kernel
