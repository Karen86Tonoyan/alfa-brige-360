# ═══════════════════════════════════════════════════════════════════════════
# ALFA_BRAIN v2.0 — PLUGIN ENGINE
# ═══════════════════════════════════════════════════════════════════════════
"""
Dynamic plugin loading and lifecycle management.

Usage:
    from core.plugin_engine import PluginEngine
    
    engine = PluginEngine(alfa_engine)
    engine.discover()
    engine.load_all()
    engine.start_all()
"""

import importlib
import json
import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import AlfaEngine

LOG = logging.getLogger("alfa.plugins")

ALFA_ROOT = Path(__file__).parent.parent
PLUGINS_DIR = ALFA_ROOT / "plugins"
PLUGINS_CONFIG = ALFA_ROOT / "config" / "plugins.json"

# ═══════════════════════════════════════════════════════════════════════════
# ENUMS & DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════

class PluginStatus(Enum):
    DISCOVERED = "discovered"
    LOADED = "loaded"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"
    DISABLED = "disabled"

@dataclass
class PluginManifest:
    name: str
    version: str = "1.0.0"
    description: str = ""
    enabled: bool = True
    auto_start: bool = True
    priority: int = 50
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PluginInfo:
    manifest: PluginManifest
    path: Path
    status: PluginStatus = PluginStatus.DISCOVERED
    instance: Optional["Plugin"] = None
    error: Optional[str] = None

# ═══════════════════════════════════════════════════════════════════════════
# PLUGIN BASE
# ═══════════════════════════════════════════════════════════════════════════

class Plugin(ABC):
    """Base class for all plugins."""
    
    def __init__(self, manifest: PluginManifest, engine: "AlfaEngine"):
        self.manifest = manifest
        self.engine = engine
        self.name = manifest.name
        self.version = manifest.version
        self.logger = logging.getLogger(f"alfa.plugin.{self.name}")
    
    @abstractmethod
    def on_load(self) -> bool:
        """Called when plugin is loaded."""
        pass
    
    @abstractmethod
    def on_start(self) -> bool:
        """Called when plugin is started."""
        pass
    
    @abstractmethod
    def on_stop(self):
        """Called when plugin is stopped."""
        pass
    
    def on_unload(self):
        """Called when plugin is unloaded."""
        pass
    
    def on_command(self, command: str, args: str) -> Optional[str]:
        """Handle CLI command."""
        return None
    
    def emit(self, topic: str, payload: Any = None):
        """Emit event via EventBus."""
        self.engine.event_bus.publish(f"plugin.{self.name}.{topic}", payload, source=self.name)
    
    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to EventBus topic."""
        self.engine.event_bus.subscribe(topic, callback, subscriber_id=f"plugin:{self.name}")
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get plugin config setting."""
        return self.manifest.config.get(key, default)

# ═══════════════════════════════════════════════════════════════════════════
# PLUGIN ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class PluginEngine:
    """Plugin discovery, loading, and lifecycle management."""
    
    def __init__(self, engine: "AlfaEngine"):
        self.engine = engine
        self.plugins: Dict[str, PluginInfo] = {}
        self._plugin_configs: Dict[str, Dict] = {}
        self._load_config()
    
    def _load_config(self):
        """Load plugins.json configuration."""
        if PLUGINS_CONFIG.exists():
            try:
                with open(PLUGINS_CONFIG, "r") as f:
                    data = json.load(f)
                for p in data.get("plugins", []):
                    self._plugin_configs[p["name"]] = p
            except Exception as e:
                LOG.error(f"Failed to load plugins.json: {e}")
    
    def discover(self) -> List[str]:
        """Discover plugins in plugins directory."""
        discovered = []
        
        if not PLUGINS_DIR.exists():
            LOG.warning(f"Plugins directory not found: {PLUGINS_DIR}")
            return discovered
        
        for item in PLUGINS_DIR.iterdir():
            if not item.is_dir() or item.name.startswith(("_", ".")):
                continue
            
            init_file = item / "__init__.py"
            if not init_file.exists():
                continue
            
            # Get config from plugins.json
            config = self._plugin_configs.get(item.name, {})
            
            manifest = PluginManifest(
                name=item.name,
                version=config.get("version", "1.0.0"),
                description=config.get("description", ""),
                enabled=config.get("enabled", True),
                auto_start=config.get("auto_start", True),
                priority=config.get("priority", 50),
                dependencies=config.get("dependencies", []),
                config=config.get("config", {})
            )
            
            info = PluginInfo(manifest=manifest, path=item)
            self.plugins[manifest.name] = info
            discovered.append(manifest.name)
            LOG.info(f"Discovered: {manifest.name}")
        
        return discovered
    
    def load(self, name: str) -> Optional[PluginInfo]:
        """Load a single plugin."""
        if name not in self.plugins:
            LOG.error(f"Plugin not found: {name}")
            return None
        
        info = self.plugins[name]
        
        if not info.manifest.enabled:
            info.status = PluginStatus.DISABLED
            return info
        
        try:
            # Add to path
            plugin_path = str(info.path)
            if plugin_path not in sys.path:
                sys.path.insert(0, str(PLUGINS_DIR))
            
            # Import module
            module = importlib.import_module(info.path.name)
            
            # Find Plugin subclass
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                    plugin_class = attr
                    break
            
            if not plugin_class:
                raise ValueError(f"No Plugin subclass in {name}")
            
            # Instantiate
            instance = plugin_class(info.manifest, self.engine)
            
            if not instance.on_load():
                raise ValueError("on_load() returned False")
            
            info.instance = instance
            info.status = PluginStatus.LOADED
            LOG.info(f"Loaded: {name}")
            
            self.engine.event_bus.publish("plugin.loaded", {"name": name})
            return info
            
        except Exception as e:
            info.status = PluginStatus.ERROR
            info.error = str(e)
            LOG.error(f"Load error [{name}]: {e}")
            return info
    
    def load_all(self) -> Dict[str, bool]:
        """Load all discovered plugins."""
        # Sort by priority
        sorted_names = sorted(
            self.plugins.keys(),
            key=lambda n: self.plugins[n].manifest.priority
        )
        
        return {name: self.load(name) is not None and self.plugins[name].status == PluginStatus.LOADED
                for name in sorted_names}
    
    def start(self, name: str) -> bool:
        """Start a loaded plugin."""
        if name not in self.plugins:
            return False
        
        info = self.plugins[name]
        if info.status != PluginStatus.LOADED or not info.instance:
            return False
        
        try:
            if info.instance.on_start():
                info.status = PluginStatus.STARTED
                LOG.info(f"Started: {name}")
                self.engine.event_bus.publish("plugin.started", {"name": name})
                return True
        except Exception as e:
            info.status = PluginStatus.ERROR
            info.error = str(e)
            LOG.error(f"Start error [{name}]: {e}")
        
        return False
    
    def stop(self, name: str) -> bool:
        """Stop a running plugin."""
        if name not in self.plugins:
            return False
        
        info = self.plugins[name]
        if info.status != PluginStatus.STARTED or not info.instance:
            return False
        
        try:
            info.instance.on_stop()
            info.status = PluginStatus.STOPPED
            LOG.info(f"Stopped: {name}")
            self.engine.event_bus.publish("plugin.stopped", {"name": name})
            return True
        except Exception as e:
            LOG.error(f"Stop error [{name}]: {e}")
            return False
    
    def start_all(self) -> Dict[str, bool]:
        """Start all loaded plugins (auto_start only)."""
        results = {}
        for name, info in self.plugins.items():
            if info.status == PluginStatus.LOADED and info.manifest.auto_start:
                results[name] = self.start(name)
        return results
    
    def stop_all(self):
        """Stop all running plugins."""
        for name, info in self.plugins.items():
            if info.status == PluginStatus.STARTED:
                self.stop(name)
    
    def unload(self, name: str) -> bool:
        """Unload a plugin."""
        if name not in self.plugins:
            return False
        
        info = self.plugins[name]
        
        if info.status == PluginStatus.STARTED:
            self.stop(name)
        
        if info.instance:
            try:
                info.instance.on_unload()
            except:
                pass
        
        info.instance = None
        info.status = PluginStatus.DISCOVERED
        LOG.info(f"Unloaded: {name}")
        return True
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get plugin instance."""
        info = self.plugins.get(name)
        return info.instance if info else None
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all plugins with status."""
        return [
            {
                "name": info.manifest.name,
                "version": info.manifest.version,
                "status": info.status.value,
                "enabled": info.manifest.enabled,
                "error": info.error
            }
            for info in self.plugins.values()
        ]
    
    def dispatch_command(self, command: str, args: str = "") -> Optional[str]:
        """Dispatch command to plugins."""
        for info in self.plugins.values():
            if info.status == PluginStatus.STARTED and info.instance:
                result = info.instance.on_command(command, args)
                if result is not None:
                    return result
        return None

__all__ = ["PluginEngine", "Plugin", "PluginManifest", "PluginInfo", "PluginStatus"]
