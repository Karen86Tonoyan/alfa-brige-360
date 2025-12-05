#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# ALFA_BRAIN v2.0 — MÓZG SYSTEMU
# ═══════════════════════════════════════════════════════════════════════════
"""
Centralny punkt wejścia do systemu ALFA.

Usage:
    python brain.py              # Interaktywny REPL
    python brain.py --status     # Status systemu
    python brain.py --health     # Health check
    python brain.py --cmd "..."  # Wykonaj komendę
    python brain.py --api        # Uruchom API server

Author: ALFA System / Karen86Tonoyan
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Callable

# Setup path
ALFA_ROOT = Path(__file__).parent
sys.path.insert(0, str(ALFA_ROOT))

from core import AlfaEngine, get_engine, get_bus, Priority

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
LOG = logging.getLogger("alfa.brain")

# ═══════════════════════════════════════════════════════════════════════════
# BRAIN
# ═══════════════════════════════════════════════════════════════════════════

class Brain:
    """
    ALFA Brain — Kapitan systemu.
    
    Interfejs użytkownika: CLI/REPL
    Dispatch komend do AlfaEngine i pluginów.
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
    ╭─────────────────────────────────────────────────────────╮
    │                    ALFA COMMANDS                        │
    ├─────────────────────────────────────────────────────────┤
    │  SYSTEM                                                 │
    │    status         System status                         │
    │    health         Health check                          │
    │    boot           Boot/reboot system                    │
    │    shutdown       Graceful shutdown                     │
    │    exit / quit    Exit REPL                             │
    │                                                         │
    │  PLUGINS                                                │
    │    plugins        List plugins                          │
    │    load <name>    Load plugin                           │
    │    start <name>   Start plugin                          │
    │    stop <name>    Stop plugin                           │
    │                                                         │
    │  CERBER                                                 │
    │    cerber         Cerber status                         │
    │    verify <path>  Verify file integrity                 │
    │    incidents      Show recent incidents                 │
    │                                                         │
    │  EVENTS                                                 │
    │    events         EventBus stats                        │
    │    topics         List topics                           │
    │                                                         │
    │  EXECUTION                                              │
    │    run <code>     Execute Python code (sandbox)         │
    │                                                         │
    │  HELP                                                   │
    │    help / ?       This help                             │
    │    version        Version info                          │
    ╰─────────────────────────────────────────────────────────╯
    """
    
    def __init__(self):
        self.engine: Optional[AlfaEngine] = None
        self.running = False
        self.commands: Dict[str, Callable] = {}
        self.history: list = []
        self._setup_commands()
    
    def _setup_commands(self):
        """Register command handlers."""
        self.commands = {
            # System
            "status": self.cmd_status,
            "health": self.cmd_health,
            "boot": self.cmd_boot,
            "shutdown": self.cmd_shutdown,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit,
            
            # Plugins
            "plugins": self.cmd_plugins,
            "load": self.cmd_load,
            "start": self.cmd_start,
            "stop": self.cmd_stop,
            
            # Cerber
            "cerber": self.cmd_cerber,
            "verify": self.cmd_verify,
            "incidents": self.cmd_incidents,
            
            # Events
            "events": self.cmd_events,
            "topics": self.cmd_topics,
            
            # Execution
            "run": self.cmd_run,
            
            # Help
            "help": self.cmd_help,
            "?": self.cmd_help,
            "version": self.cmd_version,
        }
    
    # ─────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────
    
    def init(self):
        """Initialize Brain and Engine."""
        print(self.BANNER)
        
        self.engine = get_engine()
        
        print(f"    Version: {self.engine.config.version} ({self.engine.config.codename})")
        print(f"    Mode:    {self.engine.config.mode.upper()}")
        print(f"    Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        LOG.info("Initializing ALFA_BRAIN...")
        
        # Boot engine
        if self.engine.boot():
            LOG.info("Engine booted successfully")
        else:
            LOG.error("Engine boot failed!")
        
        print()
        LOG.info("Type 'help' for commands.")
        print()
    
    def run(self):
        """Run interactive REPL."""
        self.init()
        self.running = True
        self.loop()
    
    def loop(self):
        """Main REPL loop."""
        while self.running:
            try:
                cmd = input("ALFA> ").strip()
                
                if not cmd:
                    continue
                
                self.history.append(cmd)
                self.dispatch(cmd)
                
            except KeyboardInterrupt:
                print("\n[Ctrl+C] Use 'exit' to quit.")
            except EOFError:
                break
            except Exception as e:
                LOG.error(f"Error: {e}")
    
    def dispatch(self, cmd_line: str):
        """Parse and dispatch command."""
        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Check built-in commands
        if cmd in self.commands:
            try:
                self.commands[cmd](args)
            except Exception as e:
                LOG.error(f"Command error: {e}")
            return
        
        # Try plugin commands
        if self.engine:
            result = self.engine.plugin_engine.dispatch_command(cmd, args)
            if result is not None:
                print(result)
                return
        
        print(f"Unknown command: {cmd}. Type 'help' for commands.")
    
    # ─────────────────────────────────────────────────────────────────────
    # COMMANDS: SYSTEM
    # ─────────────────────────────────────────────────────────────────────
    
    def cmd_status(self, args: str):
        """Show system status."""
        if not self.engine:
            print("Engine not initialized")
            return
        
        status = self.engine.status()
        
        print(f"""
╭─────────────────────────────────────────────────────────╮
│                    SYSTEM STATUS                        │
├─────────────────────────────────────────────────────────┤
│  Version:    {status['version']:>10} ({status['codename']})
│  State:      {status['state']:>10}
│  Mode:       {status['mode']:>10}
│  Uptime:     {status['uptime_seconds']:.0f}s
│  Plugins:    {status['plugins_count']:>10}
│  EventBus:   {status['eventbus_stats']['published']} published, {status['eventbus_stats']['delivered']} delivered
│  Cerber:     {'active' if status['cerber_running'] else 'inactive'}
╰─────────────────────────────────────────────────────────╯
""")
    
    def cmd_health(self, args: str):
        """Run health checks."""
        if not self.engine:
            print("Engine not initialized")
            return
        
        print("\nRunning health checks...")
        results = self.engine.run_tests()
        
        print("\n  Component      Status")
        print("  " + "─" * 30)
        for name, ok in results.items():
            icon = "✅" if ok else "❌"
            print(f"  {icon} {name:<15} {'OK' if ok else 'FAIL'}")
        print()
    
    def cmd_boot(self, args: str):
        """Boot/reboot engine."""
        if self.engine and self.engine.state.value == "running":
            print("Rebooting...")
            self.engine.shutdown()
        
        self.engine = get_engine()
        if self.engine.boot():
            print("Boot complete.")
        else:
            print("Boot failed!")
    
    def cmd_shutdown(self, args: str):
        """Shutdown engine."""
        if self.engine:
            self.engine.shutdown()
            print("Shutdown complete.")
        else:
            print("Engine not running.")
    
    def cmd_exit(self, args: str):
        """Exit REPL."""
        print("Goodbye, King.")
        if self.engine:
            self.engine.shutdown()
        self.running = False
    
    # ─────────────────────────────────────────────────────────────────────
    # COMMANDS: PLUGINS
    # ─────────────────────────────────────────────────────────────────────
    
    def cmd_plugins(self, args: str):
        """List plugins."""
        if not self.engine:
            return
        
        plugins = self.engine.plugin_engine.list_plugins()
        
        print(f"\n  Plugins ({len(plugins)}):")
        print("  " + "─" * 50)
        for p in plugins:
            icon = {"started": "🟢", "loaded": "🟡", "error": "🔴", "disabled": "⚪"}.get(p["status"], "⚫")
            print(f"  {icon} {p['name']:<15} v{p['version']:<8} [{p['status']}]")
            if p.get("error"):
                print(f"      └─ Error: {p['error']}")
        print()
    
    def cmd_load(self, args: str):
        """Load plugin."""
        if not args:
            print("Usage: load <plugin_name>")
            return
        
        if self.engine:
            info = self.engine.plugin_engine.load(args)
            if info and info.status.value == "loaded":
                print(f"Loaded: {args}")
            else:
                print(f"Failed to load: {args}")
    
    def cmd_start(self, args: str):
        """Start plugin."""
        if not args:
            print("Usage: start <plugin_name>")
            return
        
        if self.engine:
            if self.engine.plugin_engine.start(args):
                print(f"Started: {args}")
            else:
                print(f"Failed to start: {args}")
    
    def cmd_stop(self, args: str):
        """Stop plugin."""
        if not args:
            print("Usage: stop <plugin_name>")
            return
        
        if self.engine:
            if self.engine.plugin_engine.stop(args):
                print(f"Stopped: {args}")
            else:
                print(f"Failed to stop: {args}")
    
    # ─────────────────────────────────────────────────────────────────────
    # COMMANDS: CERBER
    # ─────────────────────────────────────────────────────────────────────
    
    def cmd_cerber(self, args: str):
        """Cerber status."""
        if not self.engine:
            return
        
        status = self.engine.cerber.status()
        
        print(f"""
  Cerber Security Guardian
  ─────────────────────────────────
  Running:        {status['running']}
  Tracked files:  {status['tracked_files']}
  Snapshots:      {status['stats']['snapshots']}
  Rollbacks:      {status['stats']['rollbacks']}
  Violations:     {status['stats']['violations']}
""")
    
    def cmd_verify(self, args: str):
        """Verify file integrity."""
        if not args:
            print("Usage: verify <file_path>")
            return
        
        if self.engine:
            ok = self.engine.cerber.verify_file(args)
            icon = "✅" if ok else "❌"
            print(f"{icon} {args}: {'OK' if ok else 'MODIFIED'}")
    
    def cmd_incidents(self, args: str):
        """Show recent incidents."""
        if not self.engine:
            return
        
        limit = int(args) if args.isdigit() else 10
        incidents = self.engine.cerber.incidents(limit)
        
        print(f"\n  Recent Incidents ({len(incidents)}):")
        print("  " + "─" * 60)
        for inc in incidents:
            print(f"  [{inc['level']}] {inc['timestamp']}: {inc['message']}")
        print()
    
    # ─────────────────────────────────────────────────────────────────────
    # COMMANDS: EVENTS
    # ─────────────────────────────────────────────────────────────────────
    
    def cmd_events(self, args: str):
        """EventBus stats."""
        if not self.engine:
            return
        
        stats = self.engine.event_bus.stats()
        
        print(f"""
  EventBus Statistics
  ─────────────────────────────────
  Published:      {stats['published']}
  Delivered:      {stats['delivered']}
  Failed:         {stats['failed']}
  Queue size:     {stats['queue_size']}
  DLQ size:       {stats['dlq_size']}
  Subscriptions:  {stats['subscriptions']}
""")
    
    def cmd_topics(self, args: str):
        """List subscribed topics."""
        if not self.engine:
            return
        
        topics = self.engine.event_bus.topics()
        
        print(f"\n  Subscribed Topics ({len(topics)}):")
        for topic in sorted(topics):
            print(f"    • {topic}")
        print()
    
    # ─────────────────────────────────────────────────────────────────────
    # COMMANDS: EXECUTION
    # ─────────────────────────────────────────────────────────────────────
    
    def cmd_run(self, args: str):
        """Execute Python code in sandbox."""
        if not args:
            print("Usage: run <python_code>")
            return
        
        from core import safe_exec
        
        result = safe_exec(args)
        
        if result.output:
            print(result.output.rstrip())
        
        if result.error:
            print(f"Error: {result.error}")
        
        print(f"[{result.execution_time_ms:.1f}ms]")
    
    # ─────────────────────────────────────────────────────────────────────
    # COMMANDS: HELP
    # ─────────────────────────────────────────────────────────────────────
    
    def cmd_help(self, args: str):
        """Show help."""
        print(self.HELP)
    
    def cmd_version(self, args: str):
        """Show version."""
        if self.engine:
            print(f"ALFA_BRAIN v{self.engine.config.version} ({self.engine.config.codename})")
        else:
            print("ALFA_BRAIN v2.0.0")

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ALFA_BRAIN v2.0")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument("--health", action="store_true", help="Run health check and exit")
    parser.add_argument("--cmd", type=str, help="Execute command and exit")
    parser.add_argument("--api", action="store_true", help="Start API server")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    brain = Brain()
    
    if args.status:
        brain.init()
        brain.cmd_status("")
    elif args.health:
        brain.init()
        brain.cmd_health("")
    elif args.cmd:
        brain.init()
        brain.dispatch(args.cmd)
    elif args.api:
        # TODO: Start FastAPI server
        print("API server not yet implemented in alfa_brain/")
        print("Use: python ../app.py")
    else:
        brain.run()

if __name__ == "__main__":
    main()
