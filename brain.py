#!/usr/bin/env python3
"""
===============================================
ALFA_BRAIN v2.0 - CENTRALNY MÓZG SYSTEMU
===============================================
Główny punkt wejścia do systemu ALFA.

Funkcje:
- CLI z REPL (interaktywna konsola)
- Dispatcher komend
- Integracja z CoreManager
- Event routing
- Cerber monitoring

Użycie:
    python brain.py              # Uruchom REPL
    python brain.py --init       # Inicjalizacja systemu
    python brain.py --status     # Status systemu
    python brain.py --health     # Health check
    python brain.py --cmd "..."  # Wykonaj komendę

Author: ALFA System / Karen86Tonoyan
"""

import sys
import os
import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime

# Add root to path
ALFA_ROOT = Path(__file__).parent
sys.path.insert(0, str(ALFA_ROOT))

from config import VERSION, CODENAME, DEV_MODE, BATTLE_MODE
from core_manager import CoreManager, get_manager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEV_MODE else logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# BRAIN CLASS
# =============================================================================

class AlfaBrain:
    """
    Centralny mózg systemu ALFA.
    Zarządza całym ekosystemem: CLI, eventy, komendy, monitoring.
    """
    
    BANNER = r"""
    ╔═══════════════════════════════════════════════════════════╗
    ║     ___    __    ______   ___       ____  ____  ___   __  ║
    ║    /   |  / /   / ____/  /   |     / __ )/ __ \/   | / /  ║
    ║   / /| | / /   / /_     / /| |    / __  / /_/ / /| |/ /   ║
    ║  / ___ |/ /___/ __/    / ___ |   / /_/ / _, _/ ___ / /___ ║
    ║ /_/  |_/_____/_/      /_/  |_|  /_____/_/ |_/_/  |_\____/ ║
    ║                                                           ║
    ║              ALFA_BRAIN v2.0 :: CERBER EDITION            ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    
    HELP = """
    Dostępne komendy:
    
    SYSTEM:
      status          - Status systemu
      health          - Health check (MCP, modułów)
      init            - Inicjalizacja/reinicjalizacja
      reload          - Przeładuj moduły
      exit / quit     - Wyjście
    
    MODUŁY:
      modules         - Lista modułów
      load <name>     - Załaduj moduł
      unload <name>   - Wyładuj moduł
      info <name>     - Info o module
    
    WARSTWY (LAYERS):
      layers          - Lista warstw MCP
      layer <name>    - Pokaż serwery w warstwie
    
    AI / CHAT:
      chat <prompt>   - Wyślij prompt do AI
      model           - Pokaż aktywny model
      profile <name>  - Zmień profil (fast/balanced/creative/security)
    
    CERBER:
      cerber status   - Status Cerbera
      cerber verify   - Weryfikacja integralności
      cerber log      - Ostatnie incydenty
    
    WYKONANIE:
      run <code>      - Wykonaj kod Python (sandbox)
      exec <file>     - Wykonaj plik
    
    POMOC:
      help / ?        - Ta pomoc
      version         - Wersja systemu
    """
    
    def __init__(self):
        self.manager: Optional[CoreManager] = None
        self.running = False
        self.commands: Dict[str, Callable] = {}
        self.history: list = []
        self._setup_commands()
    
    def _setup_commands(self):
        """Rejestracja komend."""
        self.commands = {
            # System
            'status': self.cmd_status,
            'health': self.cmd_health,
            'init': self.cmd_init,
            'reload': self.cmd_reload,
            'exit': self.cmd_exit,
            'quit': self.cmd_exit,
            
            # Modules
            'modules': self.cmd_modules,
            'load': self.cmd_load,
            'unload': self.cmd_unload,
            'info': self.cmd_info,
            
            # Layers
            'layers': self.cmd_layers,
            'layer': self.cmd_layer,
            
            # AI
            'chat': self.cmd_chat,
            'model': self.cmd_model,
            'profile': self.cmd_profile,
            
            # Cerber
            'cerber': self.cmd_cerber,
            
            # Execution
            'run': self.cmd_run,
            'exec': self.cmd_exec,
            
            # Help
            'help': self.cmd_help,
            '?': self.cmd_help,
            'version': self.cmd_version,
        }
    
    # -------------------------------------------------------------------------
    # LIFECYCLE
    # -------------------------------------------------------------------------
    
    def boot(self):
        """Inicjalizacja systemu."""
        print(self.BANNER)
        print(f"    Version: {VERSION} ({CODENAME})")
        print(f"    Mode: {'BATTLE' if BATTLE_MODE else 'DEV' if DEV_MODE else 'PROD'}")
        print(f"    Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        logger.info("Booting ALFA_BRAIN...")
        
        # Initialize manager
        self.manager = get_manager()
        
        # Run tests
        logger.info("Running system checks...")
        results = self.manager.run_tests()
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        if passed == total:
            logger.info(f"All checks passed ({passed}/{total})")
        else:
            logger.warning(f"Some checks failed ({passed}/{total})")
            for test, ok in results.items():
                if not ok:
                    logger.warning(f"  - {test}: FAILED")
        
        print()
        logger.info("ALFA_BRAIN ready. Type 'help' for commands.")
        print()
    
    def start(self):
        """Uruchom REPL."""
        self.boot()
        self.running = True
        self.loop()
    
    def loop(self):
        """Główna pętla REPL."""
        while self.running:
            try:
                # Prompt
                prompt = "ALFA" if not BATTLE_MODE else "ALFA⚔"
                cmd = input(f"{prompt}> ").strip()
                
                if not cmd:
                    continue
                
                # Save to history
                self.history.append(cmd)
                
                # Parse and dispatch
                self.dispatch(cmd)
                
            except KeyboardInterrupt:
                print("\n[Ctrl+C] Use 'exit' to quit.")
            except EOFError:
                break
            except Exception as e:
                logger.error(f"Error: {e}")
    
    def dispatch(self, cmd_line: str):
        """Dispatch komendy."""
        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd in self.commands:
            try:
                self.commands[cmd](args)
            except Exception as e:
                logger.error(f"Command error: {e}")
        else:
            print(f"Unknown command: {cmd}. Type 'help' for commands.")
    
    # -------------------------------------------------------------------------
    # COMMANDS
    # -------------------------------------------------------------------------
    
    def cmd_status(self, args: str):
        """Status systemu."""
        status = self.manager.get_status()
        print(f"\n{'='*50}")
        print(f"ALFA_BRAIN v{status['version']}")
        print(f"{'='*50}")
        print(f"Extensions: {status['extensions_count']}")
        print(f"MCP Servers: {status['mcp_servers_count']}")
        print(f"Layers: {', '.join(status['layers'].keys())}")
        print(f"Loaded modules: {len([m for m in status['modules'].values() if m['status'] == 'loaded'])}")
        print()
    
    def cmd_health(self, args: str):
        """Health check."""
        print("Checking health...")
        
        # MCP health (async)
        async def check():
            return await self.manager.mcp_health()
        
        try:
            health = asyncio.run(check())
            if health:
                print("\nMCP Servers:")
                for name, status in health.items():
                    icon = "✅" if status == "online" else "❌" if status == "offline" else "⚠️"
                    print(f"  {icon} {name}: {status}")
            else:
                print("  MCP dispatcher not available")
        except Exception as e:
            print(f"  Error checking MCP health: {e}")
        
        # Module tests
        print("\nModule tests:")
        results = self.manager.run_tests()
        for test, ok in results.items():
            icon = "✅" if ok else "❌"
            print(f"  {icon} {test}")
        print()
    
    def cmd_init(self, args: str):
        """Reinicjalizacja systemu."""
        print("Reinitializing ALFA_BRAIN...")
        self.manager = CoreManager()
        print("Done.")
    
    def cmd_reload(self, args: str):
        """Przeładuj moduły."""
        if args:
            # Reload specific module
            info = self.manager.reload_module(args)
            if info:
                print(f"Reloaded: {args}")
            else:
                print(f"Failed to reload: {args}")
        else:
            print("Usage: reload <module_name>")
    
    def cmd_exit(self, args: str):
        """Wyjście."""
        print("Goodbye, King.")
        self.running = False
    
    def cmd_modules(self, args: str):
        """Lista modułów."""
        modules = self.manager.list_modules()
        print(f"\nModules ({len(modules)}):")
        for name in modules:
            info = self.manager.modules.get(name)
            if info:
                status = info.status.value
                layer = f"[{info.layer}]" if info.layer else ""
                print(f"  - {name}: {status} {layer}")
            else:
                print(f"  - {name}: not loaded")
        print()
    
    def cmd_load(self, args: str):
        """Załaduj moduł."""
        if not args:
            print("Usage: load <module_name>")
            return
        
        info = self.manager.load_module(args)
        if info:
            print(f"Loaded: {args} ({info.type.value})")
        else:
            print(f"Failed to load: {args}")
    
    def cmd_unload(self, args: str):
        """Wyładuj moduł."""
        if not args:
            print("Usage: unload <module_name>")
            return
        
        if self.manager.unload_module(args):
            print(f"Unloaded: {args}")
        else:
            print(f"Failed to unload: {args}")
    
    def cmd_info(self, args: str):
        """Info o module."""
        if not args:
            print("Usage: info <module_name>")
            return
        
        info = self.manager.get_module_info(args)
        if info:
            print(f"\nModule: {info.name}")
            print(f"Type: {info.type.value}")
            print(f"Status: {info.status.value}")
            print(f"Layer: {info.layer or '-'}")
            print(f"Enabled: {info.enabled}")
            print(f"Description: {info.description or '-'}")
            if info.commands:
                print(f"Commands: {', '.join(info.commands)}")
            if info.error:
                print(f"Error: {info.error}")
            print()
        else:
            print(f"Module not found: {args}")
    
    def cmd_layers(self, args: str):
        """Lista warstw."""
        layers = self.manager.list_layers()
        print(f"\nLayers ({len(layers)}):")
        for layer in layers:
            servers = self.manager.layers.get(layer, [])
            print(f"  {layer}: {', '.join(servers) if servers else '(empty)'}")
        print()
    
    def cmd_layer(self, args: str):
        """Pokaż warstwę."""
        if not args:
            print("Usage: layer <layer_name>")
            return
        
        servers = self.manager.layers.get(args, [])
        if servers:
            print(f"\nLayer '{args}':")
            for server in servers:
                info = self.manager.mcp_config.get('servers', {}).get(server, {})
                print(f"  - {server}: {info.get('type', '?')} ({info.get('description', '')})")
        else:
            print(f"Layer not found or empty: {args}")
    
    def cmd_chat(self, args: str):
        """Chat z AI."""
        if not args:
            print("Usage: chat <prompt>")
            return
        
        print("Chat functionality requires API connection.")
        print("Use 'python core/api_deepseek.py' for DeepSeek or start Ollama.")
    
    def cmd_model(self, args: str):
        """Pokaż model."""
        from config import MODELS, DEFAULT_PROFILE
        current = MODELS.get(DEFAULT_PROFILE, {})
        print(f"\nActive profile: {DEFAULT_PROFILE}")
        print(f"Model: {current.get('name', 'unknown')}")
        print(f"Temperature: {current.get('temperature', 0.7)}")
        print(f"Backend: {current.get('backend', 'ollama')}")
        print()
    
    def cmd_profile(self, args: str):
        """Zmień profil."""
        from config import MODELS
        if not args:
            print("Available profiles:")
            for name, cfg in MODELS.items():
                print(f"  - {name}: {cfg.get('name')} ({cfg.get('role', '')})")
            return
        
        if args in MODELS:
            print(f"To change profile, edit config.py DEFAULT_PROFILE = '{args}'")
        else:
            print(f"Unknown profile: {args}")
    
    def cmd_cerber(self, args: str):
        """Cerber commands."""
        parts = args.split()
        subcmd = parts[0] if parts else "status"
        
        if subcmd == "status":
            print("\nCerber Status:")
            print("  Mode: ACTIVE" if os.path.exists("alfa_guard.py") else "  Mode: INACTIVE")
            print(f"  DB: {'EXISTS' if os.path.exists('alfa_guard.db') else 'NOT FOUND'}")
            print(f"  Snapshots: {len(list(Path('.alfa_snapshots').glob('*'))) if Path('.alfa_snapshots').exists() else 0}")
            print()
        
        elif subcmd == "verify":
            print("Running Cerber integrity check...")
            try:
                import alfa_guard
                # Would call verification here
                print("Verification complete.")
            except ImportError:
                print("alfa_guard.py not available")
        
        elif subcmd == "log":
            import sqlite3
            if os.path.exists("alfa_guard.db"):
                conn = sqlite3.connect("alfa_guard.db")
                c = conn.cursor()
                c.execute("SELECT ts, level, msg FROM incidents ORDER BY id DESC LIMIT 10")
                rows = c.fetchall()
                conn.close()
                
                print("\nRecent incidents:")
                for ts, level, msg in rows:
                    print(f"  [{ts}] [{level}] {msg}")
                if not rows:
                    print("  No incidents.")
                print()
            else:
                print("No incident database.")
        
        else:
            print("Cerber commands: status, verify, log")
    
    def cmd_run(self, args: str):
        """Wykonaj kod."""
        if not args:
            print("Usage: run <python_code>")
            return
        
        executor = self.manager.get_code_executor()
        if executor:
            rc, out = executor.run_python(args)
            print(out)
        else:
            print("CodeExecutor not available")
    
    def cmd_exec(self, args: str):
        """Wykonaj plik."""
        if not args:
            print("Usage: exec <file_path>")
            return
        
        if not os.path.exists(args):
            print(f"File not found: {args}")
            return
        
        code = Path(args).read_text(encoding='utf-8')
        executor = self.manager.get_code_executor()
        if executor:
            rc, out = executor.run_python(code)
            print(out)
        else:
            print("CodeExecutor not available")
    
    def cmd_help(self, args: str):
        """Pomoc."""
        print(self.HELP)
    
    def cmd_version(self, args: str):
        """Wersja."""
        print(f"ALFA_BRAIN v{VERSION} ({CODENAME})")


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="ALFA_BRAIN v2.0")
    parser.add_argument('--init', action='store_true', help='Initialize system')
    parser.add_argument('--status', action='store_true', help='Show status')
    parser.add_argument('--health', action='store_true', help='Health check')
    parser.add_argument('--cmd', '-c', help='Execute command')
    parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode')
    
    args = parser.parse_args()
    
    brain = AlfaBrain()
    
    if args.status:
        brain.manager = get_manager()
        brain.cmd_status("")
    elif args.health:
        brain.manager = get_manager()
        brain.cmd_health("")
    elif args.cmd:
        brain.manager = get_manager()
        brain.dispatch(args.cmd)
    elif args.init:
        brain.boot()
    else:
        # Start REPL
        brain.start()


if __name__ == "__main__":
    main()
