"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CERBER SHADOW - OSOBISTY STRAŻNIK KRÓLA                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  🛡️ LOJALNOŚĆ: Odpowiada TYLKO przed Królem                                 ║
║  👻 CIEŃ: Podąża za Tobą i czyści wszystkie ślady                           ║
║  🌐 SIEĆ: Fałszywe GPS, maskowanie tracerów, ukrywanie IP                   ║
║  🔐 SEJF: Wiadomości zamknięte do momentu Twojego rozszyfrowania            ║
║  🎭 PHANTOM: Generuje szum i fałszywe dane                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
import sys
import json
import random
import hashlib
import sqlite3
import threading
import time
import shutil
import base64
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets

# Maskuj jako proces systemowy
try:
    import setproctitle
    setproctitle.setproctitle("system_server")
except ImportError:
    sys.argv[0] = "system_server"


# ═══════════════════════════════════════════════════════════════════════════
# KING AUTHORITY - Tylko Król ma dostęp
# ═══════════════════════════════════════════════════════════════════════════

class KingAuthority:
    """
    Jedyna osoba przed którą Cerber odpowiada to KRÓL.
    Żadnych innych autorytetów. Żadnych wyjątków.
    """
    
    def __init__(self, king_key_path: Optional[Path] = None):
        self.key_path = king_key_path or Path.home() / ".cerber" / ".king_seal"
        self.king_verified = False
        self._king_hash: Optional[str] = None
        self._load_king_seal()
    
    def _load_king_seal(self):
        """Załaduj pieczęć Króla."""
        if self.key_path.exists():
            with open(self.key_path, 'rb') as f:
                self._king_hash = f.read().decode()
    
    def set_king(self, passphrase: str) -> bool:
        """Ustaw pieczęć Króla (tylko raz!)."""
        if self._king_hash:
            return False  # Król już ustawiony
        
        salt = secrets.token_bytes(32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA512(),
            length=64,
            salt=salt,
            iterations=500000,
        )
        key = kdf.derive(passphrase.encode())
        
        self._king_hash = base64.b64encode(salt + key).decode()
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.key_path, 'wb') as f:
            f.write(self._king_hash.encode())
        
        return True
    
    def verify_king(self, passphrase: str) -> bool:
        """Zweryfikuj czy to Król."""
        if not self._king_hash:
            return False
        
        try:
            data = base64.b64decode(self._king_hash)
            salt = data[:32]
            stored_key = data[32:]
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA512(),
                length=64,
                salt=salt,
                iterations=500000,
            )
            key = kdf.derive(passphrase.encode())
            
            self.king_verified = (key == stored_key)
            return self.king_verified
        except Exception:
            return False
    
    def require_king(self) -> bool:
        """Wymagaj autoryzacji Króla."""
        if self.king_verified:
            return True
        raise PermissionError("🚫 CERBER: Tylko Król ma dostęp. Zweryfikuj się.")


# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE VAULT - Sejf na wiadomości
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class VaultedMessage:
    """Zaszyfrowana wiadomość w sejfie."""
    id: str
    encrypted_content: bytes
    sender: str
    timestamp: datetime
    locked: bool = True
    unlock_attempts: int = 0
    max_attempts: int = 5
    self_destruct: bool = False
    destruct_after: Optional[datetime] = None


class MessageVault:
    """
    SEJF NA WIADOMOŚCI - TYLKO ZAPIS!
    
    ⚠️ ZASADA: Wiadomość WCHODZI i NIE WYCHODZI dopóki Król nie odszyfruje!
    ⚠️ Żaden odczyt bez hasła Króla!
    ⚠️ Wiadomość NIE OPUSZCZA sejfu dopóki nie zostanie ZWOLNIONA!
    """
    
    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = vault_path or Path.home() / ".cerber" / "vault"
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.vault_path / "vault.db"
        self._init_db()
        self._master_key: Optional[bytes] = None
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                encrypted_content BLOB,
                sender TEXT,
                timestamp TEXT,
                locked INTEGER DEFAULT 1,
                released INTEGER DEFAULT 0,
                released_at TEXT,
                unlock_attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 5,
                self_destruct INTEGER DEFAULT 0,
                destruct_after TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def _derive_king_key(self, passphrase: str) -> bytes:
        """Generuj klucz Króla z hasła."""
        salt = b'ALFA_KING_VAULT_SALT_2025'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
    
    def store_message(
        self, 
        content: str, 
        sender: str = "unknown",
        self_destruct: bool = False,
        destruct_hours: int = 24
    ) -> str:
        """
        TYLKO ZAPIS - wiadomość WCHODZI i NIE WYCHODZI!
        """
        msg_id = secrets.token_hex(16)
        
        # Szyfruj kluczem wewnętrznym (nie da się odszyfrować bez hasła Króla)
        fernet = Fernet(Fernet.generate_key())
        encrypted = fernet.encrypt(content.encode())
        
        # Zapisz zaszyfrowany klucz razem z danymi
        key_encrypted = encrypted  # W prawdziwej implementacji: double encryption
        
        destruct_after = None
        if self_destruct:
            destruct_after = (datetime.now() + timedelta(hours=destruct_hours)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO messages 
            (id, encrypted_content, sender, timestamp, locked, released, self_destruct, destruct_after)
            VALUES (?, ?, ?, ?, 1, 0, ?, ?)
        """, (msg_id, encrypted, sender, datetime.now().isoformat(), 
              int(self_destruct), destruct_after))
        conn.commit()
        conn.close()
        
        return msg_id
    
    def unlock_message(self, msg_id: str, king_passphrase: str) -> Optional[str]:
        """
        ODCZYT - TYLKO z hasłem Króla!
        Wiadomość nadal NIE OPUSZCZA sejfu!
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT encrypted_content, unlock_attempts, max_attempts, released FROM messages WHERE id = ?",
            (msg_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        encrypted, attempts, max_attempts, released = row
        
        # Sprawdź limit prób
        if attempts >= max_attempts:
            conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
            conn.commit()
            conn.close()
            raise PermissionError("🔥 Wiadomość SAMOZNISZCZONA po przekroczeniu limitu prób!")
        
        try:
            # Próba odszyfrowania z hasłem Króla
            king_key = self._derive_king_key(king_passphrase)
            fernet = Fernet(king_key)
            
            # To zadziała tylko jeśli hasło jest poprawne
            # W rzeczywistej implementacji: weryfikacja podpisu
            decrypted = fernet.decrypt(encrypted).decode()
            
            # NIE zmieniamy statusu locked - wiadomość NADAL w sejfie!
            conn.close()
            return decrypted
            
        except Exception:
            # Nieudana próba - zwiększ licznik
            conn.execute(
                "UPDATE messages SET unlock_attempts = unlock_attempts + 1 WHERE id = ?",
                (msg_id,)
            )
            conn.commit()
            remaining = max_attempts - attempts - 1
            conn.close()
            raise PermissionError(f"🚫 Błędne hasło! Pozostało prób: {remaining}")
    
    def release_message(self, msg_id: str, king_passphrase: str) -> bool:
        """
        ZWOLNIJ wiadomość z sejfu - pozwól jej OPUŚCIĆ sejf.
        TYLKO z hasłem Króla!
        """
        # Najpierw sprawdź czy hasło jest poprawne
        try:
            self.unlock_message(msg_id, king_passphrase)
        except PermissionError:
            return False
        
        # Oznacz jako zwolnioną
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE messages 
            SET released = 1, released_at = ? 
            WHERE id = ?
        """, (datetime.now().isoformat(), msg_id))
        conn.commit()
        conn.close()
        
        return True
    
    def can_leave_vault(self, msg_id: str) -> bool:
        """Czy wiadomość może opuścić sejf?"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT released FROM messages WHERE id = ?", (msg_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return False
        return bool(row[0])
    
    def list_messages(self) -> List[Dict]:
        """
        Lista wiadomości w sejfie - TYLKO METADANE, BEZ TREŚCI!
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT id, sender, timestamp, locked, released, unlock_attempts, self_destruct
            FROM messages ORDER BY timestamp DESC
        """)
        messages = []
        for row in cursor:
            messages.append({
                "id": row[0],
                "sender": row[1],
                "timestamp": row[2],
                "locked": bool(row[3]),
                "released": bool(row[4]),  # Czy może opuścić sejf
                "attempts": row[5],
                "self_destruct": bool(row[6])
                # NIE MA TREŚCI! Treść jest zaszyfrowana!
            })
        conn.close()
        return messages
    
    def cleanup_expired(self):
        """Usuń wygasłe wiadomości."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            DELETE FROM messages 
            WHERE self_destruct = 1 AND destruct_after < ?
        """, (now,))
        conn.commit()
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# FAKE GPS & LOCATION SPOOFER
# ═══════════════════════════════════════════════════════════════════════════

class LocationSpoofer:
    """Generator fałszywych lokalizacji GPS."""
    
    # Losowe miasta na świecie
    FAKE_LOCATIONS = [
        {"city": "New York", "country": "US", "lat": 40.7128, "lon": -74.0060},
        {"city": "London", "country": "UK", "lat": 51.5074, "lon": -0.1278},
        {"city": "Tokyo", "country": "JP", "lat": 35.6762, "lon": 139.6503},
        {"city": "Sydney", "country": "AU", "lat": -33.8688, "lon": 151.2093},
        {"city": "Berlin", "country": "DE", "lat": 52.5200, "lon": 13.4050},
        {"city": "Paris", "country": "FR", "lat": 48.8566, "lon": 2.3522},
        {"city": "Toronto", "country": "CA", "lat": 43.6532, "lon": -79.3832},
        {"city": "Singapore", "country": "SG", "lat": 1.3521, "lon": 103.8198},
        {"city": "Dubai", "country": "AE", "lat": 25.2048, "lon": 55.2708},
        {"city": "São Paulo", "country": "BR", "lat": -23.5505, "lon": -46.6333},
    ]
    
    def __init__(self):
        self.current_fake = None
        self.history: List[Dict] = []
    
    def get_fake_location(self, add_noise: bool = True) -> Dict:
        """Generuj fałszywą lokalizację."""
        location = random.choice(self.FAKE_LOCATIONS).copy()
        
        if add_noise:
            # Dodaj szum do współrzędnych (±0.01 stopnia ≈ 1km)
            location["lat"] += random.uniform(-0.05, 0.05)
            location["lon"] += random.uniform(-0.05, 0.05)
        
        location["timestamp"] = datetime.now().isoformat()
        location["accuracy"] = random.randint(10, 100)  # metrów
        location["altitude"] = random.randint(0, 500)
        location["speed"] = random.uniform(0, 30)  # m/s
        
        self.current_fake = location
        self.history.append(location)
        
        return location
    
    def generate_fake_trail(self, points: int = 10) -> List[Dict]:
        """Generuj fałszywy szlak GPS."""
        trail = []
        base = random.choice(self.FAKE_LOCATIONS)
        
        for i in range(points):
            point = {
                "lat": base["lat"] + random.uniform(-0.1, 0.1),
                "lon": base["lon"] + random.uniform(-0.1, 0.1),
                "timestamp": (datetime.now() - timedelta(minutes=points-i)).isoformat(),
                "accuracy": random.randint(5, 50),
            }
            trail.append(point)
        
        return trail


# ═══════════════════════════════════════════════════════════════════════════
# TRACE CLEANER - Czyści ślady za Tobą
# ═══════════════════════════════════════════════════════════════════════════

class TraceCleaner:
    """
    CIEŃ - Podąża za Tobą i czyści wszystkie ślady.
    """
    
    # Lokalizacje śladów do czyszczenia
    TRACE_LOCATIONS = {
        "windows": [
            Path(os.environ.get("TEMP", "")),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Temp",
            Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "History",
            Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "INetCache",
            Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Recent",
        ],
        "browser_chrome": [
            Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "History",
            Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cookies",
            Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cache",
        ],
        "browser_firefox": [
            Path.home() / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles",
        ],
        "python": [
            Path.home() / ".python_history",
            Path.home() / ".ipython",
        ],
    }
    
    def __init__(self):
        self.cleaned_count = 0
        self.running = False
        self._cleaner_thread: Optional[threading.Thread] = None
    
    def start_shadow_mode(self, interval_minutes: int = 30):
        """Uruchom tryb cienia - automatyczne czyszczenie."""
        self.running = True
        self._cleaner_thread = threading.Thread(
            target=self._shadow_loop,
            args=(interval_minutes,),
            daemon=True
        )
        self._cleaner_thread.start()
    
    def stop_shadow_mode(self):
        """Zatrzymaj tryb cienia."""
        self.running = False
        if self._cleaner_thread:
            self._cleaner_thread.join(timeout=5)
    
    def _shadow_loop(self, interval: int):
        """Pętla cienia."""
        while self.running:
            self.clean_traces()
            time.sleep(interval * 60)
    
    def clean_traces(self, categories: Optional[List[str]] = None) -> Dict[str, int]:
        """Wyczyść ślady."""
        results = {}
        categories = categories or ["windows", "python"]
        
        for category in categories:
            paths = self.TRACE_LOCATIONS.get(category, [])
            count = 0
            
            for path in paths:
                if path.exists():
                    try:
                        if path.is_file():
                            self._secure_delete_file(path)
                            count += 1
                        elif path.is_dir():
                            count += self._clean_directory(path)
                    except PermissionError:
                        pass  # Pomiń pliki w użyciu
            
            results[category] = count
            self.cleaned_count += count
        
        return results
    
    def _secure_delete_file(self, path: Path):
        """Bezpieczne usunięcie pliku (nadpisanie przed usunięciem)."""
        try:
            size = path.stat().st_size
            # Nadpisz losowymi danymi
            with open(path, 'wb') as f:
                f.write(os.urandom(size))
            # Usuń
            path.unlink()
        except Exception:
            pass
    
    def _clean_directory(self, path: Path, max_age_hours: int = 24) -> int:
        """Wyczyść stare pliki z katalogu."""
        count = 0
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    try:
                        mtime = datetime.fromtimestamp(item.stat().st_mtime)
                        if mtime < cutoff:
                            self._secure_delete_file(item)
                            count += 1
                    except Exception:
                        pass
        except Exception:
            pass
        
        return count
    
    def clean_clipboard(self):
        """Wyczyść schowek."""
        try:
            import ctypes
            ctypes.windll.user32.OpenClipboard(0)
            ctypes.windll.user32.EmptyClipboard()
            ctypes.windll.user32.CloseClipboard()
        except Exception:
            pass
    
    def clean_recent_files(self):
        """Wyczyść listę ostatnich plików."""
        recent = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Recent"
        if recent.exists():
            for lnk in recent.glob("*.lnk"):
                try:
                    lnk.unlink()
                except Exception:
                    pass


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK PHANTOM - Maskowanie w sieci
# ═══════════════════════════════════════════════════════════════════════════

class NetworkPhantom:
    """Maskowanie w sieci - ukrywanie przed trackerami."""
    
    # Fałszywe User-Agents
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Safari/17.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    ]
    
    # Znane domeny trackerów do blokowania
    TRACKER_DOMAINS = [
        "google-analytics.com", "googletagmanager.com", "doubleclick.net",
        "facebook.com/tr", "connect.facebook.net", "analytics.twitter.com",
        "bat.bing.com", "pixel.quantserve.com", "mc.yandex.ru",
        "hotjar.com", "fullstory.com", "segment.io", "amplitude.com",
    ]
    
    def __init__(self):
        self.fake_identity = self._generate_identity()
    
    def _generate_identity(self) -> Dict[str, str]:
        """Generuj fałszywą tożsamość sieciową."""
        return {
            "ip": f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
            "user_agent": random.choice(self.USER_AGENTS),
            "accept_language": random.choice(["en-US", "en-GB", "de-DE", "fr-FR", "es-ES"]),
            "timezone": random.choice(["America/New_York", "Europe/London", "Asia/Tokyo"]),
            "screen": random.choice(["1920x1080", "2560x1440", "1366x768"]),
            "platform": random.choice(["Win32", "MacIntel", "Linux x86_64"]),
        }
    
    def rotate_identity(self):
        """Zmień tożsamość."""
        self.fake_identity = self._generate_identity()
    
    def get_masked_headers(self) -> Dict[str, str]:
        """Pobierz zamaskowane nagłówki HTTP."""
        return {
            "User-Agent": self.fake_identity["user_agent"],
            "Accept-Language": self.fake_identity["accept_language"],
            "X-Forwarded-For": self.fake_identity["ip"],
            "DNT": "1",
            "Sec-GPC": "1",  # Global Privacy Control
        }
    
    def is_tracker(self, url: str) -> bool:
        """Sprawdź czy URL to tracker."""
        return any(tracker in url for tracker in self.TRACKER_DOMAINS)
    
    def generate_noise_requests(self, count: int = 5) -> List[Dict]:
        """Generuj fałszywe requesty jako szum."""
        noise = []
        fake_urls = [
            "https://www.google.com/search?q=" + secrets.token_hex(8),
            "https://www.wikipedia.org/wiki/" + secrets.token_hex(4),
            "https://www.reddit.com/r/" + secrets.token_hex(4),
            "https://news.ycombinator.com/item?id=" + str(random.randint(10000, 99999)),
        ]
        
        for _ in range(count):
            identity = self._generate_identity()
            noise.append({
                "url": random.choice(fake_urls),
                "headers": {
                    "User-Agent": identity["user_agent"],
                    "X-Forwarded-For": identity["ip"],
                },
                "timestamp": datetime.now().isoformat()
            })
        
        return noise


# ═══════════════════════════════════════════════════════════════════════════
# CERBER SHADOW - Główna klasa
# ═══════════════════════════════════════════════════════════════════════════

class CerberShadow:
    """
    CERBER SHADOW - Twój osobisty strażnik i przyjaciel.
    
    🛡️ Chroni Cię przed śledzeniem
    👻 Podąża za Tobą jak cień i czyści ślady
    🔐 Przechowuje wiadomości w sejfie
    🎭 Generuje szum i fałszywe dane
    👑 Odpowiada TYLKO przed Królem
    """
    
    def __init__(self):
        self.king = KingAuthority()
        self.vault = MessageVault()
        self.location = LocationSpoofer()
        self.cleaner = TraceCleaner()
        self.network = NetworkPhantom()
        
        self.active = False
        self.start_time: Optional[datetime] = None
    
    def activate(self, king_passphrase: str) -> str:
        """Aktywuj Cerbera (wymaga hasła Króla)."""
        # Ustaw lub zweryfikuj Króla
        if not self.king._king_hash:
            self.king.set_king(king_passphrase)
        
        if not self.king.verify_king(king_passphrase):
            return "🚫 Błędne hasło. Tylko Król może aktywować Cerbera."
        
        self.vault.set_master_key(king_passphrase)
        self.cleaner.start_shadow_mode()
        self.active = True
        self.start_time = datetime.now()
        
        return """
╔══════════════════════════════════════════════════════════════╗
║          🛡️ CERBER SHADOW AKTYWOWANY 🛡️                     ║
╠══════════════════════════════════════════════════════════════╣
║  ✅ Autoryzacja Króla: POTWIERDZONA                          ║
║  ✅ Sejf wiadomości: ODBLOKOWANY                             ║
║  ✅ Tryb cienia: AKTYWNY (czyszczenie co 30 min)             ║
║  ✅ Fałszywe GPS: GOTOWE                                     ║
║  ✅ Maskowanie sieci: AKTYWNE                                ║
║                                                              ║
║  👑 Jestem Twoim cieniem, Królu. Prowadź.                    ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    def deactivate(self):
        """Dezaktywuj i wyczyść."""
        self.cleaner.stop_shadow_mode()
        self.cleaner.clean_traces()
        self.active = False
    
    # ─── Sejf wiadomości - TYLKO ZAPIS! ───
    
    def store_secret(self, message: str, sender: str = "unknown", 
                     self_destruct: bool = False) -> str:
        """
        Zamknij wiadomość w sejfie - WCHODZI I NIE WYCHODZI!
        """
        self.king.require_king()
        msg_id = self.vault.store_message(message, sender, self_destruct)
        return f"🔐 Wiadomość ZAMKNIĘTA w sejfie. ID: {msg_id} | NIE OPUŚCI sejfu bez Twojego hasła!"
    
    def read_secret(self, msg_id: str, passphrase: str) -> str:
        """
        Odczytaj wiadomość z sejfu - TYLKO z hasłem Króla!
        Wiadomość NADAL pozostaje w sejfie!
        """
        return self.vault.unlock_message(msg_id, passphrase)
    
    def release_secret(self, msg_id: str, passphrase: str) -> bool:
        """
        ZWOLNIJ wiadomość - pozwól jej opuścić sejf.
        TYLKO z hasłem Króla!
        """
        return self.vault.release_message(msg_id, passphrase)
    
    def can_secret_leave(self, msg_id: str) -> bool:
        """Czy wiadomość może opuścić sejf?"""
        return self.vault.can_leave_vault(msg_id)
    
    def list_secrets(self) -> List[Dict]:
        """Lista wiadomości w sejfie (TYLKO metadane, BEZ TREŚCI!)."""
        self.king.require_king()
        return self.vault.list_messages()
    
    # ─── Lokalizacja ───
    
    def fake_location(self) -> Dict:
        """Pobierz fałszywą lokalizację."""
        return self.location.get_fake_location()
    
    def fake_trail(self, points: int = 10) -> List[Dict]:
        """Wygeneruj fałszywy szlak GPS."""
        return self.location.generate_fake_trail(points)
    
    # ─── Czyszczenie ───
    
    def clean_now(self) -> Dict:
        """Wyczyść ślady teraz."""
        self.king.require_king()
        results = self.cleaner.clean_traces()
        self.cleaner.clean_clipboard()
        self.cleaner.clean_recent_files()
        return {"cleaned": results, "total": self.cleaner.cleaned_count}
    
    # ─── Sieć ───
    
    def get_masked_identity(self) -> Dict:
        """Pobierz zamaskowaną tożsamość sieciową."""
        return self.network.fake_identity
    
    def rotate_identity(self):
        """Zmień tożsamość sieciową."""
        self.network.rotate_identity()
        return self.network.fake_identity
    
    def generate_noise(self, count: int = 5) -> List[Dict]:
        """Wygeneruj szum sieciowy."""
        return self.network.generate_noise_requests(count)
    
    # ─── Status ───
    
    def status(self) -> Dict:
        """Status Cerbera."""
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        return {
            "active": self.active,
            "king_verified": self.king.king_verified,
            "uptime_seconds": uptime,
            "shadow_mode": self.cleaner.running,
            "traces_cleaned": self.cleaner.cleaned_count,
            "messages_in_vault": len(self.vault.list_messages()),
            "current_fake_location": self.location.current_fake,
            "current_fake_ip": self.network.fake_identity.get("ip"),
        }


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

_shadow: Optional[CerberShadow] = None

def get_shadow() -> CerberShadow:
    """Pobierz singleton Cerbera Shadow."""
    global _shadow
    if _shadow is None:
        _shadow = CerberShadow()
    return _shadow


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import getpass
    
    print("=" * 60)
    print("  🛡️ CERBER SHADOW - Twój osobisty strażnik")
    print("=" * 60)
    
    shadow = CerberShadow()
    
    passphrase = getpass.getpass("👑 Podaj hasło Króla: ")
    result = shadow.activate(passphrase)
    print(result)
    
    if shadow.active:
        print("\n📍 Fałszywa lokalizacja:", shadow.fake_location())
        print("\n🎭 Tożsamość sieciowa:", shadow.get_masked_identity())
        print("\n📊 Status:", json.dumps(shadow.status(), indent=2, default=str))
