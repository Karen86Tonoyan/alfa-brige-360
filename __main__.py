#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# ALFA_CORE v2.0 — MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
"""
ALFA_CORE: Unified AI Assistant Backend

Usage:
    python -m alfa_core                  # Start full system
    python -m alfa_core --mode api       # API server only
    python -m alfa_core --mode sync      # Sync engine only
    python -m alfa_core --mode cli       # Interactive CLI
    python -m alfa_core status           # System status
    python -m alfa_core health           # Health check

Components:
    - Core Manager (module orchestration)
    - MCP Dispatcher (AI server routing)
    - Event Bus (pub/sub messaging)
    - Cerber (security guardian)
    - Sync Engine (LAN synchronization)
    - Plugin Engine (dynamic extensions)

Author: ALFA System / Karen86Tonoyan
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

# Add parent to path for imports
ALFA_ROOT = Path(__file__).parent
if str(ALFA_ROOT) not in sys.path:
    sys.path.insert(0, str(ALFA_ROOT))

# Version
VERSION = "2.0.0"
CODENAME = "Predator"

# Banner
BANNER = r"""
╔═══════════════════════════════════════════════════════════════╗
║     ___    __    ______   ___       __________  ____  ______  ║
║    /   |  / /   / ____/  /   |     / ____/ __ \/ __ \/ ____/  ║
║   / /| | / /   / /_     / /| |    / /   / / / / /_/ / __/     ║
║  / ___ |/ /___/ __/    / ___ |   / /___/ /_/ / _, _/ /___     ║
║ /_/  |_/_____/_/      /_/  |_|   \____/\____/_/ |_/_____/     ║
║                                                               ║
║  UNIFIED AI ASSISTANT BACKEND v{version}                     ║
║  Codename: {codename}                                         ║
╚═══════════════════════════════════════════════════════════════╝
""".format(version=VERSION.ljust(10), codename=CODENAME.ljust(15))


# ═══════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════

def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """Configure logging"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Format
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(log_level)
    
    # Root logger
    root = logging.getLogger()
    root.setLevel(log_level)
    root.addHandler(console)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root.addHandler(file_handler)
    
    return logging.getLogger("alfa.main")


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class ALFASystem:
    """
    Main system manager for ALFA_CORE.
    Orchestrates all components.
    """
    
    def __init__(self, mode: str = "full"):
        self.mode = mode
        self.running = False
        self.logger = logging.getLogger("alfa.system")
        
        # Components
        self._core_manager = None
        self._event_bus = None
        self._cerber = None
        self._sync_engine = None
        self._plugin_engine = None
        self._extensions_loader = None
        self._mcp_dispatcher = None
        
        # Tasks
        self._tasks = []
    
    async def start(self):
        """Start the system"""
        self.logger.info("Starting ALFA_CORE...")
        self.running = True
        
        # Initialize Event Bus first
        from core.event_bus import get_bus
        self._event_bus = get_bus()
        self.logger.info("✓ Event Bus initialized")
        
        # Initialize Cerber (security)
        try:
            from core.cerber import get_cerber
            self._cerber = get_cerber()
            self._cerber.start()
            self.logger.info("✓ Cerber security active")
        except Exception as e:
            self.logger.warning(f"✗ Cerber not available: {e}")
        
        # Initialize Core Manager
        try:
            from core_manager import CoreManager
            self._core_manager = CoreManager()
            self.logger.info("✓ Core Manager initialized")
        except Exception as e:
            self.logger.warning(f"✗ Core Manager not available: {e}")
        
        # Initialize Plugin Engine
        try:
            from core.plugin_engine import get_plugin_engine
            self._plugin_engine = get_plugin_engine()
            loaded = self._plugin_engine.load_all()
            active = sum(1 for v in loaded.values() if v)
            self.logger.info(f"✓ Plugin Engine: {active} plugins loaded")
        except Exception as e:
            self.logger.warning(f"✗ Plugin Engine not available: {e}")
        
        # Initialize Extensions Loader
        try:
            from core.extensions_loader import get_extensions_loader
            self._extensions_loader = get_extensions_loader()
            self._extensions_loader.load_all()
            self.logger.info("✓ Extensions loaded")
        except Exception as e:
            self.logger.warning(f"✗ Extensions Loader not available: {e}")
        
        # Initialize MCP Dispatcher
        try:
            from core.mcp_dispatcher import MCPDispatcher
            self._mcp_dispatcher = MCPDispatcher()
            self.logger.info("✓ MCP Dispatcher initialized")
        except Exception as e:
            self.logger.warning(f"✗ MCP Dispatcher not available: {e}")
        
        # Mode-specific initialization
        if self.mode in ("full", "sync"):
            await self._start_sync()
        
        if self.mode in ("full", "api"):
            await self._start_api()
        
        # Publish system started event
        from core.event_bus import publish
        publish("system.started", {"mode": self.mode, "version": VERSION})
        
        self.logger.info(f"ALFA_CORE started (mode: {self.mode})")
    
    async def _start_sync(self):
        """Start sync engine"""
        try:
            from core.sync_engine import SyncEngine
            sync_folder = ALFA_ROOT / "sync_data"
            self._sync_engine = SyncEngine(str(sync_folder))
            await self._sync_engine.start()
            self.logger.info("✓ Sync Engine started")
        except Exception as e:
            self.logger.warning(f"✗ Sync Engine not available: {e}")
    
    async def _start_api(self):
        """Start API server"""
        try:
            # Check if we have alfa_cloud API
            api_path = ALFA_ROOT / "alfa_cloud" / "api" / "server.py"
            if api_path.exists():
                self.logger.info("✓ API server available (start separately with: python alfa_cloud/api/server.py)")
            else:
                self.logger.info("○ API server not configured")
        except Exception as e:
            self.logger.warning(f"✗ API not available: {e}")
    
    async def stop(self):
        """Stop the system"""
        self.logger.info("Stopping ALFA_CORE...")
        self.running = False
        
        # Publish shutdown event
        from core.event_bus import publish
        publish("system.stopping", {})
        
        # Stop components in reverse order
        if self._sync_engine:
            await self._sync_engine.stop()
            self.logger.info("✓ Sync Engine stopped")
        
        if self._cerber:
            self._cerber.stop()
            self.logger.info("✓ Cerber stopped")
        
        # Cancel tasks
        for task in self._tasks:
            task.cancel()
        
        self.logger.info("ALFA_CORE stopped")
    
    def get_status(self) -> dict:
        """Get system status"""
        status = {
            "version": VERSION,
            "codename": CODENAME,
            "mode": self.mode,
            "running": self.running,
            "components": {}
        }
        
        # Event Bus
        if self._event_bus:
            status["components"]["event_bus"] = "active"
        
        # Cerber
        if self._cerber:
            status["components"]["cerber"] = "active" if self._cerber._running else "inactive"
        
        # Core Manager
        if self._core_manager:
            status["components"]["core_manager"] = "active"
            status["modules"] = self._core_manager.get_status()
        
        # Plugin Engine
        if self._plugin_engine:
            plugin_status = self._plugin_engine.get_status()
            status["components"]["plugin_engine"] = f"{plugin_status['active_count']}/{plugin_status['plugins_count']} active"
        
        # Extensions
        if self._extensions_loader:
            ext_status = self._extensions_loader.get_status()
            status["components"]["extensions"] = f"{ext_status['loaded_count']}/{ext_status['extensions_count']} loaded"
        
        # MCP Dispatcher
        if self._mcp_dispatcher:
            status["components"]["mcp_dispatcher"] = "active"
        
        # Sync Engine
        if self._sync_engine:
            sync_stats = self._sync_engine.get_stats()
            status["components"]["sync_engine"] = sync_stats["state"]
            status["sync"] = sync_stats
        
        return status


# ═══════════════════════════════════════════════════════════════════════════
# CLI COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

async def cmd_start(args):
    """Start ALFA_CORE system"""
    print(BANNER)
    
    logger = setup_logging(args.log_level, args.log_file)
    
    system = ALFASystem(mode=args.mode)
    
    # Handle shutdown
    loop = asyncio.get_event_loop()
    
    def shutdown_handler():
        logger.info("Shutdown signal received")
        asyncio.create_task(system.stop())
    
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, shutdown_handler)
        loop.add_signal_handler(signal.SIGTERM, shutdown_handler)
    
    try:
        await system.start()
        
        # Keep running
        while system.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
    finally:
        await system.stop()


async def cmd_status(args):
    """Show system status"""
    try:
        from core_manager import CoreManager
        manager = CoreManager()
        status = manager.get_status()
        
        print(f"\n{'='*50}")
        print(f"ALFA_CORE Status")
        print(f"{'='*50}")
        print(f"Version: {VERSION}")
        print(f"Modules: {status['extensions_count']} extensions, {status['mcp_servers_count']} MCP servers")
        print(f"Layers: {', '.join(status['layers'].keys())}")
        print(f"{'='*50}\n")
        
        if args.json:
            print(json.dumps(status, indent=2))
            
    except Exception as e:
        print(f"Error: {e}")


async def cmd_health(args):
    """Health check"""
    checks = {
        "core_manager": False,
        "event_bus": False,
        "cerber": False,
        "mcp_dispatcher": False,
        "config_valid": False
    }
    
    try:
        from core_manager import CoreManager
        CoreManager()
        checks["core_manager"] = True
    except:
        pass
    
    try:
        from core.event_bus import get_bus
        get_bus()
        checks["event_bus"] = True
    except:
        pass
    
    try:
        from core.cerber import get_cerber
        get_cerber()
        checks["cerber"] = True
    except:
        pass
    
    try:
        from core.mcp_dispatcher import MCPDispatcher
        MCPDispatcher()
        checks["mcp_dispatcher"] = True
    except:
        pass
    
    try:
        from core.extensions_loader import ConfigValidator
        is_valid, _, _ = ConfigValidator.validate_file(ALFA_ROOT / "extensions_config.json")
        checks["config_valid"] = is_valid
    except:
        pass
    
    print(f"\n{'='*40}")
    print("ALFA_CORE Health Check")
    print(f"{'='*40}")
    
    all_ok = True
    for name, ok in checks.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {name}")
        if not ok:
            all_ok = False
    
    print(f"{'='*40}")
    print(f"Overall: {'HEALTHY' if all_ok else 'DEGRADED'}\n")
    
    return 0 if all_ok else 1


async def cmd_cli(args):
    """Interactive CLI mode"""
    print(BANNER)
    print("Interactive CLI - type 'help' for commands, 'quit' to exit\n")
    
    # Initialize components
    from core_manager import CoreManager
    manager = CoreManager()
    
    while True:
        try:
            cmd = input("ALFA> ").strip()
            
            if not cmd:
                continue
            
            if cmd in ("quit", "exit", "q"):
                break
            
            if cmd == "help":
                print("""
Commands:
  status          - Show system status
  modules         - List loaded modules
  layers          - List layers
  health          - Health check
  load <module>   - Load a module
  unload <module> - Unload a module
  mcp <server>    - Check MCP server status
  quit            - Exit CLI
                """)
            
            elif cmd == "status":
                status = manager.get_status()
                print(f"Modules: {len(status['modules'])}")
                print(f"Layers: {list(status['layers'].keys())}")
            
            elif cmd == "modules":
                for name in manager.list_modules():
                    print(f"  - {name}")
            
            elif cmd == "layers":
                for layer in manager.list_layers():
                    print(f"  - {layer}")
            
            elif cmd.startswith("load "):
                module = cmd.split(" ", 1)[1]
                result = manager.load_module(module)
                print(f"Loaded: {result.name if result else 'failed'}")
            
            elif cmd.startswith("unload "):
                module = cmd.split(" ", 1)[1]
                success = manager.unload_module(module)
                print(f"Unloaded: {'ok' if success else 'failed'}")
            
            elif cmd == "health":
                await cmd_health(args)
            
            else:
                print(f"Unknown command: {cmd}")
                
        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("Goodbye!")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="ALFA_CORE - Unified AI Assistant Backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m alfa_core                    Start full system
  python -m alfa_core --mode api         Start API only
  python -m alfa_core --mode sync        Start sync only
  python -m alfa_core --mode cli         Interactive CLI
  python -m alfa_core status             Show status
  python -m alfa_core health             Health check
        """
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=["start", "status", "health", "cli"],
        help="Command to run (default: start)"
    )
    
    parser.add_argument(
        "--mode", "-m",
        default="full",
        choices=["full", "api", "sync", "cli"],
        help="Run mode (default: full)"
    )
    
    parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)"
    )
    
    parser.add_argument(
        "--log-file", "-f",
        help="Log file path"
    )
    
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output in JSON format"
    )
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"ALFA_CORE v{VERSION} ({CODENAME})"
    )
    
    args = parser.parse_args()
    
    # Route commands
    commands = {
        "start": cmd_start,
        "status": cmd_status,
        "health": cmd_health,
        "cli": cmd_cli
    }
    
    # Handle CLI mode override
    if args.mode == "cli":
        args.command = "cli"
    
    try:
        result = asyncio.run(commands[args.command](args))
        sys.exit(result if isinstance(result, int) else 0)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
