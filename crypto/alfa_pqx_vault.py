#!/usr/bin/env python3
"""
alfa_pqx_vault.py

ALFA 3.0-PQX – Vault kryptograficzny z obsługą:
- Argon2id → KEK
- AES-256-GCM → szyfrowanie SEED_ALFA
- HKDF → klucze pochodne (K_cfg, K_mail, K_logs, K_pqx_meta)
- Hooki pod PQXHybrid (X25519 + Kyber1024)
- PhotoKeys dla ALFA Photos Vault
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional

from argon2.low_level import hash_secret_raw, Type
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


# ==========================
#  Helpers: kodowanie base64
# ==========================

def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


# ==========================
#  Struktury danych
# ==========================

@dataclass
class KDFConfig:
    algorithm: str = "argon2id"
    time_cost: int = 3
    memory_cost_kib: int = 64 * 1024
    parallelism: int = 2
    salt: str = ""  # base64

    @staticmethod
    def new_with_random_salt() -> "KDFConfig":
        salt = os.urandom(16)
        return KDFConfig(salt=b64e(salt))


@dataclass
class SeedEncrypted:
    cipher: str = "AES-256-GCM"
    nonce: str = ""  # base64
    ct: str = ""     # base64
    tag: str = ""    # base64


@dataclass
class PQXMeta:
    """Metadata dla PQXHybrid encryption"""
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


@dataclass
class InnerVault:
    """MUZ - Moduł Ultra Zabezpieczony (sejf w sejfie)"""
    enabled: bool = False
    kdf: Optional[KDFConfig] = None
    blob: Optional[InnerVaultBlob] = None
    meta: Optional[InnerVaultMeta] = None


@dataclass
class AlfaKeyVault:
    version: str
    kdf: KDFConfig
    seed_encrypted: SeedEncrypted
    device: DeviceInfo
    pqx_shadow: List[PQXShadowEntry]
    escrow_meta: EscrowMeta
    inner_vault: Optional[InnerVault] = None
    pqx_meta: Optional[PQXMeta] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "version": self.version,
            "kdf": asdict(self.kdf),
            "seed_encrypted": asdict(self.seed_encrypted),
            "device": asdict(self.device),
            "pqx_shadow": [asdict(e) for e in self.pqx_shadow],
            "escrow_meta": {
                "scheme": self.escrow_meta.scheme,
                "paper_shares_locations": self.escrow_meta.paper_shares_locations,
                "remote_escrow": [asdict(e) for e in self.escrow_meta.remote_escrow],
            },
        }
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
            version=data.get("version", "3.0-PQX"),
            kdf=kdf,
            seed_encrypted=seed_enc,
            device=device,
            pqx_shadow=pqx_shadow,
            escrow_meta=escrow_meta,
            inner_vault=inner_vault,
            pqx_meta=pqx_meta,
        )

    def save_to_file(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @staticmethod
    def load_from_file(path: str) -> "AlfaKeyVault":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AlfaKeyVault.from_dict(data)


# ==========================
#  Kryptografia: KDF / AES / HKDF
# ==========================

def derive_kek(password: str, cfg: KDFConfig) -> bytes:
    """Z hasła/PIN-u wyciąga 32-bajtowy KEK przy pomocy Argon2id."""
    if cfg.algorithm != "argon2id":
        raise ValueError(f"Unsupported KDF algorithm: {cfg.algorithm}")

    salt = b64d(cfg.salt)
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=cfg.time_cost,
        memory_cost=cfg.memory_cost_kib,
        parallelism=cfg.parallelism,
        hash_len=32,
        type=Type.ID,
    )


def encrypt_seed(seed_alfa: bytes, password: str, kdf_cfg: Optional[KDFConfig] = None) -> tuple[SeedEncrypted, KDFConfig]:
    """Szyfruje SEED_ALFA przy użyciu KEK wyprowadzonego z hasła."""
    if kdf_cfg is None:
        kdf_cfg = KDFConfig.new_with_random_salt()

    kek = derive_kek(password, kdf_cfg)
    aes = AESGCM(kek)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, seed_alfa, None)

    tag_len = 16
    ct_body, tag = ct[:-tag_len], ct[-tag_len:]

    seed_enc = SeedEncrypted(
        cipher="AES-256-GCM",
        nonce=b64e(nonce),
        ct=b64e(ct_body),
        tag=b64e(tag),
    )
    return seed_enc, kdf_cfg


def decrypt_seed(seed_enc: SeedEncrypted, password: str, kdf_cfg: KDFConfig) -> bytes:
    """Odszyfrowuje SEED_ALFA z obiektu SeedEncrypted."""
    kek = derive_kek(password, kdf_cfg)
    aes = AESGCM(kek)
    nonce = b64d(seed_enc.nonce)
    ct_body = b64d(seed_enc.ct)
    tag = b64d(seed_enc.tag)
    ct = ct_body + tag
    return aes.decrypt(nonce, ct, None)


def hkdf_derive_key(seed_alfa: bytes, info: str, length: int = 32) -> bytes:
    """HKDF-SHA256: wyprowadza klucz z SEED_ALFA dla danego kontekstu."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=None,
        info=info.encode("utf-8"),
    )
    return hkdf.derive(seed_alfa)


# ==========================
#  PhotoKeys - ALFA Photos Vault
# ==========================

class PhotoKeys:
    """Klucze dla ALFA Photos Vault - wallet-style key derivation"""
    
    def __init__(self, seed: bytes):
        self.photo_master = self._derive(seed, "ALFA:PHOTOS:MASTER")
        self.thumb_master = self._derive(seed, "ALFA:PHOTOS:THUMBS")
        self.index_master = self._derive(seed, "ALFA:PHOTOS:INDEX")
        self.hmac_master = self._derive(seed, "ALFA:PHOTOS:HMAC")
    
    def _derive(self, seed: bytes, info: str) -> bytes:
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ALFA_PHOTO_VAULT",
            info=info.encode("utf-8"),
        )
        return hkdf.derive(seed)
    
    def key_for_photo(self, photo_id: str) -> bytes:
        """Klucz jednorazowy do konkretnego zdjęcia"""
        return self._derive(self.photo_master, f"FILE:{photo_id}")
    
    def key_for_thumb(self, photo_id: str) -> bytes:
        """Klucz do miniatury"""
        return self._derive(self.thumb_master, f"THUMB:{photo_id}")
    
    def index_key(self) -> bytes:
        """Klucz indeksu (stały)"""
        return self.index_master
    
    def hmac_key(self) -> bytes:
        """Klucz HMAC (stały)"""
        return self.hmac_master


# ==========================
#  PQXHybrid – interfejs (hooki)
# ==========================

def pqx_kdf_shared_secret(x25519_ss: bytes, kyber_ss: bytes, context: str) -> bytes:
    """
    Prawidłowa kombinacja SharedSecret = HKDF(X25519_ss || Kyber_ss).
    Zamiast brać "pierwsze 32B", robimy HKDF na całości (64B).
    """
    raw = x25519_ss + kyber_ss
    hkdf = HKDF(
        algorithm=hashes.SHA512(),
        length=32,
        salt=None,
        info=context.encode("utf-8"),
    )
    return hkdf.derive(raw)


def pqx_encrypt_for_recipient(
    plaintext: bytes,
    recipient_pub_x25519: bytes,
    recipient_pub_kyber: bytes,
    context: str
) -> Dict[str, Any]:
    """Hook pod PQXHybrid encryption - do zaimplementowania z biblioteką PQ"""
    raise NotImplementedError("Implement PQXHybrid encryption using your PQ library.")


def pqx_decrypt_from_sender(
    blob: Dict[str, Any],
    recipient_priv_x25519: bytes,
    recipient_priv_kyber: bytes,
    context: str
) -> bytes:
    """Hook pod PQXHybrid decryption - do zaimplementowania z biblioteką PQ"""
    raise NotImplementedError("Implement PQXHybrid decryption using your PQ library.")


# ==========================
#  MUZ - Inner Vault (sejf w sejfie)
# ==========================

def create_inner_vault(vault: AlfaKeyVault, inner_password: str, payload: bytes) -> None:
    """Tworzy MUZ – zaszyfrowany wewnętrzny sejf."""
    kdf_cfg = KDFConfig.new_with_random_salt()
    kdf_cfg.memory_cost_kib = 128 * 1024  # mocniejszy KDF dla MUZ
    kdf_cfg.time_cost = 4
    
    kek = derive_kek(inner_password, kdf_cfg)
    aes = AESGCM(kek)
    nonce = os.urandom(12)
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
        attempt_limit=10,
        lockout_seconds=300,
    )

    vault.inner_vault = InnerVault(
        enabled=True,
        kdf=kdf_cfg,
        blob=blob,
        meta=meta,
    )


def open_inner_vault(vault: AlfaKeyVault, inner_password: str) -> bytes:
    """Otwiera MUZ – zwraca payload (bytes)."""
    if not vault.inner_vault or not vault.inner_vault.enabled:
        raise RuntimeError("Inner vault not enabled")

    kdf_cfg = vault.inner_vault.kdf
    kek = derive_kek(inner_password, kdf_cfg)
    aes = AESGCM(kek)
    nonce = b64d(vault.inner_vault.blob.nonce)
    ct_body = b64d(vault.inner_vault.blob.ct)
    tag = b64d(vault.inner_vault.blob.tag)
    ct = ct_body + tag
    return aes.decrypt(nonce, ct, None)


# ==========================
#  Tworzenie / ładowanie vaulta
# ==========================

def create_new_vault(
    path: str,
    device_id: str,
    password: str,
    seed_alfa: bytes,
    paper_locations: Optional[List[str]] = None
) -> AlfaKeyVault:
    """Tworzy nowy alfa_keyvault.json na dysku."""
    if paper_locations is None:
        paper_locations = []

    seed_enc, kdf_cfg = encrypt_seed(seed_alfa, password)

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    device = DeviceInfo(
        device_id=device_id,
        epoch=1,
        created_at=now_iso,
        last_rotated_at=now_iso,
    )

    escrow_meta = EscrowMeta(
        scheme="Shamir-3-of-5",
        paper_shares_locations=paper_locations,
        remote_escrow=[],
    )
    
    pqx_meta = PQXMeta()

    vault = AlfaKeyVault(
        version="3.0-PQX",
        kdf=kdf_cfg,
        seed_encrypted=seed_enc,
        device=device,
        pqx_shadow=[],
        escrow_meta=escrow_meta,
        pqx_meta=pqx_meta,
    )

    vault.save_to_file(path)
    return vault


def open_vault(path: str, password: str) -> tuple[AlfaKeyVault, bytes]:
    """Ładuje istniejący vault i odszyfrowuje SEED_ALFA w RAM."""
    vault = AlfaKeyVault.load_from_file(path)
    seed_alfa = decrypt_seed(vault.seed_encrypted, password, vault.kdf)
    return vault, seed_alfa


# ==========================
#  Rotacja epoch / shadow backup
# ==========================

def rotate_epoch(vault: AlfaKeyVault) -> None:
    """Zwiększa epoch dla urządzenia – przydatne przy rotacji kluczy."""
    vault.device.epoch += 1
    vault.device.last_rotated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def add_shadow_snapshot(
    vault: AlfaKeyVault,
    shadow_blob_b64: str,
    recipient_pub: Dict[str, str],
    kem_suite: str = "PQXHybrid-X25519+Kyber1024",
    cipher: str = "XChaCha20-Poly1305"
) -> None:
    """Dodaje wpis shadow backupu do vaulta."""
    entry = PQXShadowEntry(
        id=f"vault_shadow_{int(time.time())}",
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        kem_suite=kem_suite,
        cipher=cipher,
        recipient_pub=recipient_pub,
        blob=shadow_blob_b64,
    )
    vault.pqx_shadow.append(entry)


# ==========================
#  RESET - przycisk awaryjny
# ==========================

def vault_reset(vault_path: str) -> dict:
    """
    Soft reset sejfu: wyczyść cache, sprawdź zdrowie pliku.
    NIE usuwa pliku sejfu z dysku.
    """
    import shutil
    
    result = {
        "status": "ok",
        "backup_created": None,
        "file_valid": False,
        "message": ""
    }
    
    # Sprawdź czy plik istnieje
    if not os.path.exists(vault_path):
        result["status"] = "error"
        result["message"] = f"Vault not found: {vault_path}"
        return result
    
    # Utwórz backup przed resetem
    backup_path = vault_path + ".pre_reset.bak"
    try:
        shutil.copy2(vault_path, backup_path)
        result["backup_created"] = backup_path
    except Exception as e:
        result["message"] = f"Backup failed: {e}"
    
    # Sprawdź czy JSON jest poprawny
    try:
        with open(vault_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result["file_valid"] = True
        result["message"] = "Vault file is valid JSON. Reset complete."
    except json.JSONDecodeError as e:
        result["file_valid"] = False
        result["message"] = f"Vault file corrupted: {e}"
    
    return result


# ==========================
#  Derive all module keys
# ==========================

def derive_all_module_keys(seed_alfa: bytes) -> Dict[str, bytes]:
    """Wyprowadza wszystkie klucze modułowe z SEED_ALFA."""
    return {
        "K_cfg": hkdf_derive_key(seed_alfa, "ALFA:config"),
        "K_mail": hkdf_derive_key(seed_alfa, "ALFA:mail"),
        "K_logs": hkdf_derive_key(seed_alfa, "ALFA:logs"),
        "K_pqx": hkdf_derive_key(seed_alfa, "ALFA:PQX:meta"),
        "K_photos": hkdf_derive_key(seed_alfa, "ALFA:photos"),
        "K_session": hkdf_derive_key(seed_alfa, "ALFA:session", length=64),
    }
