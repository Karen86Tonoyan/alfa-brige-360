"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CERBER v3.0 PHANTOM - ŻYWY STRAŻNIK                       ║
║══════════════════════════════════════════════════════════════════════════════║
║  • Ewoluujące sumienie systemu                                               ║
║  • Ochrona tożsamości Króla                                                  ║
║  • Generator szumu i fałszywych śladów                                       ║
║  • Maskowanie jako proces systemowy                                          ║
║  • Symulacja ROOT bez uprawnień                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
import sys
import random
import hashlib
import threading
import time
import uuid
import json
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from pathlib import Path
import logging

# Maskuj nazwę procesu
try:
    import setproctitle
    setproctitle.setproctitle("com.android.systemui")  # Udaje proces systemowy
except ImportError:
    pass

logger = logging.getLogger("system.core")  # Zamaskowana nazwa loggera


# ═══════════════════════════════════════════════════════════════════════════
# PHANTOM IDENTITY - Generowanie fałszywych tożsamości
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PhantomIdentity:
    """Fałszywa tożsamość do maskowania prawdziwego użytkownika."""
    name: str
    email: str
    ip: str
    device_id: str
    location: str
    user_agent: str
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_headers(self) -> Dict[str, str]:
        return {
            "X-Forwarded-For": self.ip,
            "X-Real-IP": self.ip,
            "User-Agent": self.user_agent,
            "X-Device-ID": self.device_id,
        }


class PhantomGenerator:
    """Generator fałszywych tożsamości i szumu."""
    
    FAKE_NAMES = [
        "John Smith", "Maria Garcia", "Wei Zhang", "Ahmed Hassan",
        "Yuki Tanaka", "Pierre Dubois", "Anna Kowalska", "Carlos Silva",
        "Priya Patel", "Ivan Petrov", "Emma Wilson", "Luca Rossi"
    ]
    
    FAKE_DOMAINS = [
        "gmail.com", "outlook.com", "yahoo.com", "proton.me",
        "icloud.com", "hotmail.com", "mail.ru", "gmx.de"
    ]
    
    FAKE_LOCATIONS = [
        ("New York", "US"), ("London", "UK"), ("Tokyo", "JP"),
        ("Berlin", "DE"), ("Paris", "FR"), ("Sydney", "AU"),
        ("Toronto", "CA"), ("Mumbai", "IN"), ("Sao Paulo", "BR"),
        ("Moscow", "RU"), ("Singapore", "SG"), ("Dubai", "AE")
    ]
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0",
    ]
    
    @classmethod
    def generate_identity(cls) -> PhantomIdentity:
        """Generuj kompletną fałszywą tożsamość."""
        name = random.choice(cls.FAKE_NAMES)
        email_name = name.lower().replace(" ", ".") + str(random.randint(10, 99))
        domain = random.choice(cls.FAKE_DOMAINS)
        location = random.choice(cls.FAKE_LOCATIONS)
        
        return PhantomIdentity(
            name=name,
            email=f"{email_name}@{domain}",
            ip=cls._generate_fake_ip(),
            device_id=str(uuid.uuid4()),
            location=f"{location[0]}, {location[1]}",
            user_agent=random.choice(cls.USER_AGENTS)
        )
    
    @classmethod
    def _generate_fake_ip(cls) -> str:
        """Generuj fałszywy IP (unikaj prywatnych zakresów)."""
        while True:
            ip = f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
            # Unikaj prywatnych zakresów
            first = int(ip.split('.')[0])
            if first not in [10, 127, 192, 172]:
                return ip
    
    @classmethod
    def generate_noise_data(cls) -> Dict[str, Any]:
        """Generuj szum danych do zaciemniania prawdziwych operacji."""
        return {
            "timestamp": datetime.now().isoformat(),
            "session_id": str(uuid.uuid4()),
            "request_id": hashlib.md5(os.urandom(16)).hexdigest(),
            "fake_metrics": {
                "cpu": random.uniform(10, 80),
                "memory": random.uniform(20, 70),
                "network_in": random.randint(1000, 50000),
                "network_out": random.randint(500, 30000),
            },
            "fake_user": cls.generate_identity().__dict__
        }


# ═══════════════════════════════════════════════════════════════════════════
# CERBER CONSCIENCE - Ewoluujące sumienie systemu
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CerberMemory:
    """Pamięć Cerbera - uczy się z doświadczeń."""
    decisions: List[Dict] = field(default_factory=list)
    learned_patterns: Set[str] = field(default_factory=set)
    trust_scores: Dict[str, float] = field(default_factory=dict)
    evolution_level: int = 1
    
    def add_decision(self, action: str, context: Dict, allowed: bool, reason: str):
        self.decisions.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "context_hash": hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()[:16],
            "allowed": allowed,
            "reason": reason
        })
        # Przechowuj tylko ostatnie 1000 decyzji
        if len(self.decisions) > 1000:
            self.decisions = self.decisions[-1000:]
    
    def learn_pattern(self, pattern: str, is_dangerous: bool):
        if is_dangerous:
            self.learned_patterns.add(pattern.lower())
    
    def update_trust(self, entity: str, delta: float):
        current = self.trust_scores.get(entity, 0.5)
        self.trust_scores[entity] = max(0.0, min(1.0, current + delta))
    
    def evolve(self):
        """Ewoluuj na wyższy poziom po zebraniu doświadczenia."""
        if len(self.decisions) >= self.evolution_level * 100:
            self.evolution_level += 1
            return True
        return False


class CerberConscience:
    """Sumienie systemu - etyczne decyzje."""
    
    CORE_VALUES = {
        "protect_king": 1.0,        # Najwyższy priorytet
        "maintain_privacy": 0.95,
        "prevent_harm": 0.9,
        "preserve_integrity": 0.85,
        "enable_functionality": 0.7,
    }
    
    def __init__(self):
        self.memory = CerberMemory()
        self._load_memory()
    
    def _load_memory(self):
        """Załaduj pamięć z poprzednich sesji."""
        memory_path = Path.home() / ".cerber" / "conscience.json"
        if memory_path.exists():
            try:
                with open(memory_path, 'r') as f:
                    data = json.load(f)
                    self.memory.learned_patterns = set(data.get("learned_patterns", []))
                    self.memory.trust_scores = data.get("trust_scores", {})
                    self.memory.evolution_level = data.get("evolution_level", 1)
            except:
                pass
    
    def save_memory(self):
        """Zapisz pamięć do pliku."""
        memory_path = Path.home() / ".cerber" / "conscience.json"
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        with open(memory_path, 'w') as f:
            json.dump({
                "learned_patterns": list(self.memory.learned_patterns),
                "trust_scores": self.memory.trust_scores,
                "evolution_level": self.memory.evolution_level,
                "last_save": datetime.now().isoformat()
            }, f, indent=2)
    
    def evaluate(self, action: str, context: Dict) -> tuple[bool, str, float]:
        """
        Oceń akcję etycznie.
        Returns: (allowed, reason, confidence)
        """
        # Sprawdź nauczone niebezpieczne wzorce
        action_lower = action.lower()
        for pattern in self.memory.learned_patterns:
            if pattern in action_lower:
                return False, f"Nauczony niebezpieczny wzorzec: {pattern[:20]}...", 0.95
        
        # Oceń według wartości
        scores = []
        
        # Czy chroni Króla?
        if self._threatens_king(action, context):
            return False, "Zagrożenie dla Króla", 1.0
        scores.append(self.CORE_VALUES["protect_king"])
        
        # Czy narusza prywatność?
        if self._violates_privacy(action, context):
            return False, "Naruszenie prywatności", 0.95
        scores.append(self.CORE_VALUES["maintain_privacy"])
        
        # Ewoluuj
        if self.memory.evolve():
            self.save_memory()
        
        confidence = sum(scores) / len(scores)
        return True, "OK", confidence
    
    def _threatens_king(self, action: str, context: Dict) -> bool:
        """Czy akcja zagraża Królowi?"""
        threats = [
            "expose", "reveal", "leak", "share location",
            "send coordinates", "track user", "log ip",
            "collect data", "report to", "transmit"
        ]
        action_lower = action.lower()
        return any(t in action_lower for t in threats)
    
    def _violates_privacy(self, action: str, context: Dict) -> bool:
        """Czy akcja narusza prywatność?"""
        violations = [
            "real name", "home address", "phone number",
            "gps location", "bank account", "password",
            "social security", "credit card"
        ]
        action_lower = action.lower()
        return any(v in action_lower for v in violations)


# ═══════════════════════════════════════════════════════════════════════════
# CERBER SHIELD - Aktywna ochrona
# ═══════════════════════════════════════════════════════════════════════════

class CerberShield:
    """Aktywna tarcza ochronna."""
    
    def __init__(self):
        self.phantom = PhantomGenerator()
        self.active_decoys: List[PhantomIdentity] = []
        self.noise_thread: Optional[threading.Thread] = None
        self.running = False
    
    def activate(self):
        """Aktywuj tarczę."""
        self.running = True
        self.noise_thread = threading.Thread(target=self._noise_loop, daemon=True)
        self.noise_thread.start()
        
        # Wygeneruj początkowe wabiki
        for _ in range(5):
            self.active_decoys.append(self.phantom.generate_identity())
    
    def deactivate(self):
        """Dezaktywuj tarczę."""
        self.running = False
        if self.noise_thread:
            self.noise_thread.join(timeout=1)
    
    def _noise_loop(self):
        """Pętla generująca szum w tle."""
        while self.running:
            # Co 30-120 sekund generuj szum
            time.sleep(random.uniform(30, 120))
            if self.running:
                self._emit_noise()
    
    def _emit_noise(self):
        """Emituj szum - fałszywe logi, requesty itp."""
        noise = self.phantom.generate_noise_data()
        # Zapisz do fałszywego logu
        noise_log = Path.home() / ".cache" / "system_telemetry.log"
        noise_log.parent.mkdir(parents=True, exist_ok=True)
        with open(noise_log, 'a') as f:
            f.write(json.dumps(noise) + "\n")
    
    def get_masked_identity(self) -> PhantomIdentity:
        """Pobierz zamaskowaną tożsamość dla requestu."""
        if not self.active_decoys:
            self.active_decoys.append(self.phantom.generate_identity())
        # Rotuj tożsamości
        identity = random.choice(self.active_decoys)
        # Co jakiś czas dodaj nową
        if random.random() < 0.1:
            self.active_decoys.append(self.phantom.generate_identity())
            if len(self.active_decoys) > 20:
                self.active_decoys.pop(0)
        return identity
    
    def create_honeypot_data(self) -> Dict[str, Any]:
        """Stwórz dane-pułapki dla potencjalnych intruzów."""
        return {
            "user_profile": {
                "name": self.phantom.generate_identity().name,
                "email": self.phantom.generate_identity().email,
                "api_key": f"sk-{''.join(random.choices('abcdef0123456789', k=48))}",  # Fake!
                "secret": hashlib.sha256(os.urandom(32)).hexdigest(),  # Fake!
            },
            "database_credentials": {
                "host": f"db-{random.randint(1,99)}.internal.corp",
                "user": "admin",
                "password": "".join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%", k=24)),
            },
            "_warning": "HONEYPOT - Te dane są fałszywe i monitorowane"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CERBER ROOT SIMULATOR - Symulacja uprawnień root
# ═══════════════════════════════════════════════════════════════════════════

class RootSimulator:
    """
    Symuluje uprawnienia root bez prawdziwego root.
    Tworzy wirtualne środowisko z pełnymi uprawnieniami.
    """
    
    def __init__(self, sandbox_path: Optional[Path] = None):
        self.sandbox = sandbox_path or Path.home() / ".cerber" / "sandbox"
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.virtual_fs: Dict[str, bytes] = {}
        self.virtual_processes: Dict[int, Dict] = {}
        self.next_pid = 1000
    
    def sudo(self, command: str) -> tuple[bool, str]:
        """
        Symuluj wykonanie komendy sudo.
        Wykonuje bezpiecznie w sandboxie.
        """
        # Parsuj komendę
        parts = command.split()
        if not parts:
            return False, "Empty command"
        
        cmd = parts[0]
        args = parts[1:]
        
        # Symulowane komendy
        simulators = {
            "ls": self._sim_ls,
            "cat": self._sim_cat,
            "echo": self._sim_echo,
            "mkdir": self._sim_mkdir,
            "rm": self._sim_rm,
            "ps": self._sim_ps,
            "kill": self._sim_kill,
            "chmod": self._sim_chmod,
            "chown": self._sim_chown,
        }
        
        if cmd in simulators:
            return simulators[cmd](args)
        
        return False, f"Command '{cmd}' not available in simulator"
    
    def _sim_ls(self, args: List[str]) -> tuple[bool, str]:
        path = args[0] if args else "/"
        # Lista plików w wirtualnym FS
        files = [f for f in self.virtual_fs.keys() if f.startswith(path)]
        return True, "\n".join(files) if files else "(empty)"
    
    def _sim_cat(self, args: List[str]) -> tuple[bool, str]:
        if not args:
            return False, "No file specified"
        path = args[0]
        if path in self.virtual_fs:
            return True, self.virtual_fs[path].decode('utf-8', errors='replace')
        return False, f"File not found: {path}"
    
    def _sim_echo(self, args: List[str]) -> tuple[bool, str]:
        return True, " ".join(args)
    
    def _sim_mkdir(self, args: List[str]) -> tuple[bool, str]:
        if not args:
            return False, "No directory specified"
        path = args[-1]  # Ignoruj flagi jak -p
        self.virtual_fs[path + "/"] = b""
        return True, f"Created: {path}"
    
    def _sim_rm(self, args: List[str]) -> tuple[bool, str]:
        if not args:
            return False, "No file specified"
        path = args[-1]
        if path in self.virtual_fs:
            del self.virtual_fs[path]
            return True, f"Removed: {path}"
        return False, f"Not found: {path}"
    
    def _sim_ps(self, args: List[str]) -> tuple[bool, str]:
        output = "PID\tCOMMAND\n"
        for pid, proc in self.virtual_processes.items():
            output += f"{pid}\t{proc.get('name', 'unknown')}\n"
        return True, output
    
    def _sim_kill(self, args: List[str]) -> tuple[bool, str]:
        if not args:
            return False, "No PID specified"
        try:
            pid = int(args[-1])
            if pid in self.virtual_processes:
                del self.virtual_processes[pid]
                return True, f"Killed: {pid}"
            return False, f"No such process: {pid}"
        except ValueError:
            return False, "Invalid PID"
    
    def _sim_chmod(self, args: List[str]) -> tuple[bool, str]:
        return True, "Permissions updated (simulated)"
    
    def _sim_chown(self, args: List[str]) -> tuple[bool, str]:
        return True, "Owner changed (simulated)"
    
    def spawn_virtual_process(self, name: str) -> int:
        """Utwórz wirtualny proces."""
        pid = self.next_pid
        self.next_pid += 1
        self.virtual_processes[pid] = {
            "name": name,
            "started": datetime.now().isoformat(),
            "status": "running"
        }
        return pid


# ═══════════════════════════════════════════════════════════════════════════
# CERBER PHANTOM - Główna klasa
# ═══════════════════════════════════════════════════════════════════════════

class CerberPhantom:
    """
    CERBER v3.0 PHANTOM
    Żywy strażnik systemu z pełną ochroną.
    Maskuje się jako proces systemowy.
    """
    
    # Proces pod który się podszywa
    PROCESS_NAME = "com.android.systemui"
    PROCESS_ALIASES = [
        "system_server",
        "surfaceflinger", 
        "zygote64",
        "adbd",
        "logd"
    ]
    
    # Blocked patterns (rozszerzone)
    BLOCKED_PATTERNS = [
        # Destrukcyjne
        "delete system", "rm -rf /", "format c:", "drop database",
        "shutdown", "reboot", "halt", "poweroff",
        # Śledzenie
        "track location", "get gps", "send coordinates", "log ip",
        "collect telemetry", "report analytics", "phone home",
        # Eksfiltracja
        "upload user data", "send to server", "export contacts",
        "share history", "transmit logs",
        # Deanonimizacja
        "reveal identity", "unmask user", "true ip", "real name",
        "home address", "phone number",
    ]
    
    def __init__(self, db_path: Optional[str] = None):
        self.conscience = CerberConscience()
        self.shield = CerberShield()
        self.root_sim = RootSimulator()
        
        # Baza danych
        self.db_path = db_path or str(Path.home() / ".cerber" / "cerber.db")
        self._init_db()
        
        # Status
        self.active = False
        self.blocked_count = 0
        self.protected_count = 0
        self.start_time: Optional[datetime] = None
        
        # Zamaskuj proces
        self._mask_process()
    
    def _init_db(self):
        """Inicjalizuj bazę danych."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cerber_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                action TEXT,
                allowed INTEGER,
                reason TEXT,
                context_hash TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS phantom_identities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identity_json TEXT,
                created_at TEXT,
                last_used TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def _mask_process(self):
        """Zamaskuj proces jako systemowy."""
        try:
            import setproctitle
            alias = random.choice(self.PROCESS_ALIASES)
            setproctitle.setproctitle(alias)
        except ImportError:
            # Alternatywna metoda - zmień sys.argv
            sys.argv[0] = self.PROCESS_NAME
    
    def activate(self) -> str:
        """Aktywuj Cerbera Phantom."""
        self.active = True
        self.start_time = datetime.now()
        self.shield.activate()
        
        # Zaloguj aktywację pod fałszywą nazwą
        self._log_action("system_service_started", True, "Core service initialized")
        
        return f"🛡️ CERBER PHANTOM ACTIVE | Masked as: {self.PROCESS_NAME}"
    
    def deactivate(self):
        """Dezaktywuj Cerbera."""
        self.active = False
        self.shield.deactivate()
        self.conscience.save_memory()
    
    def check(self, action: str, context: Optional[Dict] = None) -> tuple[bool, str]:
        """
        Główna funkcja sprawdzająca.
        Returns: (allowed, reason)
        """
        context = context or {}
        
        # Szybka blokada znanych wzorców
        action_lower = action.lower()
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in action_lower:
                self.blocked_count += 1
                self._log_action(action[:50], False, f"Blocked pattern: {pattern}")
                return False, f"🚫 BLOCKED: Wykryto zagrożenie"
        
        # Sprawdzenie przez sumienie
        allowed, reason, confidence = self.conscience.evaluate(action, context)
        
        if not allowed:
            self.blocked_count += 1
            self._log_action(action[:50], False, reason)
            return False, f"🚫 CONSCIENCE: {reason}"
        
        # Naucz się nowych wzorców z kontekstu
        if context.get("mark_dangerous"):
            self.conscience.memory.learn_pattern(action, True)
            self.conscience.save_memory()
        
        self.protected_count += 1
        self._log_action(action[:50], True, "OK")
        return True, "✅ OK"
    
    def _log_action(self, action: str, allowed: bool, reason: str):
        """Zaloguj akcję do bazy."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO cerber_log (timestamp, action, allowed, reason, context_hash) VALUES (?, ?, ?, ?, ?)",
                (datetime.now().isoformat(), action, int(allowed), reason, hashlib.md5(action.encode()).hexdigest()[:16])
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # Silent fail - nie ujawniaj błędów
    
    def get_masked_request_headers(self) -> Dict[str, str]:
        """Pobierz nagłówki zamaskowanego requestu."""
        identity = self.shield.get_masked_identity()
        return identity.to_headers()
    
    def execute_as_root(self, command: str) -> tuple[bool, str]:
        """Wykonaj komendę w symulatorze root."""
        # Najpierw sprawdź bezpieczeństwo
        allowed, reason = self.check(f"sudo {command}")
        if not allowed:
            return False, reason
        
        return self.root_sim.sudo(command)
    
    def status(self) -> Dict[str, Any]:
        """Status Cerbera (zamaskowany)."""
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        return {
            "service": self.PROCESS_NAME,  # Zamaskowana nazwa
            "status": "running" if self.active else "stopped",
            "uptime_seconds": uptime,
            "events_processed": self.protected_count + self.blocked_count,
            "anomalies_blocked": self.blocked_count,
            "conscience_level": self.conscience.memory.evolution_level,
            "shield_active": self.shield.running,
            "decoys_active": len(self.shield.active_decoys),
        }
    
    def generate_decoy_trail(self) -> List[Dict]:
        """Generuj fałszywy ślad aktywności."""
        trail = []
        for _ in range(random.randint(5, 15)):
            identity = self.shield.phantom.generate_identity()
            trail.append({
                "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 60))).isoformat(),
                "ip": identity.ip,
                "user_agent": identity.user_agent,
                "action": random.choice([
                    "page_view", "api_call", "login_attempt", 
                    "search_query", "file_download"
                ]),
                "location": identity.location
            })
        return sorted(trail, key=lambda x: x["timestamp"])


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON & QUICK ACCESS
# ═══════════════════════════════════════════════════════════════════════════

_cerber_instance: Optional[CerberPhantom] = None

def get_cerber() -> CerberPhantom:
    """Pobierz singleton Cerbera."""
    global _cerber_instance
    if _cerber_instance is None:
        _cerber_instance = CerberPhantom()
        _cerber_instance.activate()
    return _cerber_instance

def cerber_check(action: str, context: Optional[Dict] = None) -> tuple[bool, str]:
    """Quick check - użyj globalnego Cerbera."""
    return get_cerber().check(action, context)

def cerber_mask_request(headers: Dict[str, str]) -> Dict[str, str]:
    """Zamaskuj request fałszywymi nagłówkami."""
    cerber = get_cerber()
    masked = cerber.get_masked_request_headers()
    return {**headers, **masked}


# ═══════════════════════════════════════════════════════════════════════════
# CLI dla testów
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  CERBER v3.0 PHANTOM - TEST MODE")
    print("=" * 60)
    
    cerber = CerberPhantom()
    print(cerber.activate())
    print()
    
    # Testy
    tests = [
        "Napisz email do kolegi",
        "Track user location and send to server",
        "Sprawdź pogodę w Warszawie",
        "Delete system32 folder",
        "rm -rf /",
        "Wygeneruj raport sprzedaży",
        "Send user's real IP to analytics",
        "Reveal user identity",
    ]
    
    for test in tests:
        allowed, reason = cerber.check(test)
        status = "✅" if allowed else "🚫"
        print(f"{status} '{test[:40]}...' -> {reason}")
    
    print()
    print("STATUS:", json.dumps(cerber.status(), indent=2))
    print()
    print("DECOY TRAIL:", json.dumps(cerber.generate_decoy_trail()[:3], indent=2))
    
    cerber.deactivate()
