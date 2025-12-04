//! Moduł kryptograficzny - Argon2id, AES-GCM, HKDF, XChaCha20

mod argon2_kdf;
mod aead;
mod hkdf_derive;
mod zeroize_utils;

pub use argon2_kdf::{derive_kek, Argon2Config};
pub use aead::{encrypt_seed, decrypt_seed, AeadCipher};
pub use hkdf_derive::{derive_subkey, derive_subkey_fixed};
pub use zeroize_utils::{zeroize_buffer, SecureBuffer};

use secrecy::SecretVec;

/// Bezpieczny wrapper na klucz
pub type SecretKey = secrecy::SecretBox<[u8; 32]>;

/// Bezpieczny wrapper na seed
pub type SecretSeed = secrecy::SecretBox<[u8; 32]>;
