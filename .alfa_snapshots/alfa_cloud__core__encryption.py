"""
🔐 ALFA CLOUD ENCRYPTION
Szyfrowanie AES-256-GCM dla chmury offline
"""

import os
import hashlib
import secrets
import base64
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
import logging

# Próbuj importować cryptography, jeśli nie ma - fallback
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("⚠️ cryptography nie zainstalowane - używam fallback base64")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA CLASSES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class EncryptedData:
    """Zaszyfrowane dane"""
    ciphertext: bytes
    nonce: bytes
    salt: bytes
    tag: bytes


@dataclass
class KeyInfo:
    """Informacje o kluczu"""
    key_hash: str
    salt: bytes
    created_at: str
    algorithm: str = "AES-256-GCM"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENCRYPTION ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EncryptionEngine:
    """
    🔐 Silnik szyfrowania dla ALFA CLOUD OFFLINE
    
    Algorytmy:
    - AES-256-GCM: Szyfrowanie symetryczne
    - Argon2id: Derivacja klucza z hasła
    - BLAKE2b: Hashing
    """
    
    # Stałe
    KEY_SIZE = 32  # 256 bitów
    NONCE_SIZE = 12  # 96 bitów dla GCM
    SALT_SIZE = 16  # 128 bitów
    TAG_SIZE = 16  # 128 bitów
    
    def __init__(self, key_path: Optional[str] = None):
        self.logger = logging.getLogger("ALFA_CLOUD.Encryption")
        self.key_path = Path(key_path) if key_path else None
        self._master_key: Optional[bytes] = None
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # KEY MANAGEMENT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def generate_key(self) -> bytes:
        """Generuje losowy klucz AES-256"""
        return secrets.token_bytes(self.KEY_SIZE)
    
    def derive_key(self, password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        Derywuje klucz z hasła używając Argon2id
        
        Returns:
            Tuple[key, salt]
        """
        if salt is None:
            salt = secrets.token_bytes(self.SALT_SIZE)
        
        if CRYPTO_AVAILABLE:
            # Argon2id z cryptography
            kdf = Argon2id(
                salt=salt,
                length=self.KEY_SIZE,
                iterations=3,
                lanes=4,
                memory_cost=65536  # 64 MB
            )
            key = kdf.derive(password.encode('utf-8'))
        else:
            # Fallback: PBKDF2-like z hashlib
            key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                iterations=100000,
                dklen=self.KEY_SIZE
            )
        
        return key, salt
    
    def set_master_key(self, key: bytes):
        """Ustawia główny klucz"""
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"Klucz musi mieć {self.KEY_SIZE} bajtów")
        self._master_key = key
    
    def set_master_password(self, password: str, salt: Optional[bytes] = None) -> bytes:
        """Ustawia główny klucz z hasła"""
        key, salt = self.derive_key(password, salt)
        self._master_key = key
        return salt
    
    def save_key(self, path: str, password: Optional[str] = None):
        """Zapisuje klucz do pliku (opcjonalnie zaszyfrowany hasłem)"""
        if not self._master_key:
            raise ValueError("Brak klucza do zapisania")
        
        key_data = self._master_key
        
        if password:
            # Szyfruj klucz hasłem
            enc_key, salt = self.derive_key(password)
            encrypted = self._encrypt_raw(key_data, enc_key)
            
            # Format: SALT + NONCE + CIPHERTEXT
            key_data = salt + encrypted.nonce + encrypted.ciphertext
        
        Path(path).write_bytes(key_data)
        self.logger.info(f"🔑 Klucz zapisany: {path}")
    
    def load_key(self, path: str, password: Optional[str] = None):
        """Ładuje klucz z pliku"""
        key_data = Path(path).read_bytes()
        
        if password:
            # Odszyfruj klucz hasłem
            salt = key_data[:self.SALT_SIZE]
            nonce = key_data[self.SALT_SIZE:self.SALT_SIZE + self.NONCE_SIZE]
            ciphertext = key_data[self.SALT_SIZE + self.NONCE_SIZE:]
            
            enc_key, _ = self.derive_key(password, salt)
            key_data = self._decrypt_raw(ciphertext, nonce, enc_key)
        
        self._master_key = key_data
        self.logger.info(f"🔑 Klucz załadowany: {path}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ENCRYPTION / DECRYPTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def encrypt(self, plaintext: bytes, key: Optional[bytes] = None) -> bytes:
        """
        Szyfruje dane
        
        Format wyjściowy: NONCE (12B) + CIPHERTEXT (len(plaintext) + 16B tag)
        """
        key = key or self._master_key
        if not key:
            raise ValueError("Brak klucza szyfrującego")
        
        encrypted = self._encrypt_raw(plaintext, key)
        
        # Połącz nonce + ciphertext
        return encrypted.nonce + encrypted.ciphertext
    
    def decrypt(self, ciphertext: bytes, key: Optional[bytes] = None) -> bytes:
        """
        Deszyfruje dane
        
        Format wejściowy: NONCE (12B) + CIPHERTEXT
        """
        key = key or self._master_key
        if not key:
            raise ValueError("Brak klucza szyfrującego")
        
        # Rozdziel nonce i ciphertext
        nonce = ciphertext[:self.NONCE_SIZE]
        actual_ciphertext = ciphertext[self.NONCE_SIZE:]
        
        return self._decrypt_raw(actual_ciphertext, nonce, key)
    
    def _encrypt_raw(self, plaintext: bytes, key: bytes) -> EncryptedData:
        """Surowe szyfrowanie AES-256-GCM"""
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        
        if CRYPTO_AVAILABLE:
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        else:
            # Fallback: XOR + base64 (NIE BEZPIECZNE - tylko dla developmentu)
            self.logger.warning("⚠️ Używam fallback encryption - zainstaluj cryptography!")
            xored = bytes(a ^ b for a, b in zip(plaintext, (key * ((len(plaintext) // len(key)) + 1))[:len(plaintext)]))
            ciphertext = base64.b64encode(xored)
        
        return EncryptedData(
            ciphertext=ciphertext,
            nonce=nonce,
            salt=b"",
            tag=b""
        )
    
    def _decrypt_raw(self, ciphertext: bytes, nonce: bytes, key: bytes) -> bytes:
        """Surowe deszyfrowanie AES-256-GCM"""
        if CRYPTO_AVAILABLE:
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        else:
            # Fallback
            decoded = base64.b64decode(ciphertext)
            plaintext = bytes(a ^ b for a, b in zip(decoded, (key * ((len(decoded) // len(key)) + 1))[:len(decoded)]))
        
        return plaintext
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FILE OPERATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def encrypt_file(self, source_path: str, dest_path: Optional[str] = None,
                     key: Optional[bytes] = None) -> str:
        """
        Szyfruje plik
        """
        source = Path(source_path)
        dest = Path(dest_path) if dest_path else source.with_suffix(source.suffix + '.enc')
        
        plaintext = source.read_bytes()
        ciphertext = self.encrypt(plaintext, key)
        
        dest.write_bytes(ciphertext)
        self.logger.info(f"🔐 Zaszyfrowano: {source.name} → {dest.name}")
        
        return str(dest)
    
    def decrypt_file(self, source_path: str, dest_path: Optional[str] = None,
                     key: Optional[bytes] = None) -> str:
        """
        Deszyfruje plik
        """
        source = Path(source_path)
        
        if dest_path:
            dest = Path(dest_path)
        else:
            # Usuń .enc z nazwy
            if source.suffix == '.enc':
                dest = source.with_suffix('')
            else:
                dest = source.with_name(source.stem + '_decrypted' + source.suffix)
        
        ciphertext = source.read_bytes()
        plaintext = self.decrypt(ciphertext, key)
        
        dest.write_bytes(plaintext)
        self.logger.info(f"🔓 Odszyfrowano: {source.name} → {dest.name}")
        
        return str(dest)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # HASHING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    @staticmethod
    def hash_blake2b(data: bytes, digest_size: int = 32) -> str:
        """Hash BLAKE2b"""
        h = hashlib.blake2b(data, digest_size=digest_size)
        return h.hexdigest()
    
    @staticmethod
    def hash_sha256(data: bytes) -> str:
        """Hash SHA-256"""
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def hash_file(path: str, algorithm: str = 'blake2b') -> str:
        """Hash pliku"""
        with open(path, 'rb') as f:
            if algorithm == 'blake2b':
                h = hashlib.blake2b()
            else:
                h = hashlib.sha256()
            
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        
        return h.hexdigest()
    
    @staticmethod
    def verify_hash(data: bytes, expected_hash: str, algorithm: str = 'blake2b') -> bool:
        """Weryfikuje hash"""
        if algorithm == 'blake2b':
            actual = hashlib.blake2b(data).hexdigest()
        else:
            actual = hashlib.sha256(data).hexdigest()
        
        return secrets.compare_digest(actual, expected_hash)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECURE VAULT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SecureVault:
    """
    🏦 Bezpieczny vault dla wrażliwych danych
    
    Przechowuje:
    - API keys
    - Hasła
    - Tokeny
    - Certyfikaty
    """
    
    def __init__(self, vault_path: str, password: str):
        self.vault_path = Path(vault_path)
        self.encryption = EncryptionEngine()
        self._data: dict = {}
        
        # Inicjalizuj lub załaduj vault
        if self.vault_path.exists():
            self._load(password)
        else:
            self._init(password)
    
    def _init(self, password: str):
        """Inicjalizuje nowy vault"""
        self._salt = self.encryption.set_master_password(password)
        self._data = {}
        self._save()
    
    def _load(self, password: str):
        """Ładuje vault z dysku"""
        raw_data = self.vault_path.read_bytes()
        
        # Format: SALT (16B) + ENCRYPTED_DATA
        self._salt = raw_data[:16]
        encrypted_data = raw_data[16:]
        
        self.encryption.set_master_password(password, self._salt)
        
        decrypted = self.encryption.decrypt(encrypted_data)
        import json
        self._data = json.loads(decrypted.decode('utf-8'))
    
    def _save(self):
        """Zapisuje vault na dysk"""
        import json
        json_data = json.dumps(self._data).encode('utf-8')
        encrypted = self.encryption.encrypt(json_data)
        
        # Format: SALT + ENCRYPTED_DATA
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        self.vault_path.write_bytes(self._salt + encrypted)
    
    def set(self, key: str, value: str):
        """Zapisuje wartość w vault"""
        self._data[key] = value
        self._save()
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Pobiera wartość z vault"""
        return self._data.get(key, default)
    
    def delete(self, key: str):
        """Usuwa wartość z vault"""
        if key in self._data:
            del self._data[key]
            self._save()
    
    def list_keys(self) -> list:
        """Lista kluczy w vault"""
        return list(self._data.keys())
    
    def export(self, password: str) -> bytes:
        """Eksportuje vault (zaszyfrowany)"""
        import json
        json_data = json.dumps(self._data).encode('utf-8')
        
        key, salt = self.encryption.derive_key(password)
        encrypted = self.encryption.encrypt(json_data, key)
        
        return salt + encrypted


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    # Test encryption
    enc = EncryptionEngine()
    
    # Generuj klucz z hasła
    password = "MójTajnyKlucz123!"
    salt = enc.set_master_password(password)
    
    # Szyfruj dane
    plaintext = b"Tajne dane ALFA CLOUD"
    ciphertext = enc.encrypt(plaintext)
    
    print(f"📝 Original: {plaintext}")
    print(f"🔐 Encrypted: {ciphertext[:50]}...")
    
    # Deszyfruj
    decrypted = enc.decrypt(ciphertext)
    print(f"🔓 Decrypted: {decrypted}")
    
    # Hash
    hash_value = EncryptionEngine.hash_blake2b(plaintext)
    print(f"#️⃣ BLAKE2b: {hash_value}")
    
    print("\n✅ Encryption engine działa poprawnie!")
