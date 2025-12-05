"""
ALFA_CORE Crypto Module

ALFA_KEYVAULT 4.0 ARMORED - Production Hardened Vault

Provides cryptographic primitives for ALFA ecosystem:
- Vault management with full hardening
- HMAC integrity verification
- Anti-rollback protection
- Lockout mechanism
- Device binding
- Entropy validation
- Secure memory handling
- Key derivation (HKDF, Argon2id)
- Encryption (AES-256-GCM)
- PQXHybrid hooks (X25519 + Kyber1024)
"""

from .alfa_keyvault_v4 import (
    # Core vault v4 ARMORED
    AlfaKeyVault,
    InnerVault,
    SecurityState,
    VaultIntegrity,
    SecurityError,
    
    # Vault operations
    create_new_vault,
    open_vault,
    create_inner_vault,
    open_inner_vault,
    vault_reset,
    
    # Key derivation
    derive_kek,
    derive_hmac_key,
    hkdf_derive_key,
    derive_all_module_keys,
    
    # Encryption
    encrypt_seed,
    decrypt_seed,
    
    # PhotoKeys for Photos Vault
    PhotoKeys,
    
    # Secure memory
    SecretBytes,
    secure_random,
    
    # Security utilities
    validate_password_strength,
    calculate_entropy,
    get_device_fingerprint,
    verify_device_binding,
    verify_no_rollback,
    get_rollback_counter,
    LockoutManager,
    
    # Data classes
    KDFConfig,
    SeedEncrypted,
    DeviceInfo,
    PQXMeta,
    PQXShadowEntry,
    EscrowMeta,
    
    # Base64 utils
    b64e,
    b64d,
)

from .alfa_guard_ai import (
    AlfaSecurityAI,
    GuardEvent,
    GuardState,
)

__all__ = [
    # Vault v4 ARMORED
    "AlfaKeyVault",
    "InnerVault",
    "SecurityState",
    "VaultIntegrity",
    "SecurityError",
    
    # Vault operations
    "create_new_vault",
    "open_vault",
    "create_inner_vault",
    "open_inner_vault",
    "vault_reset",
    
    # Crypto
    "derive_kek",
    "derive_hmac_key",
    "hkdf_derive_key",
    "derive_all_module_keys",
    "encrypt_seed",
    "decrypt_seed",
    
    # Photos
    "PhotoKeys",
    
    # Secure memory
    "SecretBytes",
    "secure_random",
    
    # Security utilities
    "validate_password_strength",
    "calculate_entropy",
    "get_device_fingerprint",
    "verify_device_binding",
    "verify_no_rollback",
    "get_rollback_counter",
    "LockoutManager",
    
    # Config
    "KDFConfig",
    "SeedEncrypted",
    "PQXMeta",
    "DeviceInfo",
    "PQXShadowEntry",
    "EscrowMeta",
    
    # Security AI
    "AlfaSecurityAI",
    "GuardEvent",
    "GuardState",
    
    # Utils
    "b64e",
    "b64d",
]
