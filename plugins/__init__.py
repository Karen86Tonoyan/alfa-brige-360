# ═══════════════════════════════════════════════════════════════════════════
# ALFA CORE v2.0 — PLUGINS — Plugin Base & Loader
# ═══════════════════════════════════════════════════════════════════════════
"""
System pluginów ALFA.

Każdy plugin ma:
- manifest.yaml z metadanymi
- __init__.py z klasą Plugin
- Integrację z EventBus

Lifecycle:
    1. discover() - znajdź pluginy w plugins/
    2. load() - załaduj i zainicjalizuj
    3. start() - uruchom (hook: plugin.started)
    4. stop() - zatrzymaj (hook: plugin.stopped)
    5. unload() - wyładuj

Usage:
    from plugins import PluginLoader, Plugin
    
    loader = PluginLoader()
    loader.discover()
    loader.load_all()
"""

import os
import sys
import logging
import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

try:
    import yaml
except ImportError:
    yaml = None

# Import EventBus
try:
    from core import get_bus, publish, subscribe, Priority
except ImportError:
    get_bus = lambda: None
    publish = lambda *a, **k: None
    subscribe = lambda *a, **k: None
    Priority = None

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LOG = logging.getLogger("alfa.plugins")

PLUGINS_DIR = Path(__file__).parent
MANIFEST_FILE = "manifest.yaml"

# ═══════════════════════════════════════════════════════════════════════════
# ENUMS & DATA CLASSES
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
    """Plugin manifest from manifest.yaml"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    layer: str = ""  # MCP layer assignment
    dependencies: List[str] = field(default_factory=list)
    python_deps: List[str] = field(default_factory=list)
    events: Dict[str, str] = field(default_factory=dict)  # event -> handler method
    commands: List[str] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

@dataclass
class PluginInfo:
    """Runtime plugin information"""
    manifest: PluginManifest
    path: Path
    status: PluginStatus = PluginStatus.DISCOVERED
    instance: Optional["Plugin"] = None
    error: Optional[str] = None

# ═══════════════════════════════════════════════════════════════════════════
# PLUGIN BASE CLASS
# ═══════════════════════════════════════════════════════════════════════════

class Plugin(ABC):
    """
    Abstract base class for all ALFA plugins.
    
    Każdy plugin musi:
    - Dziedziczyć z Plugin
    - Implementować on_load(), on_start(), on_stop()
    - Opcjonalnie: on_command(), on_event()
    """
    
    def __init__(self, manifest: PluginManifest, path: Path):
        self.manifest = manifest
        self.path = path
        self.name = manifest.name
        self.version = manifest.version
        self.logger = logging.getLogger(f"alfa.plugin.{self.name}")
        self._subscriptions: List[str] = []
    
    # ─────────────────────────────────────────────────────────────────────
    # LIFECYCLE (implement in subclass)
    # ─────────────────────────────────────────────────────────────────────
    
    @abstractmethod
    def on_load(self) -> bool:
        """Called when plugin is loaded. Return True if successful."""
        pass
    
    @abstractmethod
    def on_start(self) -> bool:
        """Called when plugin is started. Return True if successful."""
        pass
    
    @abstractmethod
    def on_stop(self):
        """Called when plugin is stopped."""
        pass
    
    def on_unload(self):
        """Called when plugin is unloaded. Override if needed."""
        self._unsubscribe_all()
    
    # ─────────────────────────────────────────────────────────────────────
    # EVENT HANDLING
    # ─────────────────────────────────────────────────────────────────────
    
    def subscribe_event(self, topic: str, handler: Callable):
        """Subscribe to an event topic"""
        sub_id = subscribe(topic, handler, subscriber_id=f"plugin:{self.name}")
        self._subscriptions.append((topic, sub_id))
        self.logger.debug(f"Subscribed to {topic}")
    
    def emit_event(self, topic: str, payload: Any = None, priority: int = 50):
        """Emit an event"""
        full_topic = f"plugin.{self.name}.{topic}"
        publish(full_topic, payload, source=self.name, priority=priority)
    
    def _unsubscribe_all(self):
        """Unsubscribe from all events"""
        bus = get_bus()
        if bus:
            bus.unsubscribe_all(f"plugin:{self.name}")
        self._subscriptions.clear()
    
    # ─────────────────────────────────────────────────────────────────────
    # COMMANDS
    # ─────────────────────────────────────────────────────────────────────
    
    def on_command(self, command: str, args: str) -> Optional[str]:
        """Handle a command. Override in subclass."""
        return None
    
    def get_commands(self) -> List[str]:
        """Get available commands"""
        return self.manifest.commands
    
    # ─────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get plugin setting"""
        return self.manifest.settings.get(key, default)
    
    def get_data_path(self) -> Path:
        """Get plugin data directory"""
        data_dir = self.path / "data"
        data_dir.mkdir(exist_ok=True)
        return data_dir
    
    def __repr__(self):
        return f"<Plugin {self.name} v{self.version}>"

# ═══════════════════════════════════════════════════════════════════════════
# PLUGIN LOADER
# ═══════════════════════════════════════════════════════════════════════════

class PluginLoader:
    """
    Plugin discovery and lifecycle management.
    """
    
    def __init__(self, plugins_dir: Path = PLUGINS_DIR):
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, PluginInfo] = {}
    
    # ─────────────────────────────────────────────────────────────────────
    # DISCOVERY
    # ─────────────────────────────────────────────────────────────────────
    
    def discover(self) -> List[str]:
        """Discover plugins in plugins directory"""
        discovered = []
        
        if not self.plugins_dir.exists():
            LOG.warning(f"Plugins directory not found: {self.plugins_dir}")
            return discovered
        
        for item in self.plugins_dir.iterdir():
            if not item.is_dir():
                continue
            
            # Skip __pycache__, hidden dirs
            if item.name.startswith(("_", ".")):
                continue
            
            manifest_path = item / MANIFEST_FILE
            if not manifest_path.exists():
                LOG.debug(f"No manifest in {item.name}, skipping")
                continue
            
            try:
                manifest = self._load_manifest(manifest_path)
                if manifest:
                    info = PluginInfo(manifest=manifest, path=item)
                    self.plugins[manifest.name] = info
                    discovered.append(manifest.name)
                    LOG.info(f"Discovered plugin: {manifest.name} v{manifest.version}")
            except Exception as e:
                LOG.error(f"Error loading manifest for {item.name}: {e}")
        
        return discovered
    
    def _load_manifest(self, path: Path) -> Optional[PluginManifest]:
        """Load and parse manifest.yaml"""
        if not yaml:
            LOG.error("PyYAML not installed, cannot load manifests")
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not data or not isinstance(data, dict):
            return None
        
        return PluginManifest(
            name=data.get("name", path.parent.name),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            layer=data.get("layer", ""),
            dependencies=data.get("dependencies", []),
            python_deps=data.get("python_deps", []),
            events=data.get("events", {}),
            commands=data.get("commands", []),
            settings=data.get("settings", {}),
            enabled=data.get("enabled", True)
        )
    
    # ─────────────────────────────────────────────────────────────────────
    # LOADING
    # ─────────────────────────────────────────────────────────────────────
    
    def load(self, name: str) -> Optional[PluginInfo]:
        """Load a single plugin"""
        if name not in self.plugins:
            LOG.error(f"Plugin not found: {name}")
            return None
        
        info = self.plugins[name]
        
        if not info.manifest.enabled:
            info.status = PluginStatus.DISABLED
            LOG.info(f"Plugin disabled: {name}")
            return info
        
        # Check dependencies
        for dep in info.manifest.dependencies:
            if dep not in self.plugins:
                info.status = PluginStatus.ERROR
                info.error = f"Missing dependency: {dep}"
                LOG.error(info.error)
                return info
        
        try:
            # Add plugin path to sys.path
            plugin_path = str(info.path)
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
            
            # Import plugin module
            module_name = info.path.name
            module = importlib.import_module(module_name)
            
            # Find Plugin subclass
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, Plugin) and 
                    attr is not Plugin):
                    plugin_class = attr
                    break
            
            if not plugin_class:
                raise ValueError(f"No Plugin subclass found in {module_name}")
            
            # Instantiate
            instance = plugin_class(info.manifest, info.path)
            
            # Call on_load
            if not instance.on_load():
                raise ValueError("on_load() returned False")
            
            info.instance = instance
            info.status = PluginStatus.LOADED
            
            LOG.info(f"Loaded plugin: {name}")
            publish("plugin.loaded", {"name": name, "version": info.manifest.version})
            
            return info
            
        except Exception as e:
            info.status = PluginStatus.ERROR
            info.error = str(e)
            LOG.error(f"Error loading plugin {name}: {e}")
            return info
    
    def load_all(self) -> Dict[str, bool]:
        """Load all discovered plugins"""
        results = {}
        
        # Sort by dependencies
        sorted_plugins = self._sort_by_dependencies()
        
        for name in sorted_plugins:
            info = self.load(name)
            results[name] = info is not None and info.status == PluginStatus.LOADED
        
        return results
    
    def _sort_by_dependencies(self) -> List[str]:
        """Topological sort by dependencies"""
        # Simple implementation - load plugins with no deps first
        no_deps = []
        with_deps = []
        
        for name, info in self.plugins.items():
            if not info.manifest.dependencies:
                no_deps.append(name)
            else:
                with_deps.append(name)
        
        return no_deps + with_deps
    
    # ─────────────────────────────────────────────────────────────────────
    # START / STOP
    # ─────────────────────────────────────────────────────────────────────
    
    def start(self, name: str) -> bool:
        """Start a loaded plugin"""
        if name not in self.plugins:
            return False
        
        info = self.plugins[name]
        
        if info.status != PluginStatus.LOADED:
            LOG.warning(f"Cannot start {name}: not loaded (status: {info.status})")
            return False
        
        if not info.instance:
            return False
        
        try:
            if info.instance.on_start():
                info.status = PluginStatus.STARTED
                LOG.info(f"Started plugin: {name}")
                publish("plugin.started", {"name": name})
                return True
            else:
                LOG.error(f"on_start() returned False for {name}")
                return False
        except Exception as e:
            info.status = PluginStatus.ERROR
            info.error = str(e)
            LOG.error(f"Error starting {name}: {e}")
            return False
    
    def stop(self, name: str) -> bool:
        """Stop a running plugin"""
        if name not in self.plugins:
            return False
        
        info = self.plugins[name]
        
        if info.status != PluginStatus.STARTED:
            return False
        
        if not info.instance:
            return False
        
        try:
            info.instance.on_stop()
            info.status = PluginStatus.STOPPED
            LOG.info(f"Stopped plugin: {name}")
            publish("plugin.stopped", {"name": name})
            return True
        except Exception as e:
            LOG.error(f"Error stopping {name}: {e}")
            return False
    
    def start_all(self) -> Dict[str, bool]:
        """Start all loaded plugins"""
        results = {}
        for name, info in self.plugins.items():
            if info.status == PluginStatus.LOADED:
                results[name] = self.start(name)
        return results
    
    def stop_all(self):
        """Stop all running plugins"""
        for name, info in self.plugins.items():
            if info.status == PluginStatus.STARTED:
                self.stop(name)
    
    # ─────────────────────────────────────────────────────────────────────
    # UNLOADING
    # ─────────────────────────────────────────────────────────────────────
    
    def unload(self, name: str) -> bool:
        """Unload a plugin"""
        if name not in self.plugins:
            return False
        
        info = self.plugins[name]
        
        # Stop if running
        if info.status == PluginStatus.STARTED:
            self.stop(name)
        
        if info.instance:
            try:
                info.instance.on_unload()
            except Exception as e:
                LOG.error(f"Error in on_unload for {name}: {e}")
        
        info.instance = None
        info.status = PluginStatus.DISCOVERED
        
        LOG.info(f"Unloaded plugin: {name}")
        publish("plugin.unloaded", {"name": name})
        
        return True
    
    # ─────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get plugin instance"""
        if name in self.plugins and self.plugins[name].instance:
            return self.plugins[name].instance
        return None
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all plugins with status"""
        return [
            {
                "name": info.manifest.name,
                "version": info.manifest.version,
                "status": info.status.value,
                "layer": info.manifest.layer,
                "error": info.error
            }
            for info in self.plugins.values()
        ]
    
    def dispatch_command(self, command: str, args: str = "") -> Optional[str]:
        """Dispatch command to appropriate plugin"""
        for info in self.plugins.values():
            if info.status == PluginStatus.STARTED and info.instance:
                if command in info.manifest.commands:
                    return info.instance.on_command(command, args)
        return None

# ═══════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "Plugin",
    "PluginLoader",
    "PluginInfo",
    "PluginManifest",
    "PluginStatus"
]
