#!/usr/bin/env python3
"""
===============================================
ALFA_CORE v2.0 - CORE MANAGER
===============================================
Centralny dispatcher dla systemu ALFA.

Funkcje:
- Ładowanie modułów lokalnych (extensions/)
- Zarządzanie MCP serwerami (http/sse/stdio)
- Routing przez warstwy (layers)
- Sandbox execution (CodeExecutor)
- Health monitoring
- Hot-reload modułów

Author: ALFA System / Karen86Tonoyan
"""

import json
import importlib
import importlib.util
import sys
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [CORE] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# =============================================================================
# PATHS & CONFIG
# =============================================================================

ALFA_ROOT = Path(__file__).parent
CONFIG_PATH = ALFA_ROOT / "config"
MODULES_PATH = ALFA_ROOT / "modules"
EXTENSIONS_PATH = ALFA_ROOT / "extensions"  # Legacy ALFA_BRAIN compatibility

# Ensure paths exist
for p in [CONFIG_PATH, MODULES_PATH]:
    p.mkdir(exist_ok=True)


# =============================================================================
# DATA CLASSES
# =============================================================================

class ModuleType(Enum):
    LOCAL = "local"       # Python module in extensions/
    MCP_HTTP = "mcp_http"   # MCP server via HTTP
    MCP_SSE = "mcp_sse"    # MCP server via SSE
    MCP_STDIO = "mcp_stdio"  # MCP server via STDIO
    LAYER = "layer"       # Module layer (collection)


class ModuleStatus(Enum):
    LOADED = "loaded"
    UNLOADED = "unloaded"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ModuleInfo:
    """Information about a loaded module."""
    name: str
    type: ModuleType
    status: ModuleStatus = ModuleStatus.UNLOADED
    enabled: bool = True
    layer: Optional[str] = None
    description: str = ""
    commands: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    instance: Any = None
    error: Optional[str] = None


# =============================================================================
# CORE MANAGER
# =============================================================================

class CoreManager:
    """
    Central manager for ALFA_CORE system.
    Handles module loading, MCP dispatching, and layer routing.
    """
    
    def __init__(self):
        self.modules: Dict[str, ModuleInfo] = {}
        self.layers: Dict[str, List[str]] = {}
        self.extensions_config: Dict[str, Any] = {}
        self.mcp_config: Dict[str, Any] = {}
        self._mcp_dispatcher = None
        self._code_executor = None
        
        # Load configurations
        self._load_extensions_config()
        self._load_mcp_config()
        self._discover_layers()
    
    # -------------------------------------------------------------------------
    # CONFIG LOADING
    # -------------------------------------------------------------------------
    
    def _load_extensions_config(self):
        """Load legacy extensions_config.json."""
        config_file = ALFA_ROOT / "extensions_config.json"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                self.extensions_config = json.load(f)
            logger.info(f"Loaded extensions config: {len(self.extensions_config.get('modules', {}))} modules")
    
    def _load_mcp_config(self):
        """Load MCP servers configuration."""
        mcp_file = CONFIG_PATH / "mcp_servers.json"
        if mcp_file.exists():
            with open(mcp_file, 'r', encoding='utf-8') as f:
                self.mcp_config = json.load(f)
            logger.info(f"Loaded MCP config: {len(self.mcp_config.get('servers', {}))} servers")
    
    def _discover_layers(self):
        """Discover module layers from MCP config and directory structure."""
        # From MCP config
        if 'layers' in self.mcp_config:
            for layer_name, layer_data in self.mcp_config['layers'].items():
                self.layers[layer_name] = layer_data.get('servers', [])
        
        # From modules directory
        if MODULES_PATH.exists():
            for subdir in MODULES_PATH.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('_'):
                    if subdir.name not in self.layers:
                        self.layers[subdir.name] = []
        
        logger.info(f"Discovered layers: {list(self.layers.keys())}")
    
    # -------------------------------------------------------------------------
    # MODULE LOADING
    # -------------------------------------------------------------------------
    
    def load_module(self, name: str) -> Optional[ModuleInfo]:
        """
        Load a module by name.
        Tries: extensions/ -> modules/ -> MCP servers
        """
        # Check if already loaded
        if name in self.modules and self.modules[name].status == ModuleStatus.LOADED:
            return self.modules[name]
        
        # Try loading from different sources
        info = None
        
        # 1. Try extensions/ (legacy ALFA_BRAIN)
        info = self._load_extension_module(name)
        if info:
            self.modules[name] = info
            return info
        
        # 2. Try modules/ layers
        info = self._load_layer_module(name)
        if info:
            self.modules[name] = info
            return info
        
        # 3. Try MCP server
        info = self._load_mcp_module(name)
        if info:
            self.modules[name] = info
            return info
        
        logger.warning(f"Module not found: {name}")
        return None
    
    def _load_extension_module(self, name: str) -> Optional[ModuleInfo]:
        """Load module from extensions/ directory."""
        # Check in extensions config
        ext_config = self.extensions_config.get('modules', {}).get(name, {})
        if not ext_config.get('enabled', True):
            return ModuleInfo(
                name=name,
                type=ModuleType.LOCAL,
                status=ModuleStatus.DISABLED,
                enabled=False
            )
        
        # Try to import
        module_path = EXTENSIONS_PATH / name
        if not module_path.exists():
            return None
        
        try:
            # Add to path if needed
            if str(EXTENSIONS_PATH) not in sys.path:
                sys.path.insert(0, str(EXTENSIONS_PATH))
            
            # Import module
            mod = importlib.import_module(name)
            
            info = ModuleInfo(
                name=name,
                type=ModuleType.LOCAL,
                status=ModuleStatus.LOADED,
                enabled=True,
                description=getattr(mod, 'DESCRIPTION', ''),
                commands=getattr(mod, 'COMMANDS', []),
                config=ext_config.get('config', {}),
                instance=mod
            )
            
            logger.info(f"Loaded extension: {name}")
            return info
            
        except Exception as e:
            logger.error(f"Failed to load extension {name}: {e}")
            return ModuleInfo(
                name=name,
                type=ModuleType.LOCAL,
                status=ModuleStatus.ERROR,
                error=str(e)
            )
    
    def _load_layer_module(self, name: str) -> Optional[ModuleInfo]:
        """Load module from modules/ layer directory."""
        for layer_name in self.layers:
            module_path = MODULES_PATH / layer_name / f"{name}.py"
            init_path = MODULES_PATH / layer_name / "__init__.py"
            
            if module_path.exists() or (MODULES_PATH / layer_name / name).is_dir():
                try:
                    # Import from layer
                    spec = importlib.util.spec_from_file_location(
                        f"modules.{layer_name}.{name}",
                        init_path if (MODULES_PATH / layer_name / name).is_dir() else module_path
                    )
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        
                        info = ModuleInfo(
                            name=name,
                            type=ModuleType.LAYER,
                            status=ModuleStatus.LOADED,
                            enabled=True,
                            layer=layer_name,
                            description=getattr(mod, '__doc__', ''),
                            instance=mod
                        )
                        
                        logger.info(f"Loaded layer module: {layer_name}/{name}")
                        return info
                        
                except Exception as e:
                    logger.error(f"Failed to load layer module {name}: {e}")
                    return ModuleInfo(
                        name=name,
                        type=ModuleType.LAYER,
                        status=ModuleStatus.ERROR,
                        layer=layer_name,
                        error=str(e)
                    )
        
        return None
    
    def _load_mcp_module(self, name: str) -> Optional[ModuleInfo]:
        """Load MCP server as module."""
        server_config = self.mcp_config.get('servers', {}).get(name)
        if not server_config:
            return None
        
        server_type = server_config.get('type', 'http')
        type_map = {
            'http': ModuleType.MCP_HTTP,
            'sse': ModuleType.MCP_SSE,
            'stdio': ModuleType.MCP_STDIO
        }
        
        info = ModuleInfo(
            name=name,
            type=type_map.get(server_type, ModuleType.MCP_HTTP),
            status=ModuleStatus.LOADED,
            enabled=server_config.get('enabled', True),
            layer=server_config.get('layer'),
            description=server_config.get('description', ''),
            config=server_config
        )
        
        logger.info(f"Registered MCP server: {name} ({server_type})")
        return info
    
    def unload_module(self, name: str) -> bool:
        """Unload a module."""
        if name not in self.modules:
            return False
        
        info = self.modules[name]
        
        # Clean up instance
        if info.instance and hasattr(info.instance, 'cleanup'):
            try:
                info.instance.cleanup()
            except Exception as e:
                logger.warning(f"Cleanup failed for {name}: {e}")
        
        info.status = ModuleStatus.UNLOADED
        info.instance = None
        
        logger.info(f"Unloaded module: {name}")
        return True
    
    def reload_module(self, name: str) -> Optional[ModuleInfo]:
        """Reload a module (hot-reload)."""
        self.unload_module(name)
        
        # Clear from sys.modules if it's a Python module
        module_names = [k for k in sys.modules if name in k]
        for mod_name in module_names:
            del sys.modules[mod_name]
        
        return self.load_module(name)
    
    # -------------------------------------------------------------------------
    # MODULE DISCOVERY & LISTING
    # -------------------------------------------------------------------------
    
    def list_modules(self, layer: Optional[str] = None, enabled_only: bool = False) -> List[str]:
        """List available modules."""
        modules = set()
        
        # From extensions config
        for name, config in self.extensions_config.get('modules', {}).items():
            if enabled_only and not config.get('enabled', True):
                continue
            modules.add(name)
        
        # From MCP config
        for name, config in self.mcp_config.get('servers', {}).items():
            if layer and config.get('layer') != layer:
                continue
            if enabled_only and not config.get('enabled', True):
                continue
            modules.add(name)
        
        # From loaded modules
        for name, info in self.modules.items():
            if layer and info.layer != layer:
                continue
            if enabled_only and not info.enabled:
                continue
            modules.add(name)
        
        return sorted(modules)
    
    def list_layers(self) -> List[str]:
        """List available layers."""
        return sorted(self.layers.keys())
    
    def get_module_info(self, name: str) -> Optional[ModuleInfo]:
        """Get information about a module."""
        if name in self.modules:
            return self.modules[name]
        
        # Try to load and return info
        return self.load_module(name)
    
    # -------------------------------------------------------------------------
    # MCP DISPATCHER INTEGRATION
    # -------------------------------------------------------------------------
    
    def get_mcp_dispatcher(self):
        """Get MCP dispatcher instance."""
        if self._mcp_dispatcher is None:
            try:
                from core.mcp_dispatcher import MCPDispatcher
                self._mcp_dispatcher = MCPDispatcher()
            except ImportError:
                logger.warning("MCP dispatcher not available")
        return self._mcp_dispatcher
    
    async def mcp_call(self, server: str, method: str, **params):
        """Execute MCP call."""
        dispatcher = self.get_mcp_dispatcher()
        if dispatcher:
            return await dispatcher.execute(server, method, params)
        return None
    
    async def mcp_health(self) -> Dict[str, str]:
        """Check MCP servers health."""
        dispatcher = self.get_mcp_dispatcher()
        if dispatcher:
            statuses = await dispatcher.check_all_health()
            return {name: status.value for name, status in statuses.items()}
        return {}
    
    # -------------------------------------------------------------------------
    # CODE EXECUTOR INTEGRATION
    # -------------------------------------------------------------------------
    
    def get_code_executor(self, sandbox: bool = True, timeout: int = 30):
        """Get CodeExecutor instance."""
        if self._code_executor is None:
            try:
                # Try ALFA_BRAIN location
                from extensions.coding.code_executor import CodeExecutor
                self._code_executor = CodeExecutor(sandbox=sandbox, timeout=timeout)
            except ImportError:
                try:
                    # Try local
                    from code_executor import CodeExecutor
                    self._code_executor = CodeExecutor(sandbox=sandbox, timeout=timeout)
                except ImportError:
                    logger.warning("CodeExecutor not available")
        return self._code_executor
    
    def execute_code(self, code: str, language: str = "python") -> tuple:
        """Execute code in sandbox."""
        executor = self.get_code_executor()
        if not executor:
            return (1, "CodeExecutor not available")
        
        if language == "python":
            return executor.run_python(code)
        elif language == "powershell":
            return executor.run_powershell(code)
        elif language == "bash":
            return executor.run_bash(code)
        else:
            return (1, f"Unsupported language: {language}")
    
    # -------------------------------------------------------------------------
    # LAYER OPERATIONS
    # -------------------------------------------------------------------------
    
    def get_layer(self, name: str):
        """Get layer module."""
        layer_path = MODULES_PATH / name / "__init__.py"
        if layer_path.exists():
            try:
                spec = importlib.util.spec_from_file_location(f"modules.{name}", layer_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    return mod
            except Exception as e:
                logger.error(f"Failed to load layer {name}: {e}")
        return None
    
    def get_creative_layer(self):
        """Get Creative layer (figma, webflow)."""
        return self.get_layer("creative")
    
    def get_knowledge_layer(self):
        """Get Knowledge layer (deepwiki, microsoft-docs)."""
        return self.get_layer("knowledge")
    
    def get_automation_layer(self):
        """Get Automation layer (apify, markitdown)."""
        return self.get_layer("automation")
    
    def get_dev_layer(self):
        """Get Dev layer (idl-vscode, pylance)."""
        return self.get_layer("dev")
    
    # -------------------------------------------------------------------------
    # STATUS & INFO
    # -------------------------------------------------------------------------
    
    def get_status(self) -> Dict[str, Any]:
        """Get full system status."""
        return {
            "version": "2.0.0",
            "modules": {
                name: {
                    "type": info.type.value,
                    "status": info.status.value,
                    "enabled": info.enabled,
                    "layer": info.layer,
                    "error": info.error
                }
                for name, info in self.modules.items()
            },
            "layers": self.layers,
            "extensions_count": len(self.extensions_config.get('modules', {})),
            "mcp_servers_count": len(self.mcp_config.get('servers', {}))
        }
    
    def run_tests(self) -> Dict[str, bool]:
        """Run basic system tests."""
        results = {}
        
        # Test module loading
        for mod_name in ['coding', 'chat']:
            try:
                info = self.load_module(mod_name)
                results[f"load_{mod_name}"] = info is not None and info.status == ModuleStatus.LOADED
            except Exception:
                results[f"load_{mod_name}"] = False
        
        # Test MCP dispatcher
        try:
            dispatcher = self.get_mcp_dispatcher()
            results["mcp_dispatcher"] = dispatcher is not None
        except Exception:
            results["mcp_dispatcher"] = False
        
        # Test CodeExecutor
        try:
            executor = self.get_code_executor()
            if executor:
                rc, out = executor.run_python("print('test')")
                results["code_executor"] = rc == 0 and 'test' in out
            else:
                results["code_executor"] = False
        except Exception:
            results["code_executor"] = False
        
        return results


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_manager: Optional[CoreManager] = None


def get_manager() -> CoreManager:
    """Get global CoreManager instance."""
    global _manager
    if _manager is None:
        _manager = CoreManager()
    return _manager


# =============================================================================
# CLI
# =============================================================================

def cli_main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ALFA_CORE Manager v2.0")
    parser.add_argument('command', nargs='?', default='status',
                        choices=['status', 'list', 'load', 'info', 'test', 'layers', 'health'])
    parser.add_argument('name', nargs='?', help='Module name')
    parser.add_argument('--layer', '-l', help='Filter by layer')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    manager = get_manager()
    
    if args.command == 'status':
        status = manager.get_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print(f"ALFA_CORE v{status['version']}")
            print(f"Extensions: {status['extensions_count']}")
            print(f"MCP Servers: {status['mcp_servers_count']}")
            print(f"Layers: {', '.join(status['layers'].keys())}")
    
    elif args.command == 'list':
        modules = manager.list_modules(layer=args.layer)
        if args.json:
            print(json.dumps(modules))
        else:
            print(f"Modules{f' in {args.layer}' if args.layer else ''}:")
            for name in modules:
                info = manager.modules.get(name)
                status = info.status.value if info else 'not loaded'
                print(f"  - {name}: {status}")
    
    elif args.command == 'layers':
        layers = manager.list_layers()
        if args.json:
            print(json.dumps(manager.layers))
        else:
            print("Layers:")
            for layer in layers:
                servers = manager.layers.get(layer, [])
                print(f"  {layer}: {', '.join(servers) if servers else '(empty)'}")
    
    elif args.command == 'load' and args.name:
        info = manager.load_module(args.name)
        if info:
            print(f"Loaded: {args.name} ({info.type.value}) - {info.status.value}")
        else:
            print(f"Failed to load: {args.name}")
    
    elif args.command == 'info' and args.name:
        info = manager.get_module_info(args.name)
        if info:
            if args.json:
                print(json.dumps({
                    'name': info.name,
                    'type': info.type.value,
                    'status': info.status.value,
                    'layer': info.layer,
                    'description': info.description,
                    'commands': info.commands
                }, indent=2))
            else:
                print(f"Module: {info.name}")
                print(f"Type: {info.type.value}")
                print(f"Status: {info.status.value}")
                print(f"Layer: {info.layer or '-'}")
                print(f"Description: {info.description or '-'}")
                print(f"Commands: {', '.join(info.commands) if info.commands else '-'}")
        else:
            print(f"Module not found: {args.name}")
    
    elif args.command == 'test':
        print("Running ALFA_CORE tests...")
        results = manager.run_tests()
        for test, passed in results.items():
            icon = "✅" if passed else "❌"
            print(f"  {icon} {test}")
        
        all_passed = all(results.values())
        print(f"\n{'All tests passed!' if all_passed else 'Some tests failed.'}")
    
    elif args.command == 'health':
        print("Checking MCP servers health...")
        health = asyncio.run(manager.mcp_health())
        if health:
            for name, status in health.items():
                icon = "✅" if status == "online" else "❌" if status == "offline" else "⚠️"
                print(f"  {icon} {name}: {status}")
        else:
            print("  MCP dispatcher not available")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    cli_main()
