"""
ALFA SECRET STORE v1.0
AES-256 encrypted key vault for API secrets.
Անdelays, մdelays կdelays (Bez opóźnień, bez kompromisów)

Chroni klucze API przed:
- Wyciekiem do logów
- Ekspozycją w .env
- Przypadkowym commitem
"""

import base64
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger("ALFA.SecretStore")

# Próbujemy użyć pycryptodome, fallback do prostszej metody
try:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("[SecretStore] pycryptodome not installed - using basic protection")


def mask_key(key: str, visible_chars: int = 4) -> str:
    """
    Maskuje klucz API dla bezpiecznego wyświetlania.
    
    Args:
        key: Pełny klucz API
        visible_chars: Ile znaków pokazać na początku i końcu
        
    Returns:
        Zamaskowany klucz: "AIza****Nd9Q"
    """
    if not key:
        return "[EMPTY]"
    if len(key) <= visible_chars * 2:
        return "*" * len(key)
    return key[:visible_chars] + "*" * (len(key) - visible_chars * 2) + key[-visible_chars:]


@dataclass
class SecretEntry:
    """Wpis w magazynie sekretów."""
    name: str
    encrypted_value: str
    provider: str = "unknown"
    created_at: str = ""


class SecretStore:
    """
    ALFA Bezpieczny Magazyn Kluczy API
    AES-256-EAX encryption with automatic key management.
    """
    
    def __init__(
        self,
        store_path: Optional[str] = None,
        master_key_path: Optional[str] = None
    ):
        """
        Inicjalizuje Secret Store.
        
        Args:
            store_path: Ścieżka do pliku z zaszyfrowanymi sekretami
            master_key_path: Ścieżka do klucza głównego
        """
        base_dir = Path(__file__).parent
        self.store_path = Path(store_path) if store_path else base_dir / "secrets.enc"
        self.key_path = Path(master_key_path) if master_key_path else base_dir / "master.key"
        
        self._master_key: Optional[bytes] = None
        self._secrets: Dict[str, SecretEntry] = {}
        
        if CRYPTO_AVAILABLE:
            self._ensure_master_key()
            self._load_secrets()
    
    def _ensure_master_key(self):
        """Upewnij się, że klucz główny istnieje."""
        if not CRYPTO_AVAILABLE:
            return
            
        if not self.key_path.exists():
            # Generuj nowy klucz AES-256 (32 bajty)
            key = get_random_bytes(32)
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            self.key_path.write_bytes(key)
            # Ustaw restrykcyjne uprawnienia (tylko właściciel)
            try:
                os.chmod(self.key_path, 0o600)
            except Exception:
                pass  # Windows może nie obsługiwać chmod
            logger.info(f"[SecretStore] Generated new master key: {self.key_path}")
        
        self._master_key = self.key_path.read_bytes()
    
    def _load_secrets(self):
        """Załaduj zaszyfrowane sekrety z dysku."""
        if not self.store_path.exists():
            self._secrets = {}
            return
        
        try:
            encrypted_data = self.store_path.read_text(encoding="utf-8")
            decrypted = self._decrypt_data(encrypted_data)
            data = json.loads(decrypted)
            self._secrets = {
                name: SecretEntry(**entry)
                for name, entry in data.items()
            }
            logger.info(f"[SecretStore] Loaded {len(self._secrets)} secrets")
        except Exception as e:
            logger.error(f"[SecretStore] Failed to load secrets: {e}")
            self._secrets = {}
    
    def _save_secrets(self):
        """Zapisz zaszyfrowane sekrety na dysk."""
        if not CRYPTO_AVAILABLE:
            logger.warning("[SecretStore] Cannot save - crypto not available")
            return
            
        data = {
            name: {
                "name": entry.name,
                "encrypted_value": entry.encrypted_value,
                "provider": entry.provider,
                "created_at": entry.created_at,
            }
            for name, entry in self._secrets.items()
        }
        
        encrypted = self._encrypt_data(json.dumps(data))
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(encrypted, encoding="utf-8")
        logger.info(f"[SecretStore] Saved {len(self._secrets)} secrets")
    
    def _encrypt_data(self, plaintext: str) -> str:
        """Szyfruje dane AES-256-EAX."""
        if not CRYPTO_AVAILABLE or not self._master_key:
            raise RuntimeError("Crypto not available")
        
        cipher = AES.new(self._master_key, AES.MODE_EAX)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
        
        # Pakujemy: nonce (16) + tag (16) + ciphertext
        payload = cipher.nonce + tag + ciphertext
        return base64.b64encode(payload).decode("ascii")
    
    def _decrypt_data(self, encoded: str) -> str:
        """Deszyfruje dane AES-256-EAX."""
        if not CRYPTO_AVAILABLE or not self._master_key:
            raise RuntimeError("Crypto not available")
        
        payload = base64.b64decode(encoded)
        nonce = payload[:16]
        tag = payload[16:32]
        ciphertext = payload[32:]
        
        cipher = AES.new(self._master_key, AES.MODE_EAX, nonce=nonce)
        data = cipher.decrypt_and_verify(ciphertext, tag)
        return data.decode("utf-8")
    
    def store_secret(self, name: str, value: str, provider: str = "unknown") -> bool:
        """
        Przechowuje zaszyfrowany sekret.
        
        Args:
            name: Nazwa sekretu (np. "GEMINI_API_KEY")
            value: Wartość do zaszyfrowania
            provider: Nazwa providera
            
        Returns:
            True jeśli sukces
        """
        if not CRYPTO_AVAILABLE:
            logger.warning(f"[SecretStore] Crypto not available, storing {mask_key(value)}")
            return False
        
        from datetime import datetime
        
        # Szyfruj samą wartość
        encrypted_value = self._encrypt_data(value)
        
        self._secrets[name] = SecretEntry(
            name=name,
            encrypted_value=encrypted_value,
            provider=provider,
            created_at=datetime.now().isoformat(),
        )
        
        self._save_secrets()
        logger.info(f"[SecretStore] Stored secret: {name} ({mask_key(value)})")
        return True
    
    def get_secret(self, name: str) -> Optional[str]:
        """
        Pobiera odszyfrowany sekret.
        
        Args:
            name: Nazwa sekretu
            
        Returns:
            Odszyfrowana wartość lub None
        """
        if not CRYPTO_AVAILABLE:
            # Fallback do zmiennej środowiskowej
            return os.environ.get(name)
        
        entry = self._secrets.get(name)
        if not entry:
            # Fallback do env
            return os.environ.get(name)
        
        try:
            return self._decrypt_data(entry.encrypted_value)
        except Exception as e:
            logger.error(f"[SecretStore] Failed to decrypt {name}: {e}")
            return None
    
    def delete_secret(self, name: str) -> bool:
        """Usuwa sekret z magazynu."""
        if name in self._secrets:
            del self._secrets[name]
            self._save_secrets()
            logger.info(f"[SecretStore] Deleted secret: {name}")
            return True
        return False
    
    def list_secrets(self) -> Dict[str, str]:
        """
        Lista wszystkich sekretów (zamaskowane wartości).
        
        Returns:
            Dict {name: masked_value}
        """
        result = {}
        for name, entry in self._secrets.items():
            try:
                value = self._decrypt_data(entry.encrypted_value)
                result[name] = mask_key(value)
            except Exception:
                result[name] = "[DECRYPT_ERROR]"
        return result
    
    def rotate_master_key(self) -> bool:
        """
        Rotuje klucz główny - odszyfruje wszystko starym, zaszyfruje nowym.
        Krytyczna operacja bezpieczeństwa.
        """
        if not CRYPTO_AVAILABLE:
            return False
        
        # Odszyfruj wszystkie sekrety starym kluczem
        plaintext_secrets = {}
        for name in self._secrets:
            value = self.get_secret(name)
            if value:
                plaintext_secrets[name] = (value, self._secrets[name].provider)
        
        # Generuj nowy klucz
        new_key = get_random_bytes(32)
        
        # Backup starego klucza
        backup_path = self.key_path.with_suffix(".key.bak")
        backup_path.write_bytes(self._master_key)
        
        # Zapisz nowy klucz
        self.key_path.write_bytes(new_key)
        self._master_key = new_key
        
        # Zaszyfruj ponownie wszystkie sekrety
        self._secrets = {}
        for name, (value, provider) in plaintext_secrets.items():
            self.store_secret(name, value, provider)
        
        logger.info("[SecretStore] Master key rotated successfully")
        return True


# === SINGLETON INSTANCE ===
_store_instance: Optional[SecretStore] = None


def get_secret_store() -> SecretStore:
    """Pobierz singleton instancję SecretStore."""
    global _store_instance
    if _store_instance is None:
        _store_instance = SecretStore()
    return _store_instance


# === UTILITY FUNCTIONS ===
def get_api_key(name: str) -> Optional[str]:
    """
    Pobiera klucz API bezpiecznie.
    Najpierw sprawdza SecretStore, potem env.
    """
    store = get_secret_store()
    return store.get_secret(name)


def store_api_key(name: str, value: str, provider: str = "unknown") -> bool:
    """Zapisuje klucz API w bezpiecznym magazynie."""
    store = get_secret_store()
    return store.store_secret(name, value, provider)


# === CLI ===
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    print("[ALFA SecretStore v1.0]")
    print(f"Crypto available: {CRYPTO_AVAILABLE}")
    
    store = SecretStore()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "list":
            secrets = store.list_secrets()
            for name, masked in secrets.items():
                print(f"  {name}: {masked}")
                
        elif cmd == "store" and len(sys.argv) >= 4:
            name, value = sys.argv[2], sys.argv[3]
            provider = sys.argv[4] if len(sys.argv) > 4 else "cli"
            if store.store_secret(name, value, provider):
                print(f"[OK] Stored: {name} = {mask_key(value)}")
            else:
                print("[FAIL] Could not store secret")
                
        elif cmd == "get" and len(sys.argv) >= 3:
            name = sys.argv[2]
            value = store.get_secret(name)
            if value:
                print(f"{name} = {mask_key(value)}")
            else:
                print(f"[NOT FOUND] {name}")
                
        elif cmd == "rotate":
            if store.rotate_master_key():
                print("[OK] Master key rotated")
            else:
                print("[FAIL] Could not rotate")
        else:
            print("Usage: secret_store.py [list|store|get|rotate] [args]")
    else:
        print("\nCommands:")
        print("  list              - Show all secrets (masked)")
        print("  store NAME VALUE  - Store a secret")
        print("  get NAME          - Get a secret (masked)")
        print("  rotate            - Rotate master key")
