#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# ALFA_MASTER v2.0 — CENTRALNY KONTROLER CAŁEGO EKOSYSTEMU
# ═══════════════════════════════════════════════════════════════════════════════
"""
ALFA MASTER - Jeden punkt wejścia do całego systemu ALFA.

Kontroluje:
    - alfa_brain     → Mózg (CLI/REPL, routing)
    - alfa_cloud     → Chmura (API, AI, dashboard)
    - alfa_keyvault  → Kryptografia (Rust, PQC)
    - alfa_photos_vault → Vault zdjęć (Rust, Android)
    - ALFA_Mail      → Poczta (Python core + Android)
    - core/          → Wspólne moduły (cerber, event_bus, mcp)
    - modules/       → Moduły dodatkowe (mirror, watchdog)
    - plugins/       → Pluginy (voice, bridge, mail, delta)

Usage:
    python alfa_master.py                  # Uruchom BRAIN (domyślnie)
    python alfa_master.py --status         # Status całego systemu
    python alfa_master.py --start-all      # Uruchom wszystkie serwisy
    python alfa_master.py --cloud          # Uruchom tylko ALFA Cloud
    python alfa_master.py --mail           # Uruchom tylko ALFA Mail

Author: ALFA System / Karen86Tonoyan
Version: 2.0.0
"""

import sys
import os
import argparse
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════

ALFA_ROOT = Path(__file__).parent.resolve()

# Dodaj wszystkie moduły do path
sys.path.insert(0, str(ALFA_ROOT))
sys.path.insert(0, str(ALFA_ROOT / "core"))
sys.path.insert(0, str(ALFA_ROOT / "modules"))
sys.path.insert(0, str(ALFA_ROOT / "plugins"))
sys.path.insert(0, str(ALFA_ROOT / "alfa_brain"))
sys.path.insert(0, str(ALFA_ROOT / "alfa_cloud"))

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [ALFA] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
LOG = logging.getLogger("alfa.master")

# ═══════════════════════════════════════════════════════════════════════════════
# ECOSYSTEM DEFINITION
# ═══════════════════════════════════════════════════════════════════════════════

class ModuleType(Enum):
    PYTHON_SERVICE = "python_service"
    PYTHON_MODULE = "python_module"
    RUST_LIBRARY = "rust_library"
    RUST_ANDROID = "rust_android"
    ANDROID_APP = "android_app"
    HYBRID = "hybrid"


@dataclass
class AlfaModule:
    """Definicja modułu w ekosystemie ALFA."""
    name: str
    path: Path
    module_type: ModuleType
    enabled: bool = True
    auto_start: bool = False
    entry_point: Optional[str] = None
    description: str = ""
    dependencies: List[str] = None
    
    def __post_init__(self):
        self.dependencies = self.dependencies or []


# ═══════════════════════════════════════════════════════════════════════════════
# ECOSYSTEM REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

ECOSYSTEM: Dict[str, AlfaModule] = {
    # === BRAIN (Mózg) ===
    "alfa_brain": AlfaModule(
        name="alfa_brain",
        path=ALFA_ROOT / "alfa_brain",
        module_type=ModuleType.PYTHON_SERVICE,
        enabled=True,
        auto_start=True,
        entry_point="brain.py",
        description="Mózg systemu - CLI/REPL, routing komend",
        dependencies=["core"]
    ),
    
    # === CLOUD (Chmura) ===
    "alfa_cloud": AlfaModule(
        name="alfa_cloud",
        path=ALFA_ROOT / "alfa_cloud",
        module_type=ModuleType.PYTHON_SERVICE,
        enabled=True,
        auto_start=False,
        entry_point="run_cloud.py",
        description="Private AI Cloud - API, dashboard, AI agents",
        dependencies=["core", "alfa_brain"]
    ),
    
    # === KEYVAULT (Kryptografia) ===
    "alfa_keyvault": AlfaModule(
        name="alfa_keyvault",
        path=ALFA_ROOT / "alfa_keyvault",
        module_type=ModuleType.RUST_LIBRARY,
        enabled=True,
        auto_start=False,
        description="Post-Quantum Cryptography vault (Rust)",
        dependencies=[]
    ),
    
    # === PHOTOS VAULT (Zdjęcia) ===
    "alfa_photos_vault": AlfaModule(
        name="alfa_photos_vault",
        path=ALFA_ROOT / "alfa_photos_vault",
        module_type=ModuleType.RUST_ANDROID,
        enabled=True,
        auto_start=False,
        description="Encrypted photo vault (Rust + Android)",
        dependencies=["alfa_keyvault"]
    ),
    
    # === MAIL (Poczta) ===
    "alfa_mail": AlfaModule(
        name="alfa_mail",
        path=ALFA_ROOT / "ALFA_Mail",
        module_type=ModuleType.HYBRID,
        enabled=True,
        auto_start=False,
        entry_point="core/imap_engine.py",
        description="Secure email client (Python core + Android)",
        dependencies=["core", "alfa_keyvault"]
    ),
    
    # === CORE (Wspólne moduły) ===
    "core": AlfaModule(
        name="core",
        path=ALFA_ROOT / "core",
        module_type=ModuleType.PYTHON_MODULE,
        enabled=True,
        auto_start=True,
        description="Wspólne moduły: cerber, event_bus, mcp_dispatcher",
        dependencies=[]
    ),
    
    # === MODULES (Dodatkowe moduły) ===
    "modules": AlfaModule(
        name="modules",
        path=ALFA_ROOT / "modules",
        module_type=ModuleType.PYTHON_MODULE,
        enabled=True,
        auto_start=False,
        description="Dodatkowe moduły: mirror, watchdog, forensics",
        dependencies=["core"]
    ),
    
    # === PLUGINS (Pluginy) ===
    "plugins": AlfaModule(
        name="plugins",
        path=ALFA_ROOT / "plugins",
        module_type=ModuleType.PYTHON_MODULE,
        enabled=True,
        auto_start=False,
        description="Pluginy: voice, bridge, mail, delta",
        dependencies=["core"]
    ),
}

# ═══════════════════════════════════════════════════════════════════════════════
# ALFA MASTER
# ═══════════════════════════════════════════════════════════════════════════════

class AlfaMaster:
    """
    ALFA MASTER - Centralny kontroler całego ekosystemu.
    
    Zarządza wszystkimi modułami, uruchamia serwisy,
    monitoruje stan i koordynuje komunikację.
    """
    
    BANNER = r"""
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                                                                       ║
    ║     █████╗ ██╗     ███████╗ █████╗     ███╗   ███╗ █████╗ ███████╗   ║
    ║    ██╔══██╗██║     ██╔════╝██╔══██╗    ████╗ ████║██╔══██╗██╔════╝   ║
    ║    ███████║██║     █████╗  ███████║    ██╔████╔██║███████║███████╗   ║
    ║    ██╔══██║██║     ██╔══╝  ██╔══██║    ██║╚██╔╝██║██╔══██║╚════██║   ║
    ║    ██║  ██║███████╗██║     ██║  ██║    ██║ ╚═╝ ██║██║  ██║███████║   ║
    ║    ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝    ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ║
    ║                                                                       ║
    ║              ALFA MASTER v2.0 :: UNIFIED ECOSYSTEM                    ║
    ║                    The King's Private Cloud                           ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """
    
    def __init__(self):
        self.ecosystem = ECOSYSTEM
        self.running_services: Dict[str, subprocess.Popen] = {}
        self._initialized = False
    
    def show_banner(self):
        print(self.BANNER)
    
    def status(self) -> Dict[str, Any]:
        """Pobierz status całego ekosystemu."""
        status = {
            "alfa_root": str(ALFA_ROOT),
            "modules": {}
        }
        
        for name, module in self.ecosystem.items():
            exists = module.path.exists()
            running = name in self.running_services
            
            status["modules"][name] = {
                "path": str(module.path),
                "type": module.module_type.value,
                "enabled": module.enabled,
                "exists": exists,
                "running": running,
                "description": module.description,
                "dependencies": module.dependencies
            }
        
        return status
    
    def print_status(self):
        """Wyświetl status w czytelnej formie."""
        status = self.status()
        
        print("\n" + "═" * 70)
        print("                    ALFA ECOSYSTEM STATUS")
        print("═" * 70)
        print(f"  Root: {status['alfa_root']}")
        print("═" * 70)
        
        for name, info in status["modules"].items():
            icon = "✓" if info["exists"] else "✗"
            running = "🟢" if info["running"] else "⚪"
            enabled = "ON" if info["enabled"] else "OFF"
            
            print(f"\n  {running} {icon} {name.upper()}")
            print(f"      Type: {info['type']}")
            print(f"      Status: {enabled}")
            print(f"      Path: {info['path']}")
            print(f"      Description: {info['description']}")
            if info["dependencies"]:
                print(f"      Dependencies: {', '.join(info['dependencies'])}")
        
        print("\n" + "═" * 70)
    
    def start_module(self, name: str) -> bool:
        """Uruchom pojedynczy moduł."""
        if name not in self.ecosystem:
            LOG.error(f"Unknown module: {name}")
            return False
        
        module = self.ecosystem[name]
        
        if not module.enabled:
            LOG.warning(f"Module {name} is disabled")
            return False
        
        if not module.path.exists():
            LOG.error(f"Module path does not exist: {module.path}")
            return False
        
        if module.module_type == ModuleType.PYTHON_SERVICE and module.entry_point:
            entry = module.path / module.entry_point
            if entry.exists():
                LOG.info(f"Starting {name}...")
                process = subprocess.Popen(
                    [sys.executable, str(entry)],
                    cwd=str(module.path)
                )
                self.running_services[name] = process
                LOG.info(f"Started {name} (PID: {process.pid})")
                return True
        
        elif module.module_type == ModuleType.RUST_LIBRARY:
            LOG.info(f"Building Rust library: {name}")
            result = subprocess.run(
                ["cargo", "build", "--release"],
                cwd=str(module.path),
                capture_output=True
            )
            return result.returncode == 0
        
        return False
    
    def stop_module(self, name: str) -> bool:
        """Zatrzymaj moduł."""
        if name in self.running_services:
            process = self.running_services[name]
            process.terminate()
            process.wait(timeout=5)
            del self.running_services[name]
            LOG.info(f"Stopped {name}")
            return True
        return False
    
    def start_brain(self):
        """Uruchom ALFA Brain jako główny interfejs."""
        brain_path = ALFA_ROOT / "alfa_brain" / "brain.py"
        if brain_path.exists():
            LOG.info("Starting ALFA Brain...")
            os.chdir(str(ALFA_ROOT / "alfa_brain"))
            exec(open(brain_path).read())
        else:
            LOG.error("ALFA Brain not found!")
    
    def start_cloud(self):
        """Uruchom ALFA Cloud."""
        return self.start_module("alfa_cloud")
    
    def start_all(self):
        """Uruchom wszystkie moduły z auto_start=True."""
        for name, module in self.ecosystem.items():
            if module.auto_start and module.enabled:
                self.start_module(name)
    
    def stop_all(self):
        """Zatrzymaj wszystkie uruchomione serwisy."""
        for name in list(self.running_services.keys()):
            self.stop_module(name)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="ALFA MASTER - Centralny kontroler ekosystemu ALFA"
    )
    parser.add_argument("--status", action="store_true", help="Status całego systemu")
    parser.add_argument("--start-all", action="store_true", help="Uruchom wszystkie serwisy")
    parser.add_argument("--cloud", action="store_true", help="Uruchom ALFA Cloud")
    parser.add_argument("--mail", action="store_true", help="Uruchom ALFA Mail")
    parser.add_argument("--stop-all", action="store_true", help="Zatrzymaj wszystkie")
    
    args = parser.parse_args()
    
    master = AlfaMaster()
    master.show_banner()
    
    if args.status:
        master.print_status()
    elif args.start_all:
        master.start_all()
    elif args.cloud:
        master.start_cloud()
    elif args.mail:
        master.start_module("alfa_mail")
    elif args.stop_all:
        master.stop_all()
    else:
        # Domyślnie uruchom BRAIN
        master.start_brain()


if __name__ == "__main__":
    main()
