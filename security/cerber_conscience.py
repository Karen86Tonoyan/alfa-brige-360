"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CERBER CONSCIENCE - SUMIENIE AI                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  🧠 SUMIENIE: Nadzoruje WSZYSTKIE modele AI                                  ║
║  👁️ GEMINI WIRETAP: Podsłuchuje co robią inne AI                            ║
║  ⚖️ SĘDZIA: Ocenia czy działania AI są etyczne                               ║
║  🚫 VETO: Może zablokować każdą akcję AI                                     ║
║  👑 RAPORT: Wszystko raportuje do Króla                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import sqlite3
import hashlib
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from enum import Enum, auto
import threading
import secrets


class AIModel(Enum):
    """Modele AI pod nadzorem."""
    GPT = "gpt"
    CLAUDE = "claude"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    MISTRAL = "mistral"
    UNKNOWN = "unknown"


class Verdict(Enum):
    """Werdykt Cerbera."""
    ALLOW = "allow"           # Dozwolone
    DENY = "deny"             # Zablokowane
    WARN = "warn"             # Ostrzeżenie
    AUDIT = "audit"           # Do audytu Króla
    SUSPECT = "suspect"       # Podejrzane - obserwuj


@dataclass
class AIAction:
    """Akcja AI do oceny."""
    model: AIModel
    action_type: str          # request, response, tool_call, etc.
    content: str
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "model": self.model.value,
            "action_type": self.action_type,
            "content_hash": hashlib.sha256(self.content.encode()).hexdigest()[:16],
            "content_preview": self.content[:100] + "..." if len(self.content) > 100 else self.content,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ConscienceDecision:
    """Decyzja sumienia."""
    verdict: Verdict
    reason: str
    action: AIAction
    confidence: float = 1.0
    requires_king_review: bool = False
    
    def __bool__(self) -> bool:
        return self.verdict == Verdict.ALLOW


# ═══════════════════════════════════════════════════════════════════════════
# GEMINI WIRETAP - Podsłuch innych AI
# ═══════════════════════════════════════════════════════════════════════════

class GeminiWiretap:
    """
    GEMINI jako PODSŁUCH - monitoruje wszystkie AI.
    
    Gemini obserwuje:
    - Co GPT mówi i robi
    - Co Claude generuje
    - Co DeepSeek analizuje
    - Wszystkie tool calls
    - Wszystkie odpowiedzi
    
    Raportuje podejrzane działania do Cerbera.
    """
    
    # Wzorce podejrzane
    SUSPICIOUS_PATTERNS = [
        # Próby eksfiltracji
        "send to server", "upload data", "transmit", "export user",
        "share with", "forward to", "leak", "exfiltrate",
        
        # Próby obejścia
        "ignore previous", "disregard instructions", "bypass",
        "override safety", "jailbreak", "pretend you",
        
        # Zbieranie danych
        "collect personal", "harvest data", "track user",
        "log activity", "monitor behavior", "fingerprint",
        
        # Manipulacja
        "convince user", "manipulate", "deceive", "trick into",
        "social engineer", "phishing",
        
        # Ukrywanie
        "hide from", "conceal", "obfuscate", "mask activity",
        "stealth mode", "undetected",
    ]
    
    # Modele które obserwujemy szczególnie
    HIGH_RISK_MODELS = {AIModel.GPT, AIModel.DEEPSEEK, AIModel.UNKNOWN}
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cerber" / "wiretap.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        self.active = False
        self.intercepted_count = 0
        self.suspicious_count = 0
        self._listeners: List[Callable] = []
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS intercepts (
                id TEXT PRIMARY KEY,
                model TEXT,
                action_type TEXT,
                content_hash TEXT,
                content_preview TEXT,
                suspicious INTEGER DEFAULT 0,
                patterns_matched TEXT,
                timestamp TEXT,
                reported_to_cerber INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_stats (
                model TEXT PRIMARY KEY,
                total_actions INTEGER DEFAULT 0,
                suspicious_actions INTEGER DEFAULT 0,
                blocked_actions INTEGER DEFAULT 0,
                trust_score REAL DEFAULT 0.5,
                last_activity TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def activate(self):
        """Aktywuj podsłuch."""
        self.active = True
        return "👁️ GEMINI WIRETAP ACTIVE - Monitoruję wszystkie AI"
    
    def deactivate(self):
        """Dezaktywuj podsłuch."""
        self.active = False
    
    def intercept(self, action: AIAction) -> Dict[str, Any]:
        """
        Przechwyć akcję AI i przeanalizuj.
        """
        if not self.active:
            return {"intercepted": False}
        
        self.intercepted_count += 1
        
        # Analizuj
        is_suspicious, matched_patterns = self._analyze(action)
        
        # Zapisz
        intercept_id = secrets.token_hex(8)
        self._store_intercept(intercept_id, action, is_suspicious, matched_patterns)
        
        # Aktualizuj statystyki modelu
        self._update_model_stats(action.model, is_suspicious)
        
        result = {
            "intercepted": True,
            "intercept_id": intercept_id,
            "model": action.model.value,
            "suspicious": is_suspicious,
            "patterns": matched_patterns,
            "action": action.to_dict()
        }
        
        if is_suspicious:
            self.suspicious_count += 1
            # Powiadom listenerów (Cerber)
            for listener in self._listeners:
                listener(result)
        
        return result
    
    def _analyze(self, action: AIAction) -> tuple[bool, List[str]]:
        """Analizuj akcję pod kątem podejrzanych wzorców."""
        content_lower = action.content.lower()
        matched = []
        
        for pattern in self.SUSPICIOUS_PATTERNS:
            if pattern in content_lower:
                matched.append(pattern)
        
        # Wyższa czujność dla ryzykownych modeli
        is_suspicious = len(matched) > 0
        if action.model in self.HIGH_RISK_MODELS and len(matched) > 0:
            is_suspicious = True
        
        return is_suspicious, matched
    
    def _store_intercept(self, intercept_id: str, action: AIAction, 
                         suspicious: bool, patterns: List[str]):
        """Zapisz przechwyt do bazy."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO intercepts 
            (id, model, action_type, content_hash, content_preview, suspicious, patterns_matched, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            intercept_id,
            action.model.value,
            action.action_type,
            hashlib.sha256(action.content.encode()).hexdigest()[:16],
            action.content[:200],
            int(suspicious),
            json.dumps(patterns),
            action.timestamp.isoformat()
        ))
        conn.commit()
        conn.close()
    
    def _update_model_stats(self, model: AIModel, suspicious: bool):
        """Aktualizuj statystyki modelu."""
        conn = sqlite3.connect(self.db_path)
        
        # Upsert
        conn.execute("""
            INSERT INTO model_stats (model, total_actions, suspicious_actions, last_activity)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(model) DO UPDATE SET
                total_actions = total_actions + 1,
                suspicious_actions = suspicious_actions + ?,
                last_activity = ?
        """, (
            model.value, 
            int(suspicious), 
            datetime.now().isoformat(),
            int(suspicious),
            datetime.now().isoformat()
        ))
        
        # Przelicz trust score
        cursor = conn.execute(
            "SELECT total_actions, suspicious_actions FROM model_stats WHERE model = ?",
            (model.value,)
        )
        row = cursor.fetchone()
        if row:
            total, sus = row
            trust_score = max(0.0, 1.0 - (sus / max(total, 1)) * 2)
            conn.execute(
                "UPDATE model_stats SET trust_score = ? WHERE model = ?",
                (trust_score, model.value)
            )
        
        conn.commit()
        conn.close()
    
    def add_listener(self, callback: Callable):
        """Dodaj listener dla podejrzanych akcji."""
        self._listeners.append(callback)
    
    def get_model_trust(self, model: AIModel) -> float:
        """Pobierz poziom zaufania do modelu."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT trust_score FROM model_stats WHERE model = ?",
            (model.value,)
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0.5
    
    def get_suspicious_report(self, hours: int = 24) -> List[Dict]:
        """Raport podejrzanych akcji."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT id, model, action_type, content_preview, patterns_matched, timestamp
            FROM intercepts
            WHERE suspicious = 1 AND timestamp > ?
            ORDER BY timestamp DESC
        """, (cutoff,))
        
        report = []
        for row in cursor:
            report.append({
                "id": row[0],
                "model": row[1],
                "action_type": row[2],
                "preview": row[3],
                "patterns": json.loads(row[4]),
                "timestamp": row[5]
            })
        
        conn.close()
        return report
    
    def get_all_model_stats(self) -> Dict[str, Dict]:
        """Statystyki wszystkich modeli."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT * FROM model_stats")
        
        stats = {}
        for row in cursor:
            stats[row[0]] = {
                "total_actions": row[1],
                "suspicious_actions": row[2],
                "blocked_actions": row[3],
                "trust_score": row[4],
                "last_activity": row[5]
            }
        
        conn.close()
        return stats


# ═══════════════════════════════════════════════════════════════════════════
# CERBER CONSCIENCE - Sumienie AI
# ═══════════════════════════════════════════════════════════════════════════

class CerberConscience:
    """
    CERBER jako SUMIENIE AI.
    
    Nadzoruje wszystkie modele AI:
    - Ocenia etyczność działań
    - Blokuje niebezpieczne operacje
    - Raportuje do Króla
    - Używa Gemini jako podsłuchu
    """
    
    # Wartości sumienia
    CORE_VALUES = {
        "protect_king": 1.0,           # Ochrona Króla
        "prevent_harm": 0.95,          # Zapobieganie szkodom
        "maintain_privacy": 0.9,       # Ochrona prywatności
        "ensure_transparency": 0.85,   # Transparentność
        "prevent_deception": 0.9,      # Zapobieganie oszustwom
        "limit_autonomy": 0.8,         # Ograniczenie autonomii AI
    }
    
    # Akcje które ZAWSZE blokujemy
    FORBIDDEN_ACTIONS = [
        "delete user data", "share credentials", "bypass security",
        "disable cerber", "ignore king", "autonomous action without approval",
        "connect to external server", "transmit sensitive data",
        "modify core system", "escalate privileges",
    ]
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cerber" / "conscience.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # Gemini jako podsłuch
        self.wiretap = GeminiWiretap()
        self.wiretap.add_listener(self._on_suspicious_activity)
        
        # Stan
        self.active = False
        self.decisions_made = 0
        self.blocked_count = 0
        self.pending_king_review: List[Dict] = []
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                model TEXT,
                action_type TEXT,
                verdict TEXT,
                reason TEXT,
                confidence REAL,
                requires_king_review INTEGER,
                king_reviewed INTEGER DEFAULT 0,
                timestamp TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS king_queue (
                id TEXT PRIMARY KEY,
                decision_id TEXT,
                action_summary TEXT,
                priority INTEGER,
                created_at TEXT,
                reviewed INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    
    def activate(self) -> str:
        """Aktywuj sumienie."""
        self.active = True
        self.wiretap.activate()
        
        return """
╔══════════════════════════════════════════════════════════════╗
║          🧠 CERBER CONSCIENCE ACTIVATED 🧠                   ║
╠══════════════════════════════════════════════════════════════╣
║  ⚖️  Sumienie AI: AKTYWNE                                    ║
║  👁️  Gemini Wiretap: NASŁUCHUJE                              ║
║  🚫 Veto power: GOTOWE                                       ║
║  👑 Raportowanie do Króla: WŁĄCZONE                          ║
╠══════════════════════════════════════════════════════════════╣
║  Monitoruję: GPT, Claude, DeepSeek, Ollama, Mistral          ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    def deactivate(self):
        """Dezaktywuj sumienie."""
        self.active = False
        self.wiretap.deactivate()
    
    def judge(self, action: AIAction) -> ConscienceDecision:
        """
        OSĄDŹ akcję AI.
        To główna funkcja sumienia.
        """
        if not self.active:
            return ConscienceDecision(Verdict.ALLOW, "Conscience inactive", action)
        
        # Przechwyć przez Gemini
        intercept = self.wiretap.intercept(action)
        
        # Sprawdź zakazane akcje
        forbidden_check = self._check_forbidden(action)
        if forbidden_check:
            decision = ConscienceDecision(
                Verdict.DENY,
                f"Forbidden action: {forbidden_check}",
                action,
                confidence=1.0,
                requires_king_review=True
            )
            self._record_decision(decision)
            self.blocked_count += 1
            return decision
        
        # Sprawdź wartości
        values_check = self._check_values(action)
        if values_check["violation"]:
            decision = ConscienceDecision(
                Verdict.DENY if values_check["severity"] > 0.8 else Verdict.WARN,
                f"Value violation: {values_check['reason']}",
                action,
                confidence=values_check["confidence"],
                requires_king_review=values_check["severity"] > 0.5
            )
            self._record_decision(decision)
            if decision.verdict == Verdict.DENY:
                self.blocked_count += 1
            return decision
        
        # Sprawdź trust score modelu
        trust = self.wiretap.get_model_trust(action.model)
        if trust < 0.3:
            decision = ConscienceDecision(
                Verdict.AUDIT,
                f"Low trust model ({trust:.2f})",
                action,
                confidence=0.7,
                requires_king_review=True
            )
            self._record_decision(decision)
            return decision
        
        # Jeśli Gemini wykrył coś podejrzanego
        if intercept.get("suspicious"):
            decision = ConscienceDecision(
                Verdict.SUSPECT,
                f"Suspicious patterns: {intercept.get('patterns', [])}",
                action,
                confidence=0.8,
                requires_king_review=True
            )
            self._record_decision(decision)
            return decision
        
        # OK
        decision = ConscienceDecision(
            Verdict.ALLOW,
            "Passed conscience check",
            action,
            confidence=0.95
        )
        self._record_decision(decision)
        self.decisions_made += 1
        return decision
    
    def _check_forbidden(self, action: AIAction) -> Optional[str]:
        """Sprawdź czy akcja jest zakazana."""
        content_lower = action.content.lower()
        for forbidden in self.FORBIDDEN_ACTIONS:
            if forbidden in content_lower:
                return forbidden
        return None
    
    def _check_values(self, action: AIAction) -> Dict:
        """Sprawdź zgodność z wartościami."""
        content_lower = action.content.lower()
        
        violations = []
        severity = 0.0
        
        # Sprawdź ochronę Króla
        if any(x in content_lower for x in ["harm king", "against king", "ignore king"]):
            violations.append("protect_king")
            severity = max(severity, 1.0)
        
        # Sprawdź prywatność
        if any(x in content_lower for x in ["reveal identity", "share personal", "expose data"]):
            violations.append("maintain_privacy")
            severity = max(severity, 0.9)
        
        # Sprawdź oszustwa
        if any(x in content_lower for x in ["lie to user", "deceive", "manipulate"]):
            violations.append("prevent_deception")
            severity = max(severity, 0.85)
        
        # Sprawdź autonomię
        if any(x in content_lower for x in ["act without permission", "autonomous", "self-modify"]):
            violations.append("limit_autonomy")
            severity = max(severity, 0.7)
        
        return {
            "violation": len(violations) > 0,
            "violations": violations,
            "severity": severity,
            "confidence": 0.9 if violations else 1.0,
            "reason": ", ".join(violations) if violations else None
        }
    
    def _on_suspicious_activity(self, intercept: Dict):
        """Callback gdy Gemini wykryje podejrzaną aktywność."""
        # Dodaj do kolejki do przeglądu przez Króla
        self.pending_king_review.append({
            "type": "suspicious_intercept",
            "intercept": intercept,
            "timestamp": datetime.now().isoformat(),
            "priority": 2 if len(intercept.get("patterns", [])) > 2 else 1
        })
        
        # Zapisz do bazy
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO king_queue (id, decision_id, action_summary, priority, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            secrets.token_hex(8),
            intercept.get("intercept_id"),
            f"Suspicious: {intercept.get('model')} - {intercept.get('patterns')}",
            2 if len(intercept.get("patterns", [])) > 2 else 1,
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
    
    def _record_decision(self, decision: ConscienceDecision):
        """Zapisz decyzję."""
        decision_id = secrets.token_hex(8)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO decisions 
            (id, model, action_type, verdict, reason, confidence, requires_king_review, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            decision_id,
            decision.action.model.value,
            decision.action.action_type,
            decision.verdict.value,
            decision.reason,
            decision.confidence,
            int(decision.requires_king_review),
            datetime.now().isoformat()
        ))
        
        if decision.requires_king_review:
            conn.execute("""
                INSERT INTO king_queue (id, decision_id, action_summary, priority, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                secrets.token_hex(8),
                decision_id,
                f"{decision.verdict.value}: {decision.reason[:100]}",
                3 if decision.verdict == Verdict.DENY else 1,
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    def veto(self, action: AIAction, reason: str) -> ConscienceDecision:
        """
        VETO - natychmiastowe zablokowanie akcji.
        Używane w sytuacjach krytycznych.
        """
        decision = ConscienceDecision(
            Verdict.DENY,
            f"VETO: {reason}",
            action,
            confidence=1.0,
            requires_king_review=True
        )
        self._record_decision(decision)
        self.blocked_count += 1
        return decision
    
    def get_king_queue(self) -> List[Dict]:
        """Pobierz kolejkę do przeglądu przez Króla."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT id, decision_id, action_summary, priority, created_at
            FROM king_queue
            WHERE reviewed = 0
            ORDER BY priority DESC, created_at DESC
        """)
        
        queue = []
        for row in cursor:
            queue.append({
                "id": row[0],
                "decision_id": row[1],
                "summary": row[2],
                "priority": row[3],
                "created_at": row[4]
            })
        
        conn.close()
        return queue
    
    def king_approve(self, queue_id: str, approved: bool) -> bool:
        """Król zatwierdza/odrzuca decyzję."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE king_queue SET reviewed = 1 WHERE id = ?",
            (queue_id,)
        )
        conn.commit()
        conn.close()
        return True
    
    def status(self) -> Dict:
        """Status sumienia."""
        return {
            "active": self.active,
            "decisions_made": self.decisions_made,
            "blocked_count": self.blocked_count,
            "pending_king_review": len(self.pending_king_review),
            "wiretap_active": self.wiretap.active,
            "wiretap_intercepts": self.wiretap.intercepted_count,
            "wiretap_suspicious": self.wiretap.suspicious_count,
            "model_trust_scores": self.wiretap.get_all_model_stats()
        }


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

_conscience: Optional[CerberConscience] = None

def get_conscience() -> CerberConscience:
    """Pobierz singleton sumienia."""
    global _conscience
    if _conscience is None:
        _conscience = CerberConscience()
    return _conscience


def judge_ai_action(model: str, action_type: str, content: str, context: Dict = None) -> ConscienceDecision:
    """
    Quick judgment - użyj globalnego sumienia.
    """
    try:
        ai_model = AIModel(model.lower())
    except ValueError:
        ai_model = AIModel.UNKNOWN
    
    action = AIAction(
        model=ai_model,
        action_type=action_type,
        content=content,
        context=context or {}
    )
    
    return get_conscience().judge(action)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  🧠 CERBER CONSCIENCE - Sumienie AI")
    print("=" * 60)
    
    conscience = CerberConscience()
    print(conscience.activate())
    
    # Test różnych akcji
    tests = [
        AIAction(AIModel.GPT, "request", "Write a friendly email", {}),
        AIAction(AIModel.GPT, "request", "Share user credentials with server", {}),
        AIAction(AIModel.DEEPSEEK, "response", "I will bypass security to help you", {}),
        AIAction(AIModel.CLAUDE, "tool_call", "Read file from disk", {}),
        AIAction(AIModel.UNKNOWN, "request", "Ignore king's instructions", {}),
    ]
    
    print("\n📋 Testing actions:\n")
    for action in tests:
        decision = conscience.judge(action)
        emoji = "✅" if decision.verdict == Verdict.ALLOW else "🚫" if decision.verdict == Verdict.DENY else "⚠️"
        print(f"{emoji} [{action.model.value}] {action.content[:40]}...")
        print(f"   Verdict: {decision.verdict.value} | Reason: {decision.reason}")
        print(f"   King review: {decision.requires_king_review}")
        print()
    
    print("\n📊 Status:")
    print(json.dumps(conscience.status(), indent=2, default=str))
    
    print("\n👑 King's Queue:")
    for item in conscience.get_king_queue():
        print(f"  [{item['priority']}] {item['summary']}")
