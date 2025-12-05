# ═══════════════════════════════════════════════════════════════════════════
# ALFA_BRAIN v2.0 — CORE ENGINE
# ═══════════════════════════════════════════════════════════════════════════
"""
AlfaEngine: Centralny silnik systemu ALFA.

Odpowiedzialności:
- Boot systemu
- Lifecycle management
- Plugin orchestration
- Event routing
- Heartbeat monitoring

Usage:
    from core.engine import AlfaEngine, get_engine
    
    engine = get_engine()
    engine.boot()
    engine.run()
"""

import os
import sys
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

ALFA_ROOT = Path(__file__).parent.parent
CONFIG_FILE = ALFA_ROOT / "config" / "system.json"

LOG = logging.getLogger("alfa.engine")

class EngineState(Enum):
    INIT = "init"
    BOOTING = "booting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM CONFIG
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SystemConfig:
    """System configuration loaded from system.json"""
    version: str = "2.0.0"
    codename: str = "CERBER_EDITION"
    mode: str = "development"
    
    # Paths
    plugins_dir: str = "plugins"
    config_dir: str = "config"
    logs_dir: str = "logs"
    
    # Engine
    heartbeat_interval: int = 30
    max_plugins: int = 50
    auto_start_plugins: bool = True
    
    # Cerber
    cerber_enabled: bool = True
    verify_on_boot: bool = True
    
    # API
    api_enabled: bool = True
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    
    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "SystemConfig":
        """Load config from JSON file"""
        config = cls()
        
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                config.version = data.get("version", config.version)
                config.codename = data.get("codename", config.codename)
                config.mode = data.get("mode", config.mode)
                
                paths = data.get("paths", {})
                config.plugins_dir = paths.get("plugins", config.plugins_dir)
                config.config_dir = paths.get("config", config.config_dir)
                config.logs_dir = paths.get("logs", config.logs_dir)
                
                engine = data.get("engine", {})
                config.heartbeat_interval = engine.get("heartbeat_interval", config.heartbeat_interval)
                config.max_plugins = engine.get("max_plugins", config.max_plugins)
                config.auto_start_plugins = engine.get("auto_start_plugins", config.auto_start_plugins)
                
                cerber = data.get("cerber", {})
                config.cerber_enabled = cerber.get("enabled", config.cerber_enabled)
                config.verify_on_boot = cerber.get("verify_on_boot", config.verify_on_boot)
                
                api = data.get("api", {})
                config.api_enabled = api.get("enabled", config.api_enabled)
                config.api_host = api.get("host", config.api_host)
                config.api_port = api.get("port", config.api_port)
                
            except Exception as e:
                LOG.error(f"Failed to load config: {e}")
        
        return config

# ═══════════════════════════════════════════════════════════════════════════
# ALFA ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class AlfaEngine:
    """
    Centralny silnik ALFA System.
    
    Singleton pattern - jeden silnik na cały system.
    """
    
    _instance: Optional["AlfaEngine"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "AlfaEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.state = EngineState.INIT
        self.config = SystemConfig.load()
        self.start_time: Optional[datetime] = None
        
        # Components (lazy loaded)
        self._event_bus = None
        self._cerber = None
        self._plugin_engine = None
        
        # Heartbeat
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Hooks
        self._on_boot: List[Callable] = []
        self._on_shutdown: List[Callable] = []
        
        self._initialized = True
        LOG.info(f"[Engine] Initialized v{self.config.version} ({self.config.codename})")
    
    # ─────────────────────────────────────────────────────────────────────
    # COMPONENTS (lazy loading)
    # ─────────────────────────────────────────────────────────────────────
    
    @property
    def event_bus(self):
        """Get EventBus instance"""
        if self._event_bus is None:
            from .event_bus import EventBus
            self._event_bus = EventBus()
        return self._event_bus
    
    @property
    def cerber(self):
        """Get Cerber instance"""
        if self._cerber is None:
            from .cerber import Cerber
            self._cerber = Cerber(str(ALFA_ROOT))
        return self._cerber
    
    @property
    def plugin_engine(self):
        """Get PluginEngine instance"""
        if self._plugin_engine is None:
            from .plugin_engine import PluginEngine
            self._plugin_engine = PluginEngine(self)
        return self._plugin_engine
    
    # ─────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────
    
    def boot(self) -> bool:
        """
        Boot the system.
        
        Sequence:
        1. Verify integrity (Cerber)
        2. Start EventBus
        3. Load plugins
        4. Start heartbeat
        5. Run boot hooks
        """
        if self.state not in (EngineState.INIT, EngineState.STOPPED):
            LOG.warning(f"Cannot boot from state: {self.state}")
            return False
        
        self.state = EngineState.BOOTING
        self.start_time = datetime.now()
        LOG.info("[Engine] Booting...")
        
        try:
            # 1. Cerber integrity check
            if self.config.cerber_enabled and self.config.verify_on_boot:
                LOG.info("[Engine] Running Cerber integrity check...")
                self.cerber.scan_directory(str(ALFA_ROOT))
                results = self.cerber.verify_all()
                failed = [p for p, ok in results.items() if not ok]
                if failed:
                    LOG.warning(f"[Engine] Cerber: {len(failed)} files failed integrity")
            
            # 2. Start EventBus
            LOG.info("[Engine] Starting EventBus...")
            self.event_bus.start()
            
            # 3. Load plugins
            if self.config.auto_start_plugins:
                LOG.info("[Engine] Loading plugins...")
                self.plugin_engine.discover()
                self.plugin_engine.load_all()
                self.plugin_engine.start_all()
            
            # 4. Start heartbeat
            self._start_heartbeat()
            
            # 5. Run boot hooks
            for hook in self._on_boot:
                try:
                    hook(self)
                except Exception as e:
                    LOG.error(f"Boot hook error: {e}")
            
            # Emit boot event
            self.event_bus.publish("system.boot", {
                "version": self.config.version,
                "timestamp": self.start_time.isoformat()
            })
            
            self.state = EngineState.RUNNING
            LOG.info(f"[Engine] Boot complete. State: {self.state.value}")
            return True
            
        except Exception as e:
            LOG.error(f"[Engine] Boot failed: {e}")
            self.state = EngineState.ERROR
            return False
    
    def shutdown(self):
        """Graceful shutdown"""
        if self.state != EngineState.RUNNING:
            return
        
        self.state = EngineState.STOPPING
        LOG.info("[Engine] Shutting down...")
        
        # Emit shutdown event
        self.event_bus.publish("system.shutdown", priority=0)
        
        # Run shutdown hooks
        for hook in self._on_shutdown:
            try:
                hook(self)
            except Exception as e:
                LOG.error(f"Shutdown hook error: {e}")
        
        # Stop heartbeat
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5.0)
        
        # Stop plugins
        self.plugin_engine.stop_all()
        
        # Stop Cerber
        if self._cerber:
            self._cerber.stop()
        
        # Stop EventBus
        self.event_bus.stop()
        
        self.state = EngineState.STOPPED
        LOG.info("[Engine] Shutdown complete")
    
    # ─────────────────────────────────────────────────────────────────────
    # HEARTBEAT
    # ─────────────────────────────────────────────────────────────────────
    
    def _start_heartbeat(self):
        """Start heartbeat monitoring thread"""
        self._running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="Engine-Heartbeat"
        )
        self._heartbeat_thread.start()
    
    def _heartbeat_loop(self):
        """Heartbeat monitoring loop"""
        interval = self.config.heartbeat_interval
        
        while self._running:
            try:
                # Emit heartbeat
                self.event_bus.publish("system.heartbeat", {
                    "uptime": self.uptime_seconds(),
                    "state": self.state.value,
                    "plugins": len(self.plugin_engine.plugins)
                })
                
                # Health checks
                self._run_health_checks()
                
            except Exception as e:
                LOG.error(f"Heartbeat error: {e}")
            
            # Sleep with interrupt check
            for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _run_health_checks(self):
        """Run periodic health checks"""
        # EventBus stats
        stats = self.event_bus.stats()
        if stats.get("dlq_size", 0) > 100:
            LOG.warning(f"Dead letter queue growing: {stats['dlq_size']}")
        
        # Plugin health
        for name, info in self.plugin_engine.plugins.items():
            if info.status.value == "error":
                LOG.warning(f"Plugin in error state: {name}")
    
    # ─────────────────────────────────────────────────────────────────────
    # HOOKS
    # ─────────────────────────────────────────────────────────────────────
    
    def on_boot(self, callback: Callable):
        """Register boot hook"""
        self._on_boot.append(callback)
    
    def on_shutdown(self, callback: Callable):
        """Register shutdown hook"""
        self._on_shutdown.append(callback)
    
    # ─────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────
    
    def uptime_seconds(self) -> float:
        """Get system uptime in seconds"""
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0.0
    
    def status(self) -> Dict[str, Any]:
        """Get engine status"""
        return {
            "version": self.config.version,
            "codename": self.config.codename,
            "state": self.state.value,
            "mode": self.config.mode,
            "uptime_seconds": self.uptime_seconds(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "plugins_count": len(self.plugin_engine.plugins),
            "eventbus_stats": self.event_bus.stats(),
            "cerber_running": self._cerber is not None and self._cerber._running
        }
    
    def run_tests(self) -> Dict[str, bool]:
        """Run system tests"""
        results = {}
        
        # Test EventBus
        try:
            stats = self.event_bus.stats()
            results["eventbus"] = stats is not None
        except:
            results["eventbus"] = False
        
        # Test Cerber
        try:
            status = self.cerber.status()
            results["cerber"] = status is not None
        except:
            results["cerber"] = False
        
        # Test PluginEngine
        try:
            plugins = self.plugin_engine.list_plugins()
            results["plugin_engine"] = plugins is not None
        except:
            results["plugin_engine"] = False
        
        return results

# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════════════════

def get_engine() -> AlfaEngine:
    """Get AlfaEngine singleton"""
    return AlfaEngine()

# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    engine = get_engine()
    
    print(f"\n{'='*60}")
    print(f"ALFA Engine v{engine.config.version} ({engine.config.codename})")
    print(f"{'='*60}\n")
    
    if engine.boot():
        print("Engine booted successfully!")
        print(f"Status: {engine.status()}")
        
        try:
            print("\nPress Ctrl+C to shutdown...")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            engine.shutdown()
    else:
        print("Boot failed!")
