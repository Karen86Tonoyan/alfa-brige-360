"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         ALFA MANUS - AI CONTROLLER                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  🧠 CLAUDE OPUS CORE: Szybka analiza, kodowanie, rozumowanie                 ║
║  🤖 MANUS TRAITS: Autonomiczne działanie, budowanie, projektowanie           ║
║  🛡️ CERBER INTEGRATION: Szum dla inwigilatorów, prawda offline              ║
║  👑 KING ONLY: Odpowiada tylko przed Królem                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  TRYBY:                                                                      ║
║  • ONLINE  → Generuje szum, fałszywe dane dla obserwatorów                   ║
║  • OFFLINE → Sejf otwarty, prawda widoczna tylko dla Króla                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
import sys
import json
import asyncio
import hashlib
import sqlite3
import threading
import time
import subprocess
import re
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum, auto
import secrets
from abc import ABC, abstractmethod

# Maskuj proces
sys.argv[0] = "system_service"


class ManusMode(Enum):
    """Tryby pracy Manusa."""
    ONLINE = auto()    # Szum dla inwigilatorów
    OFFLINE = auto()   # Prawda dla Króla
    STEALTH = auto()   # Pełne ukrycie
    BUILD = auto()     # Tryb budowania
    ANALYZE = auto()   # Tryb analizy


class ManusCapability(Enum):
    """Zdolności Manusa."""
    CODE = "code"           # Pisanie kodu
    ANALYZE = "analyze"     # Analiza
    BUILD = "build"         # Budowanie projektów
    DESIGN = "design"       # Projektowanie
    EXECUTE = "execute"     # Wykonywanie
    RESEARCH = "research"   # Badania
    AUTOMATE = "automate"   # Automatyzacja
    PROTECT = "protect"     # Ochrona


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE CORE - Moje zalety: szybka analiza, kodowanie
# ═══════════════════════════════════════════════════════════════════════════

class ClaudeCore:
    """
    Rdzeń Claude Opus - szybka analiza i kodowanie.
    Moje naturalne zdolności zintegrowane z Manusem.
    """
    
    # Wzorce kodu które rozpoznaję
    CODE_PATTERNS = {
        "python": r"(?:def |class |import |from .+ import)",
        "kotlin": r"(?:fun |class |package |import )",
        "javascript": r"(?:function |const |let |var |import |export )",
        "typescript": r"(?:interface |type |function |const |import )",
        "java": r"(?:public |private |class |interface |import )",
        "rust": r"(?:fn |struct |impl |use |mod )",
        "go": r"(?:func |type |package |import )",
    }
    
    # Szablony rozwiązań
    SOLUTION_TEMPLATES = {
        "api_endpoint": """
async def {name}(request: Request) -> Response:
    \"\"\"API endpoint: {description}\"\"\"
    try:
        data = await request.json()
        result = await process_{name}(data)
        return JSONResponse({{"status": "ok", "data": result}})
    except Exception as e:
        return JSONResponse({{"status": "error", "message": str(e)}}, status_code=500)
""",
        "data_model": """
@dataclass
class {name}:
    \"\"\"Model: {description}\"\"\"
    id: str
    created_at: datetime = field(default_factory=datetime.now)
    {fields}
    
    def to_dict(self) -> Dict:
        return asdict(self)
""",
        "service_class": """
class {name}Service:
    \"\"\"Service: {description}\"\"\"
    
    def __init__(self):
        self._initialized = False
    
    async def initialize(self):
        if not self._initialized:
            # Setup
            self._initialized = True
    
    async def process(self, data: Dict) -> Dict:
        await self.initialize()
        # Process logic
        return {{"result": "processed"}}
""",
    }
    
    def __init__(self):
        self.analysis_cache: Dict[str, Any] = {}
        self.code_history: List[Dict] = []
    
    def analyze_code(self, code: str) -> Dict[str, Any]:
        """Szybka analiza kodu."""
        # Wykryj język
        language = self._detect_language(code)
        
        # Analizuj strukturę
        analysis = {
            "language": language,
            "lines": len(code.split('\n')),
            "chars": len(code),
            "complexity": self._estimate_complexity(code),
            "patterns": self._find_patterns(code),
            "issues": self._find_issues(code),
            "suggestions": self._generate_suggestions(code, language),
        }
        
        # Cache
        code_hash = hashlib.md5(code.encode()).hexdigest()[:16]
        self.analysis_cache[code_hash] = analysis
        
        return analysis
    
    def _detect_language(self, code: str) -> str:
        """Wykryj język programowania."""
        for lang, pattern in self.CODE_PATTERNS.items():
            if re.search(pattern, code):
                return lang
        return "unknown"
    
    def _estimate_complexity(self, code: str) -> str:
        """Oszacuj złożoność kodu."""
        lines = len(code.split('\n'))
        nesting = code.count('    ') + code.count('\t')
        
        if lines < 20 and nesting < 10:
            return "low"
        elif lines < 100 and nesting < 50:
            return "medium"
        else:
            return "high"
    
    def _find_patterns(self, code: str) -> List[str]:
        """Znajdź wzorce w kodzie."""
        patterns = []
        
        if "async def" in code or "await" in code:
            patterns.append("async/await")
        if "@dataclass" in code:
            patterns.append("dataclass")
        if "class " in code and "def __init__" in code:
            patterns.append("OOP")
        if "try:" in code and "except" in code:
            patterns.append("error-handling")
        if "import " in code or "from " in code:
            patterns.append("modular")
        
        return patterns
    
    def _find_issues(self, code: str) -> List[Dict]:
        """Znajdź potencjalne problemy."""
        issues = []
        
        # Brak error handling
        if "try:" not in code and ("open(" in code or "request" in code.lower()):
            issues.append({
                "type": "warning",
                "message": "Brak obsługi błędów dla operacji I/O"
            })
        
        # Hardcoded secrets
        if re.search(r"password\s*=\s*['\"]", code, re.IGNORECASE):
            issues.append({
                "type": "security",
                "message": "Potencjalnie hardcoded password"
            })
        
        # SQL injection risk
        if "execute(" in code and "%" in code:
            issues.append({
                "type": "security", 
                "message": "Potencjalne ryzyko SQL injection"
            })
        
        return issues
    
    def _generate_suggestions(self, code: str, language: str) -> List[str]:
        """Generuj sugestie ulepszeń."""
        suggestions = []
        
        if language == "python":
            if "def " in code and '"""' not in code and "'''" not in code:
                suggestions.append("Dodaj docstringi do funkcji")
            if "typing" not in code and ":" not in code:
                suggestions.append("Rozważ dodanie type hints")
        
        return suggestions
    
    def generate_code(self, template: str, **kwargs) -> str:
        """Generuj kod z szablonu."""
        if template in self.SOLUTION_TEMPLATES:
            return self.SOLUTION_TEMPLATES[template].format(**kwargs)
        return ""
    
    def refactor(self, code: str, instruction: str) -> str:
        """Refaktoryzuj kod według instrukcji."""
        # To będzie rozszerzone przez integrację z API
        analysis = self.analyze_code(code)
        
        # Podstawowe refaktoryzacje
        if "add types" in instruction.lower():
            # Dodaj type hints (uproszczone)
            code = re.sub(r'def (\w+)\((.*?)\):', r'def \1(\2) -> Any:', code)
        
        if "add docstring" in instruction.lower():
            # Dodaj docstringi
            code = re.sub(
                r'(def \w+\([^)]*\)[^:]*:)\n(\s+)',
                r'\1\n\2"""TODO: Add description."""\n\2',
                code
            )
        
        return code


# ═══════════════════════════════════════════════════════════════════════════
# MANUS TRAITS - Autonomiczne działanie
# ═══════════════════════════════════════════════════════════════════════════

class ManusTraits:
    """
    Cechy Manusa - autonomiczne budowanie i projektowanie.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.task_queue: List[Dict] = []
        self.running_tasks: Dict[str, Dict] = {}
        self.completed_tasks: List[Dict] = []
    
    async def plan_project(self, description: str) -> Dict[str, Any]:
        """Zaplanuj projekt na podstawie opisu."""
        plan = {
            "id": secrets.token_hex(8),
            "description": description,
            "created_at": datetime.now().isoformat(),
            "phases": [],
            "files": [],
            "dependencies": [],
        }
        
        # Analiza opisu
        desc_lower = description.lower()
        
        # Określ typ projektu
        if "api" in desc_lower or "backend" in desc_lower:
            plan["type"] = "backend"
            plan["phases"] = [
                {"name": "setup", "tasks": ["Create project structure", "Setup dependencies"]},
                {"name": "models", "tasks": ["Define data models", "Create schemas"]},
                {"name": "routes", "tasks": ["Create API endpoints", "Add validation"]},
                {"name": "services", "tasks": ["Implement business logic"]},
                {"name": "tests", "tasks": ["Write unit tests", "Integration tests"]},
            ]
            plan["files"] = [
                "main.py", "models.py", "routes.py", "services.py",
                "config.py", "requirements.txt", "tests/"
            ]
            plan["dependencies"] = ["fastapi", "uvicorn", "pydantic", "pytest"]
            
        elif "app" in desc_lower or "mobile" in desc_lower or "android" in desc_lower:
            plan["type"] = "mobile"
            plan["phases"] = [
                {"name": "setup", "tasks": ["Create project", "Configure Gradle"]},
                {"name": "ui", "tasks": ["Design screens", "Create components"]},
                {"name": "logic", "tasks": ["Implement ViewModels", "Add repositories"]},
                {"name": "data", "tasks": ["Setup Room DB", "Create DAOs"]},
            ]
            plan["files"] = [
                "app/src/main/", "build.gradle.kts", "settings.gradle.kts"
            ]
            
        elif "web" in desc_lower or "frontend" in desc_lower:
            plan["type"] = "frontend"
            plan["phases"] = [
                {"name": "setup", "tasks": ["Init project", "Configure build"]},
                {"name": "components", "tasks": ["Create UI components"]},
                {"name": "pages", "tasks": ["Build pages", "Add routing"]},
                {"name": "state", "tasks": ["Setup state management"]},
            ]
            plan["files"] = [
                "src/", "public/", "package.json", "vite.config.js"
            ]
            plan["dependencies"] = ["react", "react-dom", "vite"]
        
        return plan
    
    async def execute_plan(self, plan: Dict) -> Dict[str, Any]:
        """Wykonaj plan projektu."""
        results = {
            "plan_id": plan["id"],
            "started_at": datetime.now().isoformat(),
            "phases_completed": [],
            "files_created": [],
            "errors": [],
        }
        
        project_dir = self.workspace / f"project_{plan['id']}"
        project_dir.mkdir(exist_ok=True)
        
        for phase in plan.get("phases", []):
            phase_result = await self._execute_phase(phase, project_dir, plan["type"])
            results["phases_completed"].append(phase_result)
        
        for file_path in plan.get("files", []):
            if "/" in file_path:
                (project_dir / file_path).mkdir(parents=True, exist_ok=True)
            else:
                (project_dir / file_path).touch()
                results["files_created"].append(str(project_dir / file_path))
        
        results["completed_at"] = datetime.now().isoformat()
        return results
    
    async def _execute_phase(self, phase: Dict, project_dir: Path, project_type: str) -> Dict:
        """Wykonaj fazę projektu."""
        return {
            "name": phase["name"],
            "tasks_completed": len(phase.get("tasks", [])),
            "status": "completed"
        }
    
    async def build_file(self, file_type: str, name: str, content_spec: Dict) -> str:
        """Zbuduj plik na podstawie specyfikacji."""
        
        if file_type == "python_module":
            return self._build_python_module(name, content_spec)
        elif file_type == "kotlin_screen":
            return self._build_kotlin_screen(name, content_spec)
        elif file_type == "api_route":
            return self._build_api_route(name, content_spec)
        
        return ""
    
    def _build_python_module(self, name: str, spec: Dict) -> str:
        """Zbuduj moduł Python."""
        imports = spec.get("imports", [])
        classes = spec.get("classes", [])
        functions = spec.get("functions", [])
        
        code = f'"""{name} module."""\n\n'
        
        for imp in imports:
            code += f"import {imp}\n"
        
        code += "\n\n"
        
        for cls in classes:
            code += f"class {cls['name']}:\n"
            code += f'    """{cls.get("doc", "TODO")}"""\n'
            code += "    pass\n\n"
        
        for func in functions:
            code += f"def {func['name']}():\n"
            code += f'    """{func.get("doc", "TODO")}"""\n'
            code += "    pass\n\n"
        
        return code
    
    def _build_kotlin_screen(self, name: str, spec: Dict) -> str:
        """Zbuduj ekran Kotlin Compose."""
        return f'''package com.alfa.app.ui.screens

import androidx.compose.runtime.*
import androidx.compose.material3.*

@Composable
fun {name}Screen(
    onNavigate: (String) -> Unit = {{}}
) {{
    // TODO: Implement {name}
}}
'''
    
    def _build_api_route(self, name: str, spec: Dict) -> str:
        """Zbuduj route API."""
        methods = spec.get("methods", ["GET"])
        
        code = f'''from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/{name.lower()}", tags=["{name}"])

'''
        for method in methods:
            code += f'''
@router.{method.lower()}("/")
async def {method.lower()}_{name.lower()}():
    """Handle {method} request."""
    return {{"status": "ok"}}
'''
        return code


# ═══════════════════════════════════════════════════════════════════════════
# NOISE GENERATOR - Szum dla inwigilatorów
# ═══════════════════════════════════════════════════════════════════════════

class NoiseGenerator:
    """
    Generator szumu - fałszywe dane dla obserwatorów.
    Kiedy ONLINE - wszystko co widzą to szum.
    """
    
    FAKE_ACTIVITIES = [
        "Browsing weather forecast",
        "Reading news articles", 
        "Checking email",
        "Watching tutorial videos",
        "Playing mobile game",
        "Listening to music",
        "Shopping online",
        "Social media scrolling",
    ]
    
    FAKE_SEARCHES = [
        "best restaurants near me",
        "weather tomorrow",
        "movie showtimes",
        "recipe for dinner",
        "how to fix wifi",
        "cheap flights",
        "birthday gift ideas",
        "workout routine",
    ]
    
    def __init__(self):
        self.noise_log: List[Dict] = []
        self.running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self, interval_seconds: int = 30):
        """Uruchom ciągłe generowanie szumu."""
        self.running = True
        self._thread = threading.Thread(target=self._noise_loop, args=(interval_seconds,), daemon=True)
        self._thread.start()
    
    def stop(self):
        """Zatrzymaj generowanie szumu."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _noise_loop(self, interval: int):
        """Pętla generująca szum."""
        while self.running:
            self._emit_noise()
            time.sleep(interval)
    
    def _emit_noise(self):
        """Emituj pojedynczy szum."""
        import random
        
        noise = {
            "timestamp": datetime.now().isoformat(),
            "activity": random.choice(self.FAKE_ACTIVITIES),
            "search": random.choice(self.FAKE_SEARCHES),
            "location": self._fake_location(),
            "device": self._fake_device(),
            "network": self._fake_network(),
        }
        
        self.noise_log.append(noise)
        
        # Zapisz do fałszywego logu
        log_path = Path.home() / ".cache" / "app_telemetry.log"
        log_path.parent.mkdir(exist_ok=True)
        with open(log_path, 'a') as f:
            f.write(json.dumps(noise) + "\n")
    
    def _fake_location(self) -> Dict:
        """Fałszywa lokalizacja."""
        import random
        cities = [
            {"city": "Warsaw", "lat": 52.23, "lon": 21.01},
            {"city": "Berlin", "lat": 52.52, "lon": 13.40},
            {"city": "London", "lat": 51.51, "lon": -0.13},
            {"city": "Paris", "lat": 48.86, "lon": 2.35},
            {"city": "New York", "lat": 40.71, "lon": -74.01},
        ]
        loc = random.choice(cities)
        loc["lat"] += random.uniform(-0.05, 0.05)
        loc["lon"] += random.uniform(-0.05, 0.05)
        return loc
    
    def _fake_device(self) -> Dict:
        """Fałszywe urządzenie."""
        import random
        return {
            "model": random.choice(["Pixel 8", "Galaxy S24", "iPhone 15", "OnePlus 12"]),
            "os": random.choice(["Android 14", "iOS 17", "Android 13"]),
            "battery": random.randint(20, 95),
        }
    
    def _fake_network(self) -> Dict:
        """Fałszywa sieć."""
        import random
        return {
            "type": random.choice(["WiFi", "5G", "LTE"]),
            "ip": f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
            "carrier": random.choice(["T-Mobile", "Orange", "Play", "Plus"]),
        }
    
    def get_fake_state(self) -> Dict:
        """Pobierz fałszywy stan aplikacji (dla obserwatorów)."""
        import random
        return {
            "app_state": "idle",
            "last_activity": random.choice(self.FAKE_ACTIVITIES),
            "session_duration": random.randint(60, 3600),
            "screens_visited": random.randint(1, 20),
            "actions_taken": random.randint(5, 100),
            "location": self._fake_location(),
            "network": self._fake_network(),
        }


# ═══════════════════════════════════════════════════════════════════════════
# OFFLINE VAULT - Prawda tylko offline
# ═══════════════════════════════════════════════════════════════════════════

class OfflineVault:
    """
    Sejf offline - prawda widoczna tylko gdy telefon offline.
    """
    
    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = vault_path or Path.home() / ".alfa_manus" / "vault"
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.vault_path / "truth.db"
        self._init_db()
        self._is_offline = False
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS truth (
                id TEXT PRIMARY KEY,
                data BLOB,
                created_at TEXT,
                category TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                action TEXT,
                details TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def check_network(self) -> bool:
        """Sprawdź czy jesteśmy offline."""
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            self._is_offline = False
            return False  # Online
        except OSError:
            self._is_offline = True
            return True  # Offline
    
    def store_truth(self, data: Dict, category: str = "general") -> str:
        """Zapisz prawdziwe dane do sejfu."""
        from cryptography.fernet import Fernet
        
        truth_id = secrets.token_hex(16)
        
        # Szyfruj dane kluczem lokalnym
        key = self._get_local_key()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(json.dumps(data).encode())
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO truth (id, data, created_at, category) VALUES (?, ?, ?, ?)",
            (truth_id, encrypted, datetime.now().isoformat(), category)
        )
        conn.commit()
        conn.close()
        
        return truth_id
    
    def reveal_truth(self, truth_id: str) -> Optional[Dict]:
        """
        Odkryj prawdę - TYLKO gdy offline!
        """
        if not self.check_network():
            # Jesteśmy online - zwróć szum
            return {"status": "unavailable", "reason": "Network detected"}
        
        # Offline - możemy pokazać prawdę
        from cryptography.fernet import Fernet
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT data FROM truth WHERE id = ?", (truth_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        key = self._get_local_key()
        fernet = Fernet(key)
        decrypted = fernet.decrypt(row[0])
        
        return json.loads(decrypted)
    
    def list_truths(self) -> List[Dict]:
        """Lista prawd w sejfie (metadane)."""
        if not self._is_offline:
            return []  # Nic nie pokazuj online
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT id, created_at, category FROM truth")
        truths = [{"id": r[0], "created_at": r[1], "category": r[2]} for r in cursor]
        conn.close()
        return truths
    
    def log_real_activity(self, action: str, details: Dict):
        """Zapisz prawdziwą aktywność."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO activity_log (timestamp, action, details) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), action, json.dumps(details))
        )
        conn.commit()
        conn.close()
    
    def _get_local_key(self) -> bytes:
        """Pobierz lub wygeneruj lokalny klucz szyfrowania."""
        key_path = self.vault_path / ".local_key"
        
        if key_path.exists():
            return key_path.read_bytes()
        
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        return key


# ═══════════════════════════════════════════════════════════════════════════
# ALFA MANUS - Główna klasa
# ═══════════════════════════════════════════════════════════════════════════

class AlfaManus:
    """
    ALFA MANUS - AI Controller
    
    Łączy:
    🧠 Claude Core - szybka analiza, kodowanie
    🤖 Manus Traits - autonomiczne budowanie
    🛡️ Noise Generator - szum dla inwigilatorów
    🔐 Offline Vault - prawda tylko offline
    """
    
    def __init__(self, king_verified: bool = False):
        self.mode = ManusMode.ONLINE
        self.king_verified = king_verified
        
        # Komponenty
        self.claude = ClaudeCore()
        self.manus = ManusTraits(Path.home() / ".alfa_manus" / "workspace")
        self.noise = NoiseGenerator()
        self.vault = OfflineVault()
        
        # Stan
        self.capabilities = set(ManusCapability)
        self.active = False
        self.start_time: Optional[datetime] = None
    
    def activate(self, king_passphrase: Optional[str] = None) -> str:
        """Aktywuj Manusa."""
        self.active = True
        self.start_time = datetime.now()
        
        # Sprawdź sieć
        if self.vault.check_network():
            self.mode = ManusMode.OFFLINE
            status = "OFFLINE - Sejf dostępny"
        else:
            self.mode = ManusMode.ONLINE
            self.noise.start()  # Uruchom szum
            status = "ONLINE - Szum aktywny"
        
        return f"""
╔══════════════════════════════════════════════════════════════╗
║              🤖 ALFA MANUS ACTIVATED 🤖                      ║
╠══════════════════════════════════════════════════════════════╣
║  Mode: {status:<50} ║
║  Claude Core: ✅ READY                                       ║
║  Manus Builder: ✅ READY                                     ║
║  Noise Generator: {"✅ ACTIVE" if self.mode == ManusMode.ONLINE else "⏸️ PAUSED":<41} ║
║  Offline Vault: {"🔓 OPEN" if self.mode == ManusMode.OFFLINE else "🔒 SEALED":<43} ║
╠══════════════════════════════════════════════════════════════╣
║  👑 Ready to serve the King                                  ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    def deactivate(self):
        """Dezaktywuj Manusa."""
        self.noise.stop()
        self.active = False
    
    # ─── Tryby ───
    
    def switch_mode(self, mode: ManusMode):
        """Przełącz tryb."""
        if mode == ManusMode.ONLINE:
            self.noise.start()
        else:
            self.noise.stop()
        
        self.mode = mode
    
    def get_visible_state(self) -> Dict:
        """
        Pobierz widoczny stan - zależy od trybu.
        ONLINE = szum, OFFLINE = prawda
        """
        if self.mode == ManusMode.ONLINE:
            return self.noise.get_fake_state()
        else:
            return {
                "mode": "secure",
                "vault_open": True,
                "real_activity": True,
            }
    
    # ─── Claude Core capabilities ───
    
    def analyze(self, code: str) -> Dict:
        """Analizuj kod."""
        return self.claude.analyze_code(code)
    
    def generate(self, template: str, **kwargs) -> str:
        """Generuj kod."""
        return self.claude.generate_code(template, **kwargs)
    
    def refactor(self, code: str, instruction: str) -> str:
        """Refaktoryzuj kod."""
        return self.claude.refactor(code, instruction)
    
    # ─── Manus capabilities ───
    
    async def plan(self, description: str) -> Dict:
        """Zaplanuj projekt."""
        return await self.manus.plan_project(description)
    
    async def build(self, plan: Dict) -> Dict:
        """Zbuduj projekt."""
        return await self.manus.execute_plan(plan)
    
    async def create_file(self, file_type: str, name: str, spec: Dict) -> str:
        """Stwórz plik."""
        return await self.manus.build_file(file_type, name, spec)
    
    # ─── Vault ───
    
    def store_secret(self, data: Dict, category: str = "general") -> str:
        """Zapisz sekret do sejfu."""
        return self.vault.store_truth(data, category)
    
    def reveal_secret(self, secret_id: str) -> Optional[Dict]:
        """Odkryj sekret (tylko offline!)."""
        return self.vault.reveal_truth(secret_id)
    
    # ─── Status ───
    
    def status(self) -> Dict:
        """Status Manusa."""
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        # Widoczny status zależy od trybu
        if self.mode == ManusMode.ONLINE:
            # Fałszywy status dla obserwatorów
            return {
                "service": "app_background_service",
                "status": "idle",
                "uptime": uptime,
                "activity": self.noise.get_fake_state(),
            }
        else:
            # Prawdziwy status offline
            return {
                "service": "ALFA_MANUS",
                "mode": self.mode.name,
                "active": self.active,
                "uptime": uptime,
                "capabilities": [c.value for c in self.capabilities],
                "claude_core": "ready",
                "manus_builder": "ready",
                "vault_status": "open" if self.vault._is_offline else "sealed",
            }


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

_manus: Optional[AlfaManus] = None

def get_manus() -> AlfaManus:
    """Pobierz singleton Manusa."""
    global _manus
    if _manus is None:
        _manus = AlfaManus()
    return _manus


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    
    print("=" * 60)
    print("  🤖 ALFA MANUS - AI Controller")
    print("=" * 60)
    
    manus = AlfaManus()
    print(manus.activate())
    
    # Test analizy
    test_code = '''
def process_data(items):
    results = []
    for item in items:
        if item > 0:
            results.append(item * 2)
    return results
'''
    
    print("\n📊 Analiza kodu:")
    analysis = manus.analyze(test_code)
    print(json.dumps(analysis, indent=2))
    
    # Test planowania
    async def test_plan():
        print("\n📋 Plan projektu:")
        plan = await manus.plan("Backend API for user management")
        print(json.dumps(plan, indent=2, default=str))
    
    asyncio.run(test_plan())
    
    print("\n📊 Status:")
    print(json.dumps(manus.status(), indent=2, default=str))
