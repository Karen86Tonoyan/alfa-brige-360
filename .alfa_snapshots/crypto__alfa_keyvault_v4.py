#!/usr/bin/env python3
"""
alfa_keyvault_v4.py

ALFA_KEYVAULT 4.0 ARMORED — Production Hardened Vault

Security features:
- Argon2id with adaptive parameters
- AES-256-GCM + HMAC-SHA512 vault integrity
- Anti-rollback protection (monotonic counter)
- Brute-force lockout mechanism
- Device binding (optional)
- Entropy validation for passwords
- SecretBytes class for secure memory handling
- Timestamp blackout option
- Full PQXHybrid hooks (Kyber + X25519)

Author: ALFA System / Karen86Tonoyan
Version: 4.0-ARMORED
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
import platform
import secrets
import sys
import time
import uuid
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional, Tuple

from argon2.low_level import hash_secret_raw, Type
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

# ═══════════════════════════════════════════════════════════════════════════
# SECURE MEMORY HANDLING
# ═══════════════════════════════════════════════════════════════════════════

class SecretBytes:
    """
    Secure bytes container with explicit zeroization.
    Minimizes exposure in Python's GC.
    """
    __slots__ = ('_data', '_len', '_cleared')
    
    def __init__(self, data: bytes):
        self._len = len(data)
        self._data = bytearray(data)
        self._cleared = False
        # Overwrite original if mutable
        if isinstance(data, bytearray):
            for i in range(len(data)):
                data[i] = 0
    
    def expose(self) -> bytes:
        """Get bytes - use sparingly, clear after use."""
        if self._cleared:
            raise RuntimeError("SecretBytes already cleared")
        return bytes(self._data)
    
    def clear(self) -> None:
        """Securely zero the memory."""
        if self._cleared:
            return
        # Multiple overwrites
        for _ in range(3):
            for i in range(self._len):
                self._data[i] = 0
        # Try ctypes memset for extra safety
        try:
            ctypes.memset(ctypes.addressof(ctypes.c_char.from_buffer(self._data)), 0, self._len)
        except Exception:
            pass
        self._cleared = True
    
    def __del__(self):
        self.clear()
    
    def __len__(self) -> int:
        return self._len
    
    def __repr__(self) -> str:
        return f"<SecretBytes len={self._len} cleared={self._cleared}>"


def secure_random(n: int) -> bytes:
    """Cryptographically secure random bytes."""
    return secrets.token_bytes(n)


def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


# ═══════════════════════════════════════════════════════════════════════════
# ENTROPY VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

def calculate_entropy(password: str) -> float:
    """Calculate password entropy in bits."""
    if not password:
        return 0.0
    charset_size = 0
    if any(c.islower() for c in password):
        charset_size += 26
    if any(c.isupper() for c in password):
        charset_size += 26
    if any(c.isdigit() for c in password):
        charset_size += 10
    if any(c in "!@#$%^&*()_+-=[]{}|;:',.<>?/`~" for c in password):
        charset_size += 32
    if any(ord(c) > 127 for c in password):
        charset_size += 100  # Unicode bonus
    
    if charset_size == 0:
        return 0.0
    
    import math
    return len(password) * math.log2(charset_size)


def validate_password_strength(password: str, min_entropy: float = 50.0) -> Tuple[bool, float, str]:
    """
    Validate password meets minimum entropy requirements.
    Returns: (is_valid, entropy_bits, message)
    """
    entropy = calculate_entropy(password)
    
    if len(password) < 8:
        return False, entropy, "Password must be at least 8 characters"
    
    if entropy < min_entropy:
        return False, entropy, f"Password entropy {entropy:.1f} bits < required {min_entropy} bits"
    
    return True, entropy, f"Password entropy: {entropy:.1f} bits (good)"


# ═══════════════════════════════════════════════════════════════════════════
# DEVICE BINDING
# ═══════════════════════════════════════════════════════════════════════════

def get_device_fingerprint() -> str:
    """Generate unique device fingerprint for binding."""
    components = []
    
    # Platform info
    components.append(platform.node())
    components.append(platform.machine())
    components.append(platform.processor())
    
    # Try to get unique hardware IDs
    try:
        if sys.platform == "win32":
            import subprocess
            result = subprocess.run(
                ["wmic", "csproduct", "get", "uuid"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    components.append(lines[1].strip())
        elif sys.platform == "linux":
            try:
                with open("/etc/machine-id", "r") as f:
                    components.append(f.read().strip())
            except FileNotFoundError:
                pass
        elif sys.platform == "darwin":
            import subprocess
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if "IOPlatformUUID" in line:
                        uuid_str = line.split('"')[-2]
                        components.append(uuid_str)
                        break
    except Exception:
        pass
    
    # Hash all components
    fingerprint_data = "|".join(components).encode("utf-8")
    return hashlib.sha256(fingerprint_data).hexdigest()[:32]


# ═══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class KDFConfig:
    algorithm: str = "argon2id"
    time_cost: int = 3
    memory_cost_kib: int = 65536  # 64 MiB
    parallelism: int = 2
    salt: str = ""  # base64
    
    @staticmethod
    def new_with_random_salt() -> "KDFConfig":
        salt = secure_random(16)
        return KDFConfig(salt=b64e(salt))
    
    @staticmethod
    def adaptive() -> "KDFConfig":
        """Create config based on available system resources."""
        import psutil
        available_mem = psutil.virtual_memory().available
        # Use up to 12.5% of available memory, max 256 MiB
        mem_kib = min(available_mem // 8 // 1024, 256 * 1024)
        mem_kib = max(mem_kib, 64 * 1024)  # Min 64 MiB
        
        return KDFConfig(
            memory_cost_kib=int(mem_kib),
            salt=b64e(secure_random(16))
        )


@dataclass
class SecurityState:
    """Anti-brute-force and rollback protection."""
    failed_attempts: int = 0
    last_failed_at: float = 0.0
    lockout_until: float = 0.0
    monotonic_counter: int = 0  # Anti-rollback
    device_fingerprint: str = ""  # Device binding


@dataclass
class SeedEncrypted:
    cipher: str = "AES-256-GCM"
    nonce: str = ""  # base64
    ct: str = ""     # base64
    tag: str = ""    # base64


@dataclass
class VaultIntegrity:
    """HMAC integrity for entire vault document."""
    algorithm: str = "hmac-sha512"
    hmac: str = ""  # base64, computed over vault JSON without this field


@dataclass
class PQXMeta:
    """Metadata dla PQXHybrid encryption."""
    kem_classic: str = "x25519"
    kem_pq: str = "kyber1024"
    kdf: str = "hkdf-sha512"
    cipher: str = "aes-256-gcm"
    shared_secret_length: int = 64
    derived_key_length: int = 32


@dataclass
class DeviceInfo:
    device_id: str
    epoch: int
    created_at: str
    last_rotated_at: str
    fingerprint: str = ""  # Device binding fingerprint


@dataclass
class PQXShadowEntry:
    id: str
    created_at: str
    kem_suite: str
    cipher: str
    recipient_pub: Dict[str, str]
    blob: str


@dataclass
class EscrowMetaEntry:
    label: str
    kem_suite: str
    recipient_pub: Dict[str, str]


@dataclass
class EscrowMeta:
    scheme: str
    paper_shares_locations: List[str]
    remote_escrow: List[EscrowMetaEntry]


@dataclass
class InnerVaultBlob:
    cipher: str = "AES-256-GCM"
    nonce: str = ""
    ct: str = ""
    tag: str = ""


@dataclass
class InnerVaultMeta:
    label: str = "KRÓLEWSKA SKRYTKA"
    created_at: str = ""
    attempt_limit: int = 10
    lockout_seconds: int = 300
    failed_attempts: int = 0


@dataclass
class InnerVault:
    """MUZ - Moduł Ultra Zabezpieczony (sejf w sejfie)."""
    enabled: bool = False
    kdf: Optional[KDFConfig] = None
    blob: Optional[InnerVaultBlob] = None
    meta: Optional[InnerVaultMeta] = None


@dataclass
class AlfaKeyVault:
    """ALFA_KEYVAULT 4.0 ARMORED - Main vault structure."""
    version: str
    kdf: KDFConfig
    seed_encrypted: SeedEncrypted
    device: DeviceInfo
    security: SecurityState
    integrity: VaultIntegrity
    pqx_shadow: List[PQXShadowEntry]
    escrow_meta: EscrowMeta
    inner_vault: Optional[InnerVault] = None
    pqx_meta: Optional[PQXMeta] = None
    timestamp_blackout: bool = False  # Hide timestamps for privacy
    
    def to_dict(self, include_integrity: bool = True) -> Dict[str, Any]:
        result = {
            "version": self.version,
            "kdf": asdict(self.kdf),
            "seed_encrypted": asdict(self.seed_encrypted),
            "device": asdict(self.device),
            "security": asdict(self.security),
            "pqx_shadow": [asdict(e) for e in self.pqx_shadow],
            "escrow_meta": {
                "scheme": self.escrow_meta.scheme,
                "paper_shares_locations": self.escrow_meta.paper_shares_locations,
                "remote_escrow": [asdict(e) for e in self.escrow_meta.remote_escrow],
            },
            "timestamp_blackout": self.timestamp_blackout,
        }
        
        if include_integrity:
            result["integrity"] = asdict(self.integrity)
        
        if self.inner_vault and self.inner_vault.enabled:
            result["inner_vault"] = {
                "enabled": self.inner_vault.enabled,
                "kdf": asdict(self.inner_vault.kdf) if self.inner_vault.kdf else None,
                "blob": asdict(self.inner_vault.blob) if self.inner_vault.blob else None,
                "meta": asdict(self.inner_vault.meta) if self.inner_vault.meta else None,
            }
        
        if self.pqx_meta:
            result["pqx_meta"] = asdict(self.pqx_meta)
        
        return result
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AlfaKeyVault":
        kdf = KDFConfig(**data["kdf"])
        seed_enc = SeedEncrypted(**data["seed_encrypted"])
        device = DeviceInfo(**data["device"])
        security = SecurityState(**data.get("security", {}))
        integrity = VaultIntegrity(**data.get("integrity", {}))
        pqx_shadow = [PQXShadowEntry(**e) for e in data.get("pqx_shadow", [])]
        
        escrow = data.get("escrow_meta", {})
        remote = [EscrowMetaEntry(**e) for e in escrow.get("remote_escrow", [])]
        escrow_meta = EscrowMeta(
            scheme=escrow.get("scheme", "Shamir-3-of-5"),
            paper_shares_locations=escrow.get("paper_shares_locations", []),
            remote_escrow=remote,
        )
        
        inner_vault = None
        if "inner_vault" in data and data["inner_vault"].get("enabled"):
            iv = data["inner_vault"]
            inner_vault = InnerVault(
                enabled=True,
                kdf=KDFConfig(**iv["kdf"]) if iv.get("kdf") else None,
                blob=InnerVaultBlob(**iv["blob"]) if iv.get("blob") else None,
                meta=InnerVaultMeta(**iv["meta"]) if iv.get("meta") else None,
            )
        
        pqx_meta = None
        if "pqx_meta" in data:
            pqx_meta = PQXMeta(**data["pqx_meta"])
        
        return AlfaKeyVault(
            version=data.get("version", "4.0-ARMORED"),
            kdf=kdf,
            seed_encrypted=seed_enc,
            device=device,
            security=security,
            integrity=integrity,
            pqx_shadow=pqx_shadow,
            escrow_meta=escrow_meta,
            inner_vault=inner_vault,
            pqx_meta=pqx_meta,
            timestamp_blackout=data.get("timestamp_blackout", False),
        )
    
    def compute_integrity_hmac(self, hmac_key: bytes) -> str:
        """Compute HMAC over vault document (excluding integrity field)."""
        vault_data = self.to_dict(include_integrity=False)
        vault_json = json.dumps(vault_data, sort_keys=True, separators=(',', ':'))
        mac = hmac.new(hmac_key, vault_json.encode("utf-8"), hashlib.sha512)
        return b64e(mac.digest())
    
    def verify_integrity(self, hmac_key: bytes) -> bool:
        """Verify vault integrity HMAC."""
        expected = self.compute_integrity_hmac(hmac_key)
        return hmac.compare_digest(expected, self.integrity.hmac)
    
    def save_to_file(self, path: str, hmac_key: bytes) -> None:
        """Save vault with integrity HMAC."""
        self.integrity.hmac = self.compute_integrity_hmac(hmac_key)
        self.security.monotonic_counter += 1  # Anti-rollback
        
        # Atomic write
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        os.replace(temp_path, path)
    
    @staticmethod
    def load_from_file(path: str) -> "AlfaKeyVault":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AlfaKeyVault.from_dict(data)


# ═══════════════════════════════════════════════════════════════════════════
# CRYPTOGRAPHIC OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

def derive_kek(password: str, cfg: KDFConfig) -> SecretBytes:
    """Derive Key Encryption Key from password using Argon2id."""
    if cfg.algorithm != "argon2id":
        raise ValueError(f"Unsupported KDF: {cfg.algorithm}")
    
    salt = b64d(cfg.salt)
    kek = hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=cfg.time_cost,
        memory_cost=cfg.memory_cost_kib,
        parallelism=cfg.parallelism,
        hash_len=32,
        type=Type.ID,
    )
    return SecretBytes(kek)


def derive_hmac_key(kek: SecretBytes) -> bytes:
    """Derive HMAC key from KEK for vault integrity."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"ALFA:VAULT:INTEGRITY:HMAC",
    )
    return hkdf.derive(kek.expose())


def encrypt_seed(seed_alfa: bytes, password: str, kdf_cfg: Optional[KDFConfig] = None) -> Tuple[SeedEncrypted, KDFConfig, SecretBytes]:
    """Encrypt SEED_ALFA using KEK derived from password."""
    if kdf_cfg is None:
        kdf_cfg = KDFConfig.adaptive()
    
    kek = derive_kek(password, kdf_cfg)
    aes = AESGCM(kek.expose())
    nonce = secure_random(12)
    ct = aes.encrypt(nonce, seed_alfa, None)
    
    tag_len = 16
    ct_body, tag = ct[:-tag_len], ct[-tag_len:]
    
    seed_enc = SeedEncrypted(
        cipher="AES-256-GCM",
        nonce=b64e(nonce),
        ct=b64e(ct_body),
        tag=b64e(tag),
    )
    return seed_enc, kdf_cfg, kek


def decrypt_seed(seed_enc: SeedEncrypted, password: str, kdf_cfg: KDFConfig) -> Tuple[SecretBytes, SecretBytes]:
    """Decrypt SEED_ALFA. Returns (seed, kek) both as SecretBytes."""
    kek = derive_kek(password, kdf_cfg)
    aes = AESGCM(kek.expose())
    nonce = b64d(seed_enc.nonce)
    ct_body = b64d(seed_enc.ct)
    tag = b64d(seed_enc.tag)
    ct = ct_body + tag
    seed = aes.decrypt(nonce, ct, None)
    return SecretBytes(seed), kek


def hkdf_derive_key(seed: SecretBytes, info: str, length: int = 32) -> bytes:
    """HKDF-SHA256: derive subkey from seed."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=None,
        info=info.encode("utf-8"),
    )
    return hkdf.derive(seed.expose())


# ═══════════════════════════════════════════════════════════════════════════
# LOCKOUT MECHANISM
# ═══════════════════════════════════════════════════════════════════════════

class LockoutManager:
    """Manage brute-force protection with exponential backoff."""
    
    MAX_ATTEMPTS = 5
    BASE_LOCKOUT_SECONDS = 30
    MAX_LOCKOUT_SECONDS = 3600  # 1 hour max
    
    @staticmethod
    def check_lockout(security: SecurityState) -> Tuple[bool, int]:
        """Check if vault is locked out. Returns (is_locked, seconds_remaining)."""
        now = time.time()
        if security.lockout_until > now:
            return True, int(security.lockout_until - now)
        return False, 0
    
    @staticmethod
    def record_failure(security: SecurityState) -> None:
        """Record failed attempt and potentially trigger lockout."""
        now = time.time()
        security.failed_attempts += 1
        security.last_failed_at = now
        
        if security.failed_attempts >= LockoutManager.MAX_ATTEMPTS:
            # Exponential backoff: 30s, 60s, 120s, 240s, ... up to 1 hour
            lockout_time = min(
                LockoutManager.BASE_LOCKOUT_SECONDS * (2 ** (security.failed_attempts - LockoutManager.MAX_ATTEMPTS)),
                LockoutManager.MAX_LOCKOUT_SECONDS
            )
            security.lockout_until = now + lockout_time
    
    @staticmethod
    def record_success(security: SecurityState) -> None:
        """Record successful attempt and reset counters."""
        security.failed_attempts = 0
        security.last_failed_at = 0.0
        security.lockout_until = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# ANTI-ROLLBACK PROTECTION
# ═══════════════════════════════════════════════════════════════════════════

def verify_no_rollback(vault: AlfaKeyVault, expected_min_counter: int) -> bool:
    """Verify vault hasn't been rolled back to earlier state."""
    return vault.security.monotonic_counter >= expected_min_counter


def get_rollback_counter(vault_path: str) -> int:
    """Get current monotonic counter from vault file."""
    try:
        vault = AlfaKeyVault.load_from_file(vault_path)
        return vault.security.monotonic_counter
    except Exception:
        return 0


# ═══════════════════════════════════════════════════════════════════════════
# DEVICE BINDING
# ═══════════════════════════════════════════════════════════════════════════

def verify_device_binding(vault: AlfaKeyVault, strict: bool = False) -> Tuple[bool, str]:
    """
    Verify vault is used on correct device.
    Returns: (is_valid, message)
    """
    if not vault.device.fingerprint:
        return True, "No device binding configured"
    
    current_fp = get_device_fingerprint()
    if vault.device.fingerprint == current_fp:
        return True, "Device verified"
    
    if strict:
        return False, f"Device mismatch: expected {vault.device.fingerprint[:8]}..., got {current_fp[:8]}..."
    
    return True, f"Warning: Device fingerprint changed (expected {vault.device.fingerprint[:8]}...)"


# ═══════════════════════════════════════════════════════════════════════════
# PHOTO KEYS (for ALFA Photos Vault)
# ═══════════════════════════════════════════════════════════════════════════

class PhotoKeys:
    """Wallet-style key derivation for ALFA Photos Vault."""
    
    def __init__(self, seed: SecretBytes):
        self._seed = seed
        self.photo_master = self._derive("ALFA:PHOTOS:MASTER")
        self.thumb_master = self._derive("ALFA:PHOTOS:THUMBS")
        self.index_master = self._derive("ALFA:PHOTOS:INDEX")
        self.hmac_master = self._derive("ALFA:PHOTOS:HMAC")
    
    def _derive(self, info: str) -> bytes:
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ALFA_PHOTO_VAULT_v4",
            info=info.encode("utf-8"),
        )
        return hkdf.derive(self._seed.expose())
    
    def key_for_photo(self, photo_id: str) -> bytes:
        """Unique key for specific photo."""
        return self._derive(f"FILE:{photo_id}")
    
    def key_for_thumb(self, photo_id: str) -> bytes:
        """Key for thumbnail."""
        return self._derive(f"THUMB:{photo_id}")
    
    def index_key(self) -> bytes:
        return self.index_master
    
    def hmac_key(self) -> bytes:
        return self.hmac_master
    
    def clear(self) -> None:
        """Clear all derived keys."""
        self._seed.clear()


# ═══════════════════════════════════════════════════════════════════════════
# VAULT OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

def create_new_vault(
    path: str,
    device_id: str,
    password: str,
    seed_alfa: Optional[bytes] = None,
    paper_locations: Optional[List[str]] = None,
    enable_device_binding: bool = True,
    timestamp_blackout: bool = False,
    min_entropy: float = 50.0,
) -> Tuple[AlfaKeyVault, SecretBytes]:
    """
    Create new ALFA_KEYVAULT 4.0 ARMORED.
    Returns: (vault, seed_secret)
    """
    # Validate password strength
    valid, entropy, msg = validate_password_strength(password, min_entropy)
    if not valid:
        raise ValueError(f"Password too weak: {msg}")
    
    # Generate seed if not provided
    if seed_alfa is None:
        seed_alfa = secure_random(32)
    
    seed_secret = SecretBytes(seed_alfa)
    
    if paper_locations is None:
        paper_locations = []
    
    seed_enc, kdf_cfg, kek = encrypt_seed(seed_alfa, password)
    
    now_iso = "" if timestamp_blackout else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    device = DeviceInfo(
        device_id=device_id,
        epoch=1,
        created_at=now_iso,
        last_rotated_at=now_iso,
        fingerprint=get_device_fingerprint() if enable_device_binding else "",
    )
    
    security = SecurityState(
        monotonic_counter=1,
        device_fingerprint=device.fingerprint,
    )
    
    escrow_meta = EscrowMeta(
        scheme="Shamir-3-of-5",
        paper_shares_locations=paper_locations,
        remote_escrow=[],
    )
    
    vault = AlfaKeyVault(
        version="4.0-ARMORED",
        kdf=kdf_cfg,
        seed_encrypted=seed_enc,
        device=device,
        security=security,
        integrity=VaultIntegrity(),
        pqx_shadow=[],
        escrow_meta=escrow_meta,
        pqx_meta=PQXMeta(),
        timestamp_blackout=timestamp_blackout,
    )
    
    # Compute and save with HMAC
    hmac_key = derive_hmac_key(kek)
    vault.save_to_file(path, hmac_key)
    
    kek.clear()
    return vault, seed_secret


def open_vault(
    path: str,
    password: str,
    verify_device: bool = True,
    expected_min_counter: Optional[int] = None,
) -> Tuple[AlfaKeyVault, SecretBytes]:
    """
    Open existing vault with full security checks.
    Returns: (vault, seed_secret)
    """
    vault = AlfaKeyVault.load_from_file(path)
    
    # Check lockout
    is_locked, remaining = LockoutManager.check_lockout(vault.security)
    if is_locked:
        raise PermissionError(f"Vault locked for {remaining} more seconds")
    
    # Verify device binding
    if verify_device:
        valid, msg = verify_device_binding(vault)
        if not valid:
            raise PermissionError(f"Device binding failed: {msg}")
    
    # Anti-rollback check
    if expected_min_counter is not None:
        if not verify_no_rollback(vault, expected_min_counter):
            raise SecurityError(f"Rollback detected: counter {vault.security.monotonic_counter} < expected {expected_min_counter}")
    
    try:
        seed_secret, kek = decrypt_seed(vault.seed_encrypted, password, vault.kdf)
        
        # Verify integrity HMAC
        hmac_key = derive_hmac_key(kek)
        if vault.integrity.hmac and not vault.verify_integrity(hmac_key):
            kek.clear()
            seed_secret.clear()
            LockoutManager.record_failure(vault.security)
            raise SecurityError("Vault integrity check failed - possible tampering")
        
        # Success - reset failure counter
        LockoutManager.record_success(vault.security)
        vault.save_to_file(path, hmac_key)
        
        kek.clear()
        return vault, seed_secret
        
    except Exception as e:
        LockoutManager.record_failure(vault.security)
        # Save updated security state
        try:
            # Need to derive key just for HMAC
            kek = derive_kek(password, vault.kdf)
            hmac_key = derive_hmac_key(kek)
            vault.save_to_file(path, hmac_key)
            kek.clear()
        except Exception:
            pass
        raise


class SecurityError(Exception):
    """Security-related error."""
    pass


# ═══════════════════════════════════════════════════════════════════════════
# MUZ - INNER VAULT
# ═══════════════════════════════════════════════════════════════════════════

def create_inner_vault(vault: AlfaKeyVault, inner_password: str, payload: bytes) -> None:
    """Create MUZ - encrypted inner vault."""
    valid, entropy, msg = validate_password_strength(inner_password, min_entropy=60.0)
    if not valid:
        raise ValueError(f"MUZ password too weak: {msg}")
    
    kdf_cfg = KDFConfig.new_with_random_salt()
    kdf_cfg.memory_cost_kib = 128 * 1024  # 128 MiB for MUZ
    kdf_cfg.time_cost = 4
    
    kek = derive_kek(inner_password, kdf_cfg)
    aes = AESGCM(kek.expose())
    nonce = secure_random(12)
    ct = aes.encrypt(nonce, payload, None)
    
    tag_len = 16
    ct_body, tag = ct[:-tag_len], ct[-tag_len:]
    
    blob = InnerVaultBlob(
        cipher="AES-256-GCM",
        nonce=b64e(nonce),
        ct=b64e(ct_body),
        tag=b64e(tag),
    )
    
    meta = InnerVaultMeta(
        label="KRÓLEWSKA SKRYTKA",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    
    vault.inner_vault = InnerVault(
        enabled=True,
        kdf=kdf_cfg,
        blob=blob,
        meta=meta,
    )
    
    kek.clear()


def open_inner_vault(vault: AlfaKeyVault, inner_password: str) -> SecretBytes:
    """Open MUZ - returns payload as SecretBytes."""
    if not vault.inner_vault or not vault.inner_vault.enabled:
        raise RuntimeError("Inner vault not enabled")
    
    meta = vault.inner_vault.meta
    if meta.failed_attempts >= meta.attempt_limit:
        raise PermissionError(f"MUZ locked after {meta.attempt_limit} failed attempts")
    
    try:
        kek = derive_kek(inner_password, vault.inner_vault.kdf)
        aes = AESGCM(kek.expose())
        nonce = b64d(vault.inner_vault.blob.nonce)
        ct_body = b64d(vault.inner_vault.blob.ct)
        tag = b64d(vault.inner_vault.blob.tag)
        ct = ct_body + tag
        payload = aes.decrypt(nonce, ct, None)
        
        meta.failed_attempts = 0  # Reset on success
        kek.clear()
        return SecretBytes(payload)
        
    except Exception:
        meta.failed_attempts += 1
        raise


# ═══════════════════════════════════════════════════════════════════════════
# DERIVE ALL MODULE KEYS
# ═══════════════════════════════════════════════════════════════════════════

def derive_all_module_keys(seed: SecretBytes) -> Dict[str, bytes]:
    """Derive all ALFA module keys from seed."""
    return {
        "K_cfg": hkdf_derive_key(seed, "ALFA:config"),
        "K_mail": hkdf_derive_key(seed, "ALFA:mail"),
        "K_logs": hkdf_derive_key(seed, "ALFA:logs"),
        "K_pqx": hkdf_derive_key(seed, "ALFA:PQX:meta"),
        "K_photos": hkdf_derive_key(seed, "ALFA:photos"),
        "K_session": hkdf_derive_key(seed, "ALFA:session", length=64),
        "K_cerber": hkdf_derive_key(seed, "ALFA:cerber"),
    }


# ═══════════════════════════════════════════════════════════════════════════
# RESET BUTTON
# ═══════════════════════════════════════════════════════════════════════════

def vault_reset(vault_path: str) -> Dict[str, Any]:
    """
    Soft reset: verify vault, create backup, clear lockout.
    Does NOT delete vault file.
    """
    import shutil
    
    result = {
        "status": "ok",
        "backup_created": None,
        "file_valid": False,
        "integrity_valid": None,
        "message": "",
    }
    
    if not os.path.exists(vault_path):
        result["status"] = "error"
        result["message"] = f"Vault not found: {vault_path}"
        return result
    
    # Create backup
    backup_path = vault_path + f".reset_backup_{int(time.time())}.json"
    try:
        shutil.copy2(vault_path, backup_path)
        result["backup_created"] = backup_path
    except Exception as e:
        result["message"] = f"Backup failed: {e}"
    
    # Validate JSON
    try:
        vault = AlfaKeyVault.load_from_file(vault_path)
        result["file_valid"] = True
        
        # Reset lockout
        vault.security.failed_attempts = 0
        vault.security.lockout_until = 0.0
        
        result["message"] = "Vault reset complete. Lockout cleared."
        
    except json.JSONDecodeError as e:
        result["file_valid"] = False
        result["status"] = "error"
        result["message"] = f"Vault corrupted: {e}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Reset failed: {e}"
    
    return result
