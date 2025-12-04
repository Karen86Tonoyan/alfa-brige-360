//! AEAD szyfrowanie - AES-256-GCM i XChaCha20-Poly1305

use aes_gcm::{
    aead::{Aead, KeyInit, OsRng, generic_array::GenericArray},
    Aes256Gcm, Nonce as AesNonce,
};
use chacha20poly1305::{XChaCha20Poly1305, XNonce};
use secrecy::{SecretBox, ExposeSecret};
use serde::{Deserialize, Serialize};

use crate::error::{AlfaKeyVaultError, Result};

/// Typ szyfru AEAD
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AeadCipher {
    /// AES-256-GCM (12-byte nonce)
    #[serde(rename = "aes-256-gcm")]
    Aes256Gcm,
    /// XChaCha20-Poly1305 (24-byte nonce) - preferowany
    #[serde(rename = "xchacha20-poly1305")]
    XChaCha20Poly1305,
}

impl Default for AeadCipher {
    fn default() -> Self {
        Self::XChaCha20Poly1305
    }
}

impl AeadCipher {
    pub fn nonce_len(&self) -> usize {
        match self {
            Self::Aes256Gcm => 12,
            Self::XChaCha20Poly1305 => 24,
        }
    }

    pub fn name(&self) -> &'static str {
        match self {
            Self::Aes256Gcm => "AES-256-GCM",
            Self::XChaCha20Poly1305 => "XChaCha20-Poly1305",
        }
    }
}

/// Szyfruje seed używając KEK
pub fn encrypt_seed(
    seed: &SecretBox<[u8; 32]>,
    kek: &SecretBox<[u8; 32]>,
    cipher: AeadCipher,
) -> Result<(Vec<u8>, Vec<u8>)> {
    match cipher {
        AeadCipher::Aes256Gcm => encrypt_aes_gcm(seed, kek),
        AeadCipher::XChaCha20Poly1305 => encrypt_xchacha(seed, kek),
    }
}

/// Deszyfruje seed używając KEK
pub fn decrypt_seed(
    kek: &SecretBox<[u8; 32]>,
    nonce: &[u8],
    ciphertext: &[u8],
    cipher: AeadCipher,
) -> Result<SecretBox<[u8; 32]>> {
    match cipher {
        AeadCipher::Aes256Gcm => decrypt_aes_gcm(kek, nonce, ciphertext),
        AeadCipher::XChaCha20Poly1305 => decrypt_xchacha(kek, nonce, ciphertext),
    }
}

// AES-256-GCM implementation
fn encrypt_aes_gcm(
    seed: &SecretBox<[u8; 32]>,
    kek: &SecretBox<[u8; 32]>,
) -> Result<(Vec<u8>, Vec<u8>)> {
    let key = GenericArray::from_slice(kek.expose_secret());
    let cipher = Aes256Gcm::new(key);

    let mut nonce_bytes = [0u8; 12];
    getrandom::getrandom(&mut nonce_bytes)
        .map_err(|e| AlfaKeyVaultError::Crypto(format!("RNG failed: {}", e)))?;
    let nonce = AesNonce::from_slice(&nonce_bytes);

    let ciphertext = cipher
        .encrypt(nonce, seed.expose_secret().as_ref())
        .map_err(|e| AlfaKeyVaultError::Crypto(format!("AES-GCM encryption failed: {}", e)))?;

    Ok((nonce_bytes.to_vec(), ciphertext))
}

fn decrypt_aes_gcm(
    kek: &SecretBox<[u8; 32]>,
    nonce: &[u8],
    ciphertext: &[u8],
) -> Result<SecretBox<[u8; 32]>> {
    if nonce.len() != 12 {
        return Err(AlfaKeyVaultError::Crypto("Invalid AES-GCM nonce length".into()));
    }

    let key = GenericArray::from_slice(kek.expose_secret());
    let cipher = Aes256Gcm::new(key);
    let nonce = AesNonce::from_slice(nonce);

    let plaintext = cipher
        .decrypt(nonce, ciphertext)
        .map_err(|_| AlfaKeyVaultError::AuthFailed)?;

    if plaintext.len() != 32 {
        return Err(AlfaKeyVaultError::Crypto("Invalid seed length".into()));
    }

    let mut seed = [0u8; 32];
    seed.copy_from_slice(&plaintext);
    Ok(SecretBox::new(Box::new(seed)))
}

// XChaCha20-Poly1305 implementation
fn encrypt_xchacha(
    seed: &SecretBox<[u8; 32]>,
    kek: &SecretBox<[u8; 32]>,
) -> Result<(Vec<u8>, Vec<u8>)> {
    use chacha20poly1305::aead::KeyInit;
    
    let key = chacha20poly1305::Key::from_slice(kek.expose_secret());
    let cipher = XChaCha20Poly1305::new(key);

    let mut nonce_bytes = [0u8; 24];
    getrandom::getrandom(&mut nonce_bytes)
        .map_err(|e| AlfaKeyVaultError::Crypto(format!("RNG failed: {}", e)))?;
    let nonce = XNonce::from_slice(&nonce_bytes);

    let ciphertext = cipher
        .encrypt(nonce, seed.expose_secret().as_ref())
        .map_err(|e| AlfaKeyVaultError::Crypto(format!("XChaCha20 encryption failed: {}", e)))?;

    Ok((nonce_bytes.to_vec(), ciphertext))
}

fn decrypt_xchacha(
    kek: &SecretBox<[u8; 32]>,
    nonce: &[u8],
    ciphertext: &[u8],
) -> Result<SecretBox<[u8; 32]>> {
    use chacha20poly1305::aead::KeyInit;
    
    if nonce.len() != 24 {
        return Err(AlfaKeyVaultError::Crypto("Invalid XChaCha20 nonce length".into()));
    }

    let key = chacha20poly1305::Key::from_slice(kek.expose_secret());
    let cipher = XChaCha20Poly1305::new(key);
    let nonce = XNonce::from_slice(nonce);

    let plaintext = cipher
        .decrypt(nonce, ciphertext)
        .map_err(|_| AlfaKeyVaultError::AuthFailed)?;

    if plaintext.len() != 32 {
        return Err(AlfaKeyVaultError::Crypto("Invalid seed length".into()));
    }

    let mut seed = [0u8; 32];
    seed.copy_from_slice(&plaintext);
    Ok(SecretBox::new(Box::new(seed)))
}

/// Szyfruje dowolne dane
pub fn encrypt_data(
    data: &[u8],
    key: &SecretBox<[u8; 32]>,
    cipher: AeadCipher,
) -> Result<(Vec<u8>, Vec<u8>)> {
    match cipher {
        AeadCipher::Aes256Gcm => {
            let k = GenericArray::from_slice(key.expose_secret());
            let c = Aes256Gcm::new(k);
            let mut nonce_bytes = [0u8; 12];
            getrandom::getrandom(&mut nonce_bytes).unwrap();
            let nonce = AesNonce::from_slice(&nonce_bytes);
            let ct = c.encrypt(nonce, data)
                .map_err(|e| AlfaKeyVaultError::Crypto(e.to_string()))?;
            Ok((nonce_bytes.to_vec(), ct))
        }
        AeadCipher::XChaCha20Poly1305 => {
            use chacha20poly1305::aead::KeyInit;
            let k = chacha20poly1305::Key::from_slice(key.expose_secret());
            let c = XChaCha20Poly1305::new(k);
            let mut nonce_bytes = [0u8; 24];
            getrandom::getrandom(&mut nonce_bytes).unwrap();
            let nonce = XNonce::from_slice(&nonce_bytes);
            let ct = c.encrypt(nonce, data)
                .map_err(|e| AlfaKeyVaultError::Crypto(e.to_string()))?;
            Ok((nonce_bytes.to_vec(), ct))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_aes_gcm_roundtrip() {
        let seed = SecretBox::new(Box::new([42u8; 32]));
        let kek = SecretBox::new(Box::new([1u8; 32]));

        let (nonce, ct) = encrypt_seed(&seed, &kek, AeadCipher::Aes256Gcm).unwrap();
        let decrypted = decrypt_seed(&kek, &nonce, &ct, AeadCipher::Aes256Gcm).unwrap();

        assert_eq!(seed.expose_secret(), decrypted.expose_secret());
    }

    #[test]
    fn test_xchacha_roundtrip() {
        let seed = SecretBox::new(Box::new([42u8; 32]));
        let kek = SecretBox::new(Box::new([1u8; 32]));

        let (nonce, ct) = encrypt_seed(&seed, &kek, AeadCipher::XChaCha20Poly1305).unwrap();
        let decrypted = decrypt_seed(&kek, &nonce, &ct, AeadCipher::XChaCha20Poly1305).unwrap();

        assert_eq!(seed.expose_secret(), decrypted.expose_secret());
    }

    #[test]
    fn test_wrong_password_fails() {
        let seed = SecretBox::new(Box::new([42u8; 32]));
        let kek1 = SecretBox::new(Box::new([1u8; 32]));
        let kek2 = SecretBox::new(Box::new([2u8; 32]));

        let (nonce, ct) = encrypt_seed(&seed, &kek1, AeadCipher::XChaCha20Poly1305).unwrap();
        let result = decrypt_seed(&kek2, &nonce, &ct, AeadCipher::XChaCha20Poly1305);

        assert!(result.is_err());
    }
}
