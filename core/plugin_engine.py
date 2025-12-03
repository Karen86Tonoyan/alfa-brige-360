#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# ALFA CORE v2.0 — PLUGIN ENGINE — Dynamic Plugin System
# ═══════════════════════════════════════════════════════════════════════════
"""
PLUGIN ENGINE: System dynamicznego ładowania i zarządzania pluginami.

Features:
- Manifest-based plugin registration
- Hot-reload support
- Hook system (before/after/error)
- Dependency resolution
- Sandboxed execution
- EventBus integration

Plugin Lifecycle:
1. Discovery (scan directories)
2. Manifest validation
3. Dependency check
4. Loading (import module)
5. Initialization (call setup())
6. Registration (hooks, commands)
7. Active (respond to events)
8. Shutdown (call cleanup())

Author: ALFA System / Karen86Tonoyan
"""

import asyncio
import importlib
import importlib.util
import inspect
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# EventBus integration
try:
    from .event_bus import EventBus, Priority, get_bus, publish
except ImportError:
    EventBus = None
    Priority = None
    get_bus = lambda: None
    publish = lambda *a, **k: None

# SecureExecutor integration
try:
    from .secure_executor import SecureExecutor, SecurityLevel
except ImportError:
    SecureExecutor = None
    SecurityLevel = None

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LOG = logging.getLogger("alfa.plugins")

# Paths
ALFA_ROOT = Path(__file__).parent.parent
PLUGINS_PATH = ALFA_ROOT / "plugins"
EXTENSIONS_PATH = ALFA_ROOT / "extensions"

# Manifest
MANIFEST_FILE = "plugin.json"
LEGACY_MANIFEST = "__manifest__.py"

# Timeouts
LOAD_TIMEOUT = 30
HOOK_TIMEOUT = 10


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS & DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

class PluginState(Enum):
    """Stan pluginu"""
    DISCOVERED = "discovered"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"
    UNLOADED = "unloaded"


class HookType(Enum):
    """Typy hooków"""
    # Lifecycle
    BEFORE_LOAD = "before_load"
    AFTER_LOAD = "after_load"
    BEFORE_UNLOAD = "before_unload"
    AFTER_UNLOAD = "after_unload"
    
    # Execution
    BEFORE_EXECUTE = "before_execute"
    AFTER_EXECUTE = "after_execute"
    ON_ERROR = "on_error"
    
    # Events
    ON_MESSAGE = "on_message"
    ON_COMMAND = "on_command"
    ON_EVENT = "on_event"
    
    # System
    ON_STARTUP = "on_startup"
    ON_SHUTDOWN = "on_shutdown"
    ON_CONFIG_CHANGE = "on_config_change"


@dataclass
class PluginManifest:
    """Manifest pluginu"""
    name: str
    version: str
    description: str = ""
    author: str = ""
    license: str = "MIT"
    
    # Entry point
    main: str = "__init__"  # Module to import
    
    # Requirements
    dependencies: List[str] = field(default_factory=list)
    python_requires: str = ">=3.10"
    pip_packages: List[str] = field(default_factory=list)
    
    # Capabilities
    commands: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    
    # Config
    config_schema: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)
    
    # Security
    permissions: List[str] = field(default_factory=list)
    sandbox_level: str = "standard"  # minimal, standard, extended
    
    # Metadata
    homepage: str = ""
    repository: str = ""
    tags: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PluginManifest":
        return cls(
            name=data.get("name", "unknown"),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            license=data.get("license", "MIT"),
            main=data.get("main", "__init__"),
            dependencies=data.get("dependencies", []),
            python_requires=data.get("python_requires", ">=3.10"),
            pip_packages=data.get("pip_packages", []),
            commands=data.get("commands", []),
            hooks=data.get("hooks", []),
            provides=data.get("provides", []),
            config_schema=data.get("config_schema", {}),
            default_config=data.get("default_config", {}),
            permissions=data.get("permissions", []),
            sandbox_level=data.get("sandbox_level", "standard"),
            homepage=data.get("homepage", ""),
            repository=data.get("repository", ""),
            tags=data.get("tags", [])
        )
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "main": self.main,
            "dependencies": self.dependencies,
            "python_requires": self.python_requires,
            "pip_packages": self.pip_packages,
            "commands": self.commands,
            "hooks": self.hooks,
            "provides": self.provides,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "permissions": self.permissions,
            "sandbox_level": self.sandbox_level,
            "homepage": self.homepage,
            "repository": self.repository,
            "tags": self.tags
        }


@dataclass
class PluginInfo:
    """Pełne informacje o załadowanym pluginie"""
    manifest: PluginManifest
    path: Path
    state: PluginState = PluginState.DISCOVERED
    module: Any = None
    instance: Any = None
    config: Dict[str, Any] = field(default_factory=dict)
    loaded_at: Optional[float] = None
    error: Optional[str] = None
    
    @property
    def name(self) -> str:
        return self.manifest.name
    
    @property
    def version(self) -> str:
        return self.manifest.version


@dataclass
class HookRegistration:
    """Rejestracja hooka"""
    hook_type: HookType
    plugin_name: str
    callback: Callable
    priority: int = 50  # 0=first, 100=last
    async_handler: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# PLUGIN ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class PluginEngine:
    """
    Silnik zarządzania pluginami ALFA System.
    
    Usage:
        engine = PluginEngine()
        engine.discover()
        engine.load_all()
        
        # Execute command
        result = await engine.execute_command("my_plugin.my_command", args)
        
        # Trigger hook
        await engine.trigger_hook(HookType.ON_MESSAGE, {"text": "Hello"})
    """
    
    def __init__(
        self,
        plugins_paths: List[Path] = None,
        auto_discover: bool = True
    ):
        # Paths
        self.plugins_paths = plugins_paths or [PLUGINS_PATH, EXTENSIONS_PATH]
        for p in self.plugins_paths:
            p.mkdir(parents=True, exist_ok=True)
        
        # Registry
        self.plugins: Dict[str, PluginInfo] = {}
        self.hooks: Dict[HookType, List[HookRegistration]] = {t: [] for t in HookType}
        self.commands: Dict[str, Tuple[str, Callable]] = {}  # cmd -> (plugin, callback)
        
        # Dependency graph
        self._dependencies: Dict[str, Set[str]] = {}
        self._dependents: Dict[str, Set[str]] = {}
        
        # State
        self._lock = threading.RLock()
        self._initialized = False
        
        # Sandbox
        self._executor = None
        if SecureExecutor:
            self._executor = SecureExecutor(level=SecurityLevel.STANDARD)
        
        if auto_discover:
            self.discover()
        
        LOG.info(f"[PluginEngine] Initialized with {len(self.plugins_paths)} paths")
    
    # ─────────────────────────────────────────────────────────────────────
    # DISCOVERY
    # ─────────────────────────────────────────────────────────────────────
    
    def discover(self) -> List[str]:
        """Discover plugins in configured paths"""
        discovered = []
        
        for base_path in self.plugins_paths:
            if not base_path.exists():
                continue
            
            for item in base_path.iterdir():
                if item.is_dir() and not item.name.startswith(('_', '.')):
                    manifest = self._load_manifest(item)
                    if manifest:
                        plugin_info = PluginInfo(
                            manifest=manifest,
                            path=item,
                            state=PluginState.DISCOVERED,
                            config=manifest.default_config.copy()
                        )
                        
                        with self._lock:
                            self.plugins[manifest.name] = plugin_info
                        
                        discovered.append(manifest.name)
                        LOG.debug(f"[Discover] Found: {manifest.name} v{manifest.version}")
        
        LOG.info(f"[PluginEngine] Discovered {len(discovered)} plugins")
        return discovered
    
    def _load_manifest(self, plugin_path: Path) -> Optional[PluginManifest]:
        """Load plugin manifest from directory"""
        # Try JSON manifest
        json_manifest = plugin_path / MANIFEST_FILE
        if json_manifest.exists():
            try:
                with open(json_manifest, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return PluginManifest.from_dict(data)
            except Exception as e:
                LOG.error(f"[Manifest] Error loading {json_manifest}: {e}")
                return None
        
        # Try legacy Python manifest
        py_manifest = plugin_path / LEGACY_MANIFEST
        if py_manifest.exists():
            try:
                spec = importlib.util.spec_from_file_location("_manifest", py_manifest)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    
                    return PluginManifest(
                        name=getattr(mod, 'NAME', plugin_path.name),
                        version=getattr(mod, 'VERSION', '0.0.0'),
                        description=getattr(mod, 'DESCRIPTION', ''),
                        author=getattr(mod, 'AUTHOR', ''),
                        commands=getattr(mod, 'COMMANDS', []),
                        hooks=getattr(mod, 'HOOKS', []),
                        dependencies=getattr(mod, 'DEPENDENCIES', [])
                    )
            except Exception as e:
                LOG.error(f"[Manifest] Error loading {py_manifest}: {e}")
                return None
        
        # Try to infer from __init__.py
        init_file = plugin_path / "__init__.py"
        if init_file.exists():
            return PluginManifest(
                name=plugin_path.name,
                version="0.0.0",
                description=f"Auto-discovered plugin: {plugin_path.name}",
                main="__init__"
            )
        
        return None
    
    # ─────────────────────────────────────────────────────────────────────
    # LOADING
    # ─────────────────────────────────────────────────────────────────────
    
    def load(self, name: str) -> bool:
        """Load a specific plugin"""
        with self._lock:
            if name not in self.plugins:
                LOG.error(f"[Load] Plugin not found: {name}")
                return False
            
            plugin = self.plugins[name]
            
            if plugin.state == PluginState.ACTIVE:
                LOG.debug(f"[Load] Already active: {name}")
                return True
        
        # Check dependencies
        if not self._check_dependencies(name):
            plugin.state = PluginState.ERROR
            plugin.error = "Missing dependencies"
            return False
        
        # Trigger before_load hooks
        asyncio.get_event_loop().run_until_complete(
            self.trigger_hook(HookType.BEFORE_LOAD, {"plugin": name})
        )
        
        plugin.state = PluginState.LOADING
        
        try:
            # Add to path
            if str(plugin.path.parent) not in sys.path:
                sys.path.insert(0, str(plugin.path.parent))
            
            # Import module
            module_name = plugin.manifest.main
            if module_name == "__init__":
                module_name = plugin.path.name
            
            spec = importlib.util.spec_from_file_location(
                module_name,
                plugin.path / f"{plugin.manifest.main}.py" if plugin.manifest.main != "__init__" 
                else plugin.path / "__init__.py"
            )
            
            if not spec or not spec.loader:
                raise ImportError(f"Cannot load spec for {name}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"plugins.{name}"] = module
            spec.loader.exec_module(module)
            
            plugin.module = module
            
            # Create instance if class-based
            if hasattr(module, 'Plugin'):
                plugin.instance = module.Plugin(plugin.config)
            elif hasattr(module, 'setup'):
                # Function-based plugin
                module.setup(plugin.config)
            
            # Register commands
            self._register_commands(plugin)
            
            # Register hooks
            self._register_hooks(plugin)
            
            plugin.state = PluginState.ACTIVE
            plugin.loaded_at = time.time()
            
            LOG.info(f"[Load] Loaded: {name} v{plugin.version}")
            
            # Trigger after_load hooks
            asyncio.get_event_loop().run_until_complete(
                self.trigger_hook(HookType.AFTER_LOAD, {"plugin": name})
            )
            
            # Publish event
            if get_bus():
                publish("plugin.loaded", {"name": name, "version": plugin.version})
            
            return True
            
        except Exception as e:
            plugin.state = PluginState.ERROR
            plugin.error = str(e)
            LOG.error(f"[Load] Failed: {name} - {e}")
            
            # Trigger error hook
            asyncio.get_event_loop().run_until_complete(
                self.trigger_hook(HookType.ON_ERROR, {"plugin": name, "error": str(e)})
            )
            
            return False
    
    def load_all(self, ignore_errors: bool = True) -> Dict[str, bool]:
        """Load all discovered plugins"""
        results = {}
        
        # Sort by dependencies
        load_order = self._resolve_load_order()
        
        for name in load_order:
            try:
                results[name] = self.load(name)
            except Exception as e:
                results[name] = False
                if not ignore_errors:
                    raise
        
        return results
    
    def _check_dependencies(self, name: str) -> bool:
        """Check if all dependencies are available"""
        plugin = self.plugins.get(name)
        if not plugin:
            return False
        
        for dep in plugin.manifest.dependencies:
            if dep not in self.plugins:
                LOG.warning(f"[Deps] Missing dependency: {dep} for {name}")
                return False
            
            dep_plugin = self.plugins[dep]
            if dep_plugin.state not in {PluginState.ACTIVE, PluginState.LOADED}:
                # Try to load dependency first
                if not self.load(dep):
                    return False
        
        return True
    
    def _resolve_load_order(self) -> List[str]:
        """Resolve plugin load order based on dependencies"""
        # Build dependency graph
        graph: Dict[str, Set[str]] = {}
        for name, plugin in self.plugins.items():
            graph[name] = set(plugin.manifest.dependencies)
        
        # Topological sort
        order = []
        visited = set()
        temp_visited = set()
        
        def visit(name: str):
            if name in temp_visited:
                raise ValueError(f"Circular dependency detected: {name}")
            if name in visited:
                return
            
            temp_visited.add(name)
            for dep in graph.get(name, set()):
                if dep in graph:  # Only visit known plugins
                    visit(dep)
            temp_visited.remove(name)
            visited.add(name)
            order.append(name)
        
        for name in graph:
            if name not in visited:
                visit(name)
        
        return order
    
    def _register_commands(self, plugin: PluginInfo):
        """Register plugin commands"""
        module = plugin.module
        
        # From manifest
        for cmd in plugin.manifest.commands:
            if hasattr(module, cmd):
                callback = getattr(module, cmd)
                full_cmd = f"{plugin.name}.{cmd}"
                self.commands[full_cmd] = (plugin.name, callback)
                LOG.debug(f"[Register] Command: {full_cmd}")
        
        # Auto-discover @command decorated
        for name, obj in inspect.getmembers(module):
            if hasattr(obj, '_alfa_command'):
                full_cmd = f"{plugin.name}.{name}"
                self.commands[full_cmd] = (plugin.name, obj)
    
    def _register_hooks(self, plugin: PluginInfo):
        """Register plugin hooks"""
        module = plugin.module
        instance = plugin.instance
        
        # Check module and instance for hook methods
        targets = [module]
        if instance:
            targets.append(instance)
        
        for target in targets:
            for hook_type in HookType:
                method_name = f"on_{hook_type.name.lower()}"
                alt_name = hook_type.name.lower()
                
                callback = getattr(target, method_name, None) or getattr(target, alt_name, None)
                
                if callback and callable(callback):
                    is_async = asyncio.iscoroutinefunction(callback)
                    
                    reg = HookRegistration(
                        hook_type=hook_type,
                        plugin_name=plugin.name,
                        callback=callback,
                        async_handler=is_async
                    )
                    
                    self.hooks[hook_type].append(reg)
                    LOG.debug(f"[Register] Hook: {plugin.name}.{hook_type.name}")
    
    # ─────────────────────────────────────────────────────────────────────
    # UNLOADING
    # ─────────────────────────────────────────────────────────────────────
    
    def unload(self, name: str) -> bool:
        """Unload a plugin"""
        with self._lock:
            if name not in self.plugins:
                return False
            
            plugin = self.plugins[name]
            
            if plugin.state not in {PluginState.ACTIVE, PluginState.LOADED}:
                return True
        
        # Trigger before_unload
        asyncio.get_event_loop().run_until_complete(
            self.trigger_hook(HookType.BEFORE_UNLOAD, {"plugin": name})
        )
        
        try:
            # Call cleanup
            if plugin.instance and hasattr(plugin.instance, 'cleanup'):
                plugin.instance.cleanup()
            elif plugin.module and hasattr(plugin.module, 'cleanup'):
                plugin.module.cleanup()
            
            # Remove commands
            to_remove = [cmd for cmd, (pname, _) in self.commands.items() if pname == name]
            for cmd in to_remove:
                del self.commands[cmd]
            
            # Remove hooks
            for hook_type in HookType:
                self.hooks[hook_type] = [
                    h for h in self.hooks[hook_type]
                    if h.plugin_name != name
                ]
            
            # Clear module reference
            mod_name = f"plugins.{name}"
            if mod_name in sys.modules:
                del sys.modules[mod_name]
            
            plugin.state = PluginState.UNLOADED
            plugin.module = None
            plugin.instance = None
            
            LOG.info(f"[Unload] Unloaded: {name}")
            
            # Trigger after_unload
            asyncio.get_event_loop().run_until_complete(
                self.trigger_hook(HookType.AFTER_UNLOAD, {"plugin": name})
            )
            
            # Publish event
            if get_bus():
                publish("plugin.unloaded", {"name": name})
            
            return True
            
        except Exception as e:
            LOG.error(f"[Unload] Failed: {name} - {e}")
            plugin.error = str(e)
            return False
    
    def reload(self, name: str) -> bool:
        """Hot-reload a plugin"""
        self.unload(name)
        
        # Re-discover manifest
        if name in self.plugins:
            plugin = self.plugins[name]
            manifest = self._load_manifest(plugin.path)
            if manifest:
                plugin.manifest = manifest
        
        return self.load(name)
    
    # ─────────────────────────────────────────────────────────────────────
    # EXECUTION
    # ─────────────────────────────────────────────────────────────────────
    
    async def execute_command(
        self,
        command: str,
        args: Dict[str, Any] = None,
        context: Dict[str, Any] = None
    ) -> Any:
        """Execute a plugin command"""
        if command not in self.commands:
            raise ValueError(f"Unknown command: {command}")
        
        plugin_name, callback = self.commands[command]
        plugin = self.plugins.get(plugin_name)
        
        if not plugin or plugin.state != PluginState.ACTIVE:
            raise RuntimeError(f"Plugin not active: {plugin_name}")
        
        # Trigger before_execute
        await self.trigger_hook(HookType.BEFORE_EXECUTE, {
            "command": command,
            "args": args,
            "context": context
        })
        
        try:
            # Execute
            if asyncio.iscoroutinefunction(callback):
                result = await callback(**(args or {}))
            else:
                result = callback(**(args or {}))
            
            # Trigger after_execute
            await self.trigger_hook(HookType.AFTER_EXECUTE, {
                "command": command,
                "result": result
            })
            
            return result
            
        except Exception as e:
            # Trigger on_error
            await self.trigger_hook(HookType.ON_ERROR, {
                "command": command,
                "error": str(e)
            })
            raise
    
    async def trigger_hook(
        self,
        hook_type: HookType,
        data: Dict[str, Any] = None
    ) -> List[Any]:
        """Trigger all registered hooks of a type"""
        results = []
        handlers = sorted(self.hooks.get(hook_type, []), key=lambda h: h.priority)
        
        for handler in handlers:
            try:
                if handler.async_handler:
                    result = await asyncio.wait_for(
                        handler.callback(data or {}),
                        timeout=HOOK_TIMEOUT
                    )
                else:
                    result = handler.callback(data or {})
                
                results.append(result)
                
            except asyncio.TimeoutError:
                LOG.warning(f"[Hook] Timeout: {handler.plugin_name}.{hook_type.name}")
            except Exception as e:
                LOG.error(f"[Hook] Error: {handler.plugin_name}.{hook_type.name} - {e}")
        
        return results
    
    # ─────────────────────────────────────────────────────────────────────
    # QUERY
    # ─────────────────────────────────────────────────────────────────────
    
    def list_plugins(self, state: PluginState = None) -> List[str]:
        """List plugins, optionally filtered by state"""
        with self._lock:
            if state:
                return [name for name, p in self.plugins.items() if p.state == state]
            return list(self.plugins.keys())
    
    def get_plugin(self, name: str) -> Optional[PluginInfo]:
        """Get plugin info"""
        return self.plugins.get(name)
    
    def list_commands(self, plugin: str = None) -> List[str]:
        """List available commands"""
        if plugin:
            return [cmd for cmd, (pname, _) in self.commands.items() if pname == plugin]
        return list(self.commands.keys())
    
    def get_status(self) -> Dict[str, Any]:
        """Get engine status"""
        with self._lock:
            return {
                "plugins_count": len(self.plugins),
                "active_count": sum(1 for p in self.plugins.values() if p.state == PluginState.ACTIVE),
                "commands_count": len(self.commands),
                "hooks_count": sum(len(h) for h in self.hooks.values()),
                "plugins": {
                    name: {
                        "version": p.version,
                        "state": p.state.value,
                        "error": p.error
                    }
                    for name, p in self.plugins.items()
                }
            }


# ═══════════════════════════════════════════════════════════════════════════
# DECORATORS
# ═══════════════════════════════════════════════════════════════════════════

def command(name: str = None):
    """Decorator to mark a function as a plugin command"""
    def decorator(func):
        func._alfa_command = name or func.__name__
        return func
    return decorator


def hook(hook_type: HookType, priority: int = 50):
    """Decorator to register a hook handler"""
    def decorator(func):
        func._alfa_hook = (hook_type, priority)
        return func
    return decorator


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

_engine: Optional[PluginEngine] = None


def get_plugin_engine() -> PluginEngine:
    """Get or create PluginEngine singleton"""
    global _engine
    if _engine is None:
        _engine = PluginEngine()
    return _engine


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ALFA Plugin Engine")
    parser.add_argument("action", choices=["list", "load", "unload", "reload", "status"])
    parser.add_argument("--plugin", "-p", help="Plugin name")
    parser.add_argument("--all", "-a", action="store_true", help="All plugins")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    engine = PluginEngine()
    
    if args.action == "list":
        print("Discovered plugins:")
        for name, plugin in engine.plugins.items():
            print(f"  {name} v{plugin.version} [{plugin.state.value}]")
    
    elif args.action == "load":
        if args.all:
            results = engine.load_all()
            for name, success in results.items():
                print(f"  {name}: {'✓' if success else '✗'}")
        elif args.plugin:
            success = engine.load(args.plugin)
            print(f"{args.plugin}: {'✓' if success else '✗'}")
    
    elif args.action == "unload":
        if args.plugin:
            success = engine.unload(args.plugin)
            print(f"{args.plugin}: {'✓' if success else '✗'}")
    
    elif args.action == "reload":
        if args.plugin:
            success = engine.reload(args.plugin)
            print(f"{args.plugin}: {'✓' if success else '✗'}")
    
    elif args.action == "status":
        status = engine.get_status()
        print(f"Plugins: {status['plugins_count']} ({status['active_count']} active)")
        print(f"Commands: {status['commands_count']}")
        print(f"Hooks: {status['hooks_count']}")
