#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# ALFA CORE v2.0 — EXTENSIONS LOADER — Legacy Module Compatibility
# ═══════════════════════════════════════════════════════════════════════════
"""
EXTENSIONS LOADER: Ładowanie rozszerzeń z extensions_config.json.

Features:
- Config validation (JSON Schema)
- Module auto-discovery
- Hot-reload support
- Layer organization
- Backwards compatibility with ALFA_BRAIN

Layers (from extensions_config.json):
- modules: coding, chat, vision, audio, video, security, web
- layers: creative, knowledge, automation, dev

Author: ALFA System / Karen86Tonoyan
"""

import asyncio
import importlib
import importlib.util
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# Watchdog for hot-reload (optional)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    HAS_WATCHDOG = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    FileModifiedEvent = None
    HAS_WATCHDOG = False

# EventBus integration
try:
    from .event_bus import get_bus, publish, Priority
except ImportError:
    get_bus = lambda: None
    publish = lambda *a, **k: None
    Priority = None

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

LOG = logging.getLogger("alfa.extensions")


ALFA_ROOT = Path(__file__).parent.parent
EXTENSIONS_PATH = ALFA_ROOT / "extensions"
CONFIG_FILE = ALFA_ROOT / "extensions_config.json"

# Config schema for validation
CONFIG_SCHEMA = {
    "type": "object",
    "required": ["version", "modules"],
    "properties": {
        "version": {"type": "string"},
        "description": {"type": "string"},
        "modules": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "config": {"type": "object"}
                }
            }
        },
        "layers": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "modules": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    }
}


# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ExtensionConfig:
    """Configuration for a single extension"""
    name: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    layer: Optional[str] = None


@dataclass
class ExtensionInfo:
    """Runtime information about loaded extension"""
    name: str
    path: Path
    config: ExtensionConfig
    module: Any = None
    instance: Any = None
    loaded: bool = False
    loaded_at: Optional[float] = None
    error: Optional[str] = None
    commands: List[str] = field(default_factory=list)
    
    @property
    def is_active(self) -> bool:
        return self.loaded and self.config.enabled


@dataclass
class LayerInfo:
    """Information about extension layer"""
    name: str
    enabled: bool = True
    modules: List[str] = field(default_factory=list)
    description: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

class ConfigValidator:
    """Validate extensions_config.json"""
    
    @staticmethod
    def validate(config: Dict) -> tuple[bool, List[str]]:
        """
        Validate config against schema.
        Returns (is_valid, errors)
        """
        errors = []
        
        # Check required fields
        if "version" not in config:
            errors.append("Missing required field: version")
        
        if "modules" not in config:
            errors.append("Missing required field: modules")
        elif not isinstance(config["modules"], dict):
            errors.append("'modules' must be an object")
        
        # Validate modules
        for name, mod_config in config.get("modules", {}).items():
            if not isinstance(mod_config, dict):
                errors.append(f"Module '{name}' config must be an object")
                continue
            
            if "enabled" in mod_config and not isinstance(mod_config["enabled"], bool):
                errors.append(f"Module '{name}' enabled must be boolean")
            
            if "config" in mod_config and not isinstance(mod_config["config"], dict):
                errors.append(f"Module '{name}' config must be an object")
        
        # Validate layers
        for name, layer_config in config.get("layers", {}).items():
            if not isinstance(layer_config, dict):
                errors.append(f"Layer '{name}' config must be an object")
                continue
            
            if "modules" in layer_config:
                if not isinstance(layer_config["modules"], list):
                    errors.append(f"Layer '{name}' modules must be an array")
                else:
                    # Check if referenced modules exist
                    for mod in layer_config["modules"]:
                        if mod not in config.get("modules", {}):
                            errors.append(f"Layer '{name}' references unknown module: {mod}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_file(path: Path) -> tuple[bool, List[str], Optional[Dict]]:
        """
        Validate config file.
        Returns (is_valid, errors, config)
        """
        if not path.exists():
            return False, [f"Config file not found: {path}"], None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {e}"], None
        except Exception as e:
            return False, [f"Error reading config: {e}"], None
        
        is_valid, errors = ConfigValidator.validate(config)
        return is_valid, errors, config


# ═══════════════════════════════════════════════════════════════════════════
# FILE WATCHER (Hot-Reload)
# ═══════════════════════════════════════════════════════════════════════════

class ExtensionFileHandler(FileSystemEventHandler):
    """Watch for extension file changes"""
    
    def __init__(self, loader: 'ExtensionsLoader'):
        self.loader = loader
        self._debounce: Dict[str, float] = {}
        self._debounce_delay = 1.0  # seconds
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        
        # Check debounce
        now = time.time()
        if path.name in self._debounce:
            if now - self._debounce[path.name] < self._debounce_delay:
                return
        self._debounce[path.name] = now
        
        # Config file changed
        if path.name == "extensions_config.json":
            LOG.info("[HotReload] Config changed, reloading...")
            self.loader.reload_config()
        
        # Python file in extension changed
        elif path.suffix == ".py":
            # Find which extension this belongs to
            rel = path.relative_to(EXTENSIONS_PATH)
            ext_name = rel.parts[0] if len(rel.parts) > 0 else None
            
            if ext_name and ext_name in self.loader.extensions:
                LOG.info(f"[HotReload] Extension modified: {ext_name}")
                asyncio.run(self.loader.reload_extension(ext_name))


# ═══════════════════════════════════════════════════════════════════════════
# EXTENSIONS LOADER
# ═══════════════════════════════════════════════════════════════════════════

class ExtensionsLoader:
    """
    Load and manage extensions from extensions_config.json.
    
    Usage:
        loader = ExtensionsLoader()
        loader.load_all()
        
        # Get extension
        coding = loader.get("coding")
        
        # Hot-reload
        loader.enable_hot_reload()
    """
    
    def __init__(
        self,
        config_path: Path = None,
        extensions_path: Path = None,
        auto_load: bool = False
    ):
        self.config_path = config_path or CONFIG_FILE
        self.extensions_path = extensions_path or EXTENSIONS_PATH
        self.extensions_path.mkdir(parents=True, exist_ok=True)
        
        # State
        self.config: Dict[str, Any] = {}
        self.extensions: Dict[str, ExtensionInfo] = {}
        self.layers: Dict[str, LayerInfo] = {}
        
        self._lock = threading.RLock()
        self._observer: Optional[Observer] = None
        self._initialized = False
        
        # Load config
        self._load_config()
        
        if auto_load:
            self.load_all()
        
        LOG.info(f"[ExtensionsLoader] Initialized: {len(self.extensions)} extensions")
    
    # ─────────────────────────────────────────────────────────────────────
    # CONFIG
    # ─────────────────────────────────────────────────────────────────────
    
    def _load_config(self) -> bool:
        """Load and validate extensions_config.json"""
        is_valid, errors, config = ConfigValidator.validate_file(self.config_path)
        
        if not is_valid:
            LOG.error(f"[Config] Validation failed:")
            for err in errors:
                LOG.error(f"  - {err}")
            return False
        
        self.config = config
        
        # Parse modules
        for name, mod_config in config.get("modules", {}).items():
            ext_config = ExtensionConfig(
                name=name,
                enabled=mod_config.get("enabled", True),
                config=mod_config.get("config", {})
            )
            
            ext_path = self.extensions_path / name
            if ext_path.exists():
                self.extensions[name] = ExtensionInfo(
                    name=name,
                    path=ext_path,
                    config=ext_config
                )
        
        # Parse layers
        for name, layer_config in config.get("layers", {}).items():
            self.layers[name] = LayerInfo(
                name=name,
                enabled=layer_config.get("enabled", True),
                modules=layer_config.get("modules", []),
                description=layer_config.get("description", "")
            )
            
            # Link modules to layers
            for mod_name in layer_config.get("modules", []):
                if mod_name in self.extensions:
                    self.extensions[mod_name].config.layer = name
        
        LOG.info(f"[Config] Loaded: {len(self.extensions)} modules, {len(self.layers)} layers")
        return True
    
    def reload_config(self) -> bool:
        """Reload config file and update extensions"""
        with self._lock:
            old_extensions = set(self.extensions.keys())
            
            if not self._load_config():
                return False
            
            new_extensions = set(self.extensions.keys())
            
            # Unload removed extensions
            for name in old_extensions - new_extensions:
                asyncio.run(self.unload_extension(name))
            
            # Load new extensions
            for name in new_extensions - old_extensions:
                if self.extensions[name].config.enabled:
                    asyncio.run(self.load_extension(name))
            
            # Publish event
            if get_bus():
                publish("extensions.config_reloaded", {
                    "added": list(new_extensions - old_extensions),
                    "removed": list(old_extensions - new_extensions)
                })
            
            return True
    
    def save_config(self) -> bool:
        """Save current config to file"""
        try:
            # Rebuild config from current state
            config = {
                "version": self.config.get("version", "2.0.0"),
                "description": self.config.get("description", "ALFA_CORE Extensions"),
                "modules": {},
                "layers": {}
            }
            
            for name, ext in self.extensions.items():
                config["modules"][name] = {
                    "enabled": ext.config.enabled,
                    "config": ext.config.config
                }
            
            for name, layer in self.layers.items():
                config["layers"][name] = {
                    "enabled": layer.enabled,
                    "modules": layer.modules,
                    "description": layer.description
                }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            LOG.info("[Config] Saved")
            return True
            
        except Exception as e:
            LOG.error(f"[Config] Save failed: {e}")
            return False
    
    # ─────────────────────────────────────────────────────────────────────
    # LOADING
    # ─────────────────────────────────────────────────────────────────────
    
    async def load_extension(self, name: str) -> bool:
        """Load a single extension"""
        with self._lock:
            if name not in self.extensions:
                LOG.error(f"[Load] Unknown extension: {name}")
                return False
            
            ext = self.extensions[name]
            
            if ext.loaded:
                LOG.debug(f"[Load] Already loaded: {name}")
                return True
            
            if not ext.config.enabled:
                LOG.debug(f"[Load] Disabled: {name}")
                return False
        
        try:
            # Add to path
            if str(self.extensions_path) not in sys.path:
                sys.path.insert(0, str(self.extensions_path))
            
            # Find entry point
            init_file = ext.path / "__init__.py"
            main_file = ext.path / f"{name}.py"
            
            if init_file.exists():
                module_file = init_file
            elif main_file.exists():
                module_file = main_file
            else:
                # Try to find any .py file
                py_files = list(ext.path.glob("*.py"))
                if py_files:
                    module_file = py_files[0]
                else:
                    raise ImportError(f"No Python files in {ext.path}")
            
            # Import
            spec = importlib.util.spec_from_file_location(name, module_file)
            if not spec or not spec.loader:
                raise ImportError(f"Cannot load spec for {name}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"extensions.{name}"] = module
            spec.loader.exec_module(module)
            
            ext.module = module
            
            # Create instance if class-based
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            if hasattr(module, class_name):
                ext.instance = getattr(module, class_name)(ext.config.config)
            elif hasattr(module, 'Extension'):
                ext.instance = module.Extension(ext.config.config)
            elif hasattr(module, 'setup'):
                module.setup(ext.config.config)
            
            # Discover commands
            ext.commands = getattr(module, 'COMMANDS', [])
            
            ext.loaded = True
            ext.loaded_at = time.time()
            ext.error = None
            
            LOG.info(f"[Load] Loaded: {name}")
            
            # Publish event
            if get_bus():
                publish("extensions.loaded", {"name": name})
            
            return True
            
        except Exception as e:
            ext.error = str(e)
            LOG.error(f"[Load] Failed: {name} - {e}")
            return False
    
    async def unload_extension(self, name: str) -> bool:
        """Unload an extension"""
        with self._lock:
            if name not in self.extensions:
                return False
            
            ext = self.extensions[name]
            
            if not ext.loaded:
                return True
        
        try:
            # Call cleanup
            if ext.instance and hasattr(ext.instance, 'cleanup'):
                ext.instance.cleanup()
            elif ext.module and hasattr(ext.module, 'cleanup'):
                ext.module.cleanup()
            
            # Remove from sys.modules
            mod_name = f"extensions.{name}"
            if mod_name in sys.modules:
                del sys.modules[mod_name]
            
            ext.module = None
            ext.instance = None
            ext.loaded = False
            
            LOG.info(f"[Unload] Unloaded: {name}")
            
            # Publish event
            if get_bus():
                publish("extensions.unloaded", {"name": name})
            
            return True
            
        except Exception as e:
            LOG.error(f"[Unload] Failed: {name} - {e}")
            return False
    
    async def reload_extension(self, name: str) -> bool:
        """Hot-reload an extension"""
        await self.unload_extension(name)
        return await self.load_extension(name)
    
    def load_all(self) -> Dict[str, bool]:
        """Load all enabled extensions"""
        results = {}
        
        for name, ext in self.extensions.items():
            if ext.config.enabled:
                results[name] = asyncio.get_event_loop().run_until_complete(
                    self.load_extension(name)
                )
        
        return results
    
    def load_layer(self, layer_name: str) -> Dict[str, bool]:
        """Load all extensions in a layer"""
        if layer_name not in self.layers:
            LOG.error(f"[Layer] Unknown layer: {layer_name}")
            return {}
        
        layer = self.layers[layer_name]
        if not layer.enabled:
            LOG.debug(f"[Layer] Disabled: {layer_name}")
            return {}
        
        results = {}
        for mod_name in layer.modules:
            if mod_name in self.extensions:
                results[mod_name] = asyncio.get_event_loop().run_until_complete(
                    self.load_extension(mod_name)
                )
        
        return results
    
    # ─────────────────────────────────────────────────────────────────────
    # HOT-RELOAD
    # ─────────────────────────────────────────────────────────────────────
    
    def enable_hot_reload(self) -> bool:
        """Enable file watching for hot-reload"""
        if not HAS_WATCHDOG:
            LOG.warning("[HotReload] watchdog not installed, hot-reload disabled")
            return False
        
        if self._observer:
            return True
        
        try:
            self._observer = Observer()
            handler = ExtensionFileHandler(self)
            
            # Watch extensions directory
            self._observer.schedule(handler, str(self.extensions_path), recursive=True)
            
            # Watch config file directory
            self._observer.schedule(handler, str(self.config_path.parent), recursive=False)
            
            self._observer.start()
            LOG.info("[HotReload] Enabled")
            return True
            
        except Exception as e:
            LOG.error(f"[HotReload] Failed to enable: {e}")
            return False
    
    def disable_hot_reload(self):
        """Disable file watching"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            LOG.info("[HotReload] Disabled")

    
    # ─────────────────────────────────────────────────────────────────────
    # QUERY
    # ─────────────────────────────────────────────────────────────────────
    
    def get(self, name: str) -> Optional[ExtensionInfo]:
        """Get extension by name"""
        return self.extensions.get(name)
    
    def get_module(self, name: str) -> Any:
        """Get extension module"""
        ext = self.extensions.get(name)
        return ext.module if ext else None
    
    def get_instance(self, name: str) -> Any:
        """Get extension instance"""
        ext = self.extensions.get(name)
        return ext.instance if ext else None
    
    def list_extensions(self, enabled_only: bool = False, layer: str = None) -> List[str]:
        """List extension names"""
        result = []
        for name, ext in self.extensions.items():
            if enabled_only and not ext.config.enabled:
                continue
            if layer and ext.config.layer != layer:
                continue
            result.append(name)
        return result
    
    def list_layers(self, enabled_only: bool = False) -> List[str]:
        """List layer names"""
        if enabled_only:
            return [name for name, layer in self.layers.items() if layer.enabled]
        return list(self.layers.keys())
    
    def get_layer(self, name: str) -> Optional[LayerInfo]:
        """Get layer by name"""
        return self.layers.get(name)
    
    def get_status(self) -> Dict[str, Any]:
        """Get loader status"""
        return {
            "config_version": self.config.get("version", "unknown"),
            "extensions_count": len(self.extensions),
            "loaded_count": sum(1 for e in self.extensions.values() if e.loaded),
            "layers_count": len(self.layers),
            "hot_reload": self._observer is not None,
            "extensions": {
                name: {
                    "enabled": ext.config.enabled,
                    "loaded": ext.loaded,
                    "layer": ext.config.layer,
                    "commands": ext.commands,
                    "error": ext.error
                }
                for name, ext in self.extensions.items()
            },
            "layers": {
                name: {
                    "enabled": layer.enabled,
                    "modules": layer.modules
                }
                for name, layer in self.layers.items()
            }
        }
    
    # ─────────────────────────────────────────────────────────────────────
    # MODULE OPERATIONS
    # ─────────────────────────────────────────────────────────────────────
    
    def enable(self, name: str) -> bool:
        """Enable an extension"""
        if name not in self.extensions:
            return False
        
        self.extensions[name].config.enabled = True
        return True
    
    def disable(self, name: str) -> bool:
        """Disable an extension"""
        if name not in self.extensions:
            return False
        
        ext = self.extensions[name]
        ext.config.enabled = False
        
        if ext.loaded:
            asyncio.get_event_loop().run_until_complete(self.unload_extension(name))
        
        return True
    
    def set_config(self, name: str, key: str, value: Any) -> bool:
        """Set extension config value"""
        if name not in self.extensions:
            return False
        
        self.extensions[name].config.config[key] = value
        
        # Notify extension
        ext = self.extensions[name]
        if ext.instance and hasattr(ext.instance, 'on_config_change'):
            ext.instance.on_config_change(key, value)
        
        return True
    
    def get_config(self, name: str, key: str = None) -> Any:
        """Get extension config"""
        if name not in self.extensions:
            return None
        
        config = self.extensions[name].config.config
        if key:
            return config.get(key)
        return config


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

_loader: Optional[ExtensionsLoader] = None


def get_extensions_loader() -> ExtensionsLoader:
    """Get or create ExtensionsLoader singleton"""
    global _loader
    if _loader is None:
        _loader = ExtensionsLoader()
    return _loader


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ALFA Extensions Loader")
    parser.add_argument("action", choices=["list", "load", "unload", "reload", "status", "validate"])
    parser.add_argument("--extension", "-e", help="Extension name")
    parser.add_argument("--layer", "-l", help="Layer name")
    parser.add_argument("--all", "-a", action="store_true", help="All extensions")
    parser.add_argument("--watch", "-w", action="store_true", help="Enable hot-reload")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    loader = ExtensionsLoader()
    
    if args.action == "list":
        print("Extensions:")
        for name, ext in loader.extensions.items():
            status = "✓" if ext.loaded else ("✗" if ext.error else "○")
            layer = f"[{ext.config.layer}]" if ext.config.layer else ""
            print(f"  {status} {name} {layer}")
        
        print("\nLayers:")
        for name, layer in loader.layers.items():
            print(f"  {name}: {', '.join(layer.modules)}")
    
    elif args.action == "load":
        if args.all:
            results = loader.load_all()
            for name, success in results.items():
                print(f"  {name}: {'✓' if success else '✗'}")
        elif args.layer:
            results = loader.load_layer(args.layer)
            for name, success in results.items():
                print(f"  {name}: {'✓' if success else '✗'}")
        elif args.extension:
            success = asyncio.run(loader.load_extension(args.extension))
            print(f"{args.extension}: {'✓' if success else '✗'}")
    
    elif args.action == "unload":
        if args.extension:
            success = asyncio.run(loader.unload_extension(args.extension))
            print(f"{args.extension}: {'✓' if success else '✗'}")
    
    elif args.action == "reload":
        if args.extension:
            success = asyncio.run(loader.reload_extension(args.extension))
            print(f"{args.extension}: {'✓' if success else '✗'}")
    
    elif args.action == "status":
        status = loader.get_status()
        print(f"Version: {status['config_version']}")
        print(f"Extensions: {status['loaded_count']}/{status['extensions_count']} loaded")
        print(f"Layers: {status['layers_count']}")
        print(f"Hot-Reload: {'enabled' if status['hot_reload'] else 'disabled'}")
    
    elif args.action == "validate":
        is_valid, errors, _ = ConfigValidator.validate_file(loader.config_path)
        if is_valid:
            print("✓ Config is valid")
        else:
            print("✗ Config validation failed:")
            for err in errors:
                print(f"  - {err}")
    
    if args.watch:
        loader.enable_hot_reload()
        print("Watching for changes... (Ctrl+C to stop)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            loader.disable_hot_reload()
