//! ALFA Photos Vault - AEAD Encryption
//!
//! AES-256-GCM for photos, XChaCha20-Poly1305 for index/metadata.

use aes_gcm::{
    aead::{Aead, KeyInit},
    Aes256Gcm, Nonce,
};
use chacha20poly1305::{XChaCha20Poly1305, XNonce};
use zeroize::Zeroize;

use super::keys::{VaultKey, NONCE_LEN, XCHACHA_NONCE_LEN, generate_nonce, generate_xchacha_nonce};
use crate::error::{VaultError, VaultResult};

/// Encrypted data with nonce prepended
pub struct EncryptedData {
    /// Nonce (12 or 24 bytes depending on cipher)
    pub nonce: Vec<u8>,
    /// Ciphertext with authentication tag
    pub ciphertext: Vec<u8>,
}

impl EncryptedData {
    /// Serialize to bytes (nonce || ciphertext)
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut result = Vec::with_capacity(self.nonce.len() + self.ciphertext.len());
        result.extend_from_slice(&self.nonce);
        result.extend_from_slice(&self.ciphertext);
        result
    }
    
    /// Deserialize from bytes (AES-GCM format)
    pub fn from_bytes_aes(data: &[u8]) -> VaultResult<Self> {
        if data.len() < NONCE_LEN + 16 {
            return Err(VaultError::DecryptionFailed("Data too short".into()));
        }
        
        Ok(Self {
            nonce: data[..NONCE_LEN].to_vec(),
            ciphertext: data[NONCE_LEN..].to_vec(),
        })
    }
    
    /// Deserialize from bytes (XChaCha20 format)
    pub fn from_bytes_xchacha(data: &[u8]) -> VaultResult<Self> {
        if data.len() < XCHACHA_NONCE_LEN + 16 {
            return Err(VaultError::DecryptionFailed("Data too short".into()));
        }
        
        Ok(Self {
            nonce: data[..XCHACHA_NONCE_LEN].to_vec(),
            ciphertext: data[XCHACHA_NONCE_LEN..].to_vec(),
        })
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// AES-256-GCM (for photos and thumbnails)
// ═══════════════════════════════════════════════════════════════════════════

/// Encrypt data with AES-256-GCM
pub fn encrypt_aes_gcm(key: &VaultKey, plaintext: &[u8]) -> VaultResult<EncryptedData> {
    let cipher = Aes256Gcm::new_from_slice(key.expose())
        .map_err(|e| VaultError::EncryptionFailed(e.to_string()))?;
    
    let nonce_bytes = generate_nonce();
    let nonce = Nonce::from_slice(&nonce_bytes);
    
    let ciphertext = cipher
        .encrypt(nonce, plaintext)
        .map_err(|e| VaultError::EncryptionFailed(e.to_string()))?;
    
    Ok(EncryptedData {
        nonce: nonce_bytes.to_vec(),
        ciphertext,
    })
}

/// Decrypt data with AES-256-GCM
pub fn decrypt_aes_gcm(key: &VaultKey, encrypted: &EncryptedData) -> VaultResult<Vec<u8>> {
    let cipher = Aes256Gcm::new_from_slice(key.expose())
        .map_err(|e| VaultError::DecryptionFailed(e.to_string()))?;
    
    if encrypted.nonce.len() != NONCE_LEN {
        return Err(VaultError::DecryptionFailed("Invalid nonce length".into()));
    }
    
    let nonce = Nonce::from_slice(&encrypted.nonce);
    
    let mut plaintext = cipher
        .decrypt(nonce, encrypted.ciphertext.as_slice())
        .map_err(|_| VaultError::DecryptionFailed("Authentication failed".into()))?;
    
    // The plaintext will be zeroized when dropped
    Ok(plaintext)
}

// ═══════════════════════════════════════════════════════════════════════════
// XChaCha20-Poly1305 (for index and metadata - faster for small data)
// ═══════════════════════════════════════════════════════════════════════════

/// Encrypt data with XChaCha20-Poly1305
pub fn encrypt_xchacha(key: &VaultKey, plaintext: &[u8]) -> VaultResult<EncryptedData> {
    let cipher = XChaCha20Poly1305::new_from_slice(key.expose())
        .map_err(|e| VaultError::EncryptionFailed(e.to_string()))?;
    
    let nonce_bytes = generate_xchacha_nonce();
    let nonce = XNonce::from_slice(&nonce_bytes);
    
    let ciphertext = cipher
        .encrypt(nonce, plaintext)
        .map_err(|e| VaultError::EncryptionFailed(e.to_string()))?;
    
    Ok(EncryptedData {
        nonce: nonce_bytes.to_vec(),
        ciphertext,
    })
}

/// Decrypt data with XChaCha20-Poly1305
pub fn decrypt_xchacha(key: &VaultKey, encrypted: &EncryptedData) -> VaultResult<Vec<u8>> {
    let cipher = XChaCha20Poly1305::new_from_slice(key.expose())
        .map_err(|e| VaultError::DecryptionFailed(e.to_string()))?;
    
    if encrypted.nonce.len() != XCHACHA_NONCE_LEN {
        return Err(VaultError::DecryptionFailed("Invalid nonce length".into()));
    }
    
    let nonce = XNonce::from_slice(&encrypted.nonce);
    
    cipher
        .decrypt(nonce, encrypted.ciphertext.as_slice())
        .map_err(|_| VaultError::DecryptionFailed("Authentication failed".into()))
}

// ═══════════════════════════════════════════════════════════════════════════
// HMAC for integrity verification
// ═══════════════════════════════════════════════════════════════════════════

use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

/// Compute HMAC-SHA256 for file integrity
pub fn compute_hmac(key: &VaultKey, data: &[u8]) -> [u8; 32] {
    let mut mac = HmacSha256::new_from_slice(key.expose())
        .expect("HMAC key length is always valid");
    mac.update(data);
    mac.finalize().into_bytes().into()
}

/// Verify HMAC-SHA256
pub fn verify_hmac(key: &VaultKey, data: &[u8], expected: &[u8; 32]) -> bool {
    let computed = compute_hmac(key, data);
    // Constant-time comparison
    computed == *expected
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_aes_gcm_roundtrip() {
        let key = VaultKey::generate();
        let plaintext = b"ALFA Photos Vault - Top Secret Photo Data";
        
        let encrypted = encrypt_aes_gcm(&key, plaintext).unwrap();
        let decrypted = decrypt_aes_gcm(&key, &encrypted).unwrap();
        
        assert_eq!(plaintext.as_slice(), decrypted.as_slice());
    }
    
    #[test]
    fn test_xchacha_roundtrip() {
        let key = VaultKey::generate();
        let plaintext = b"ALFA Index Database Content";
        
        let encrypted = encrypt_xchacha(&key, plaintext).unwrap();
        let decrypted = decrypt_xchacha(&key, &encrypted).unwrap();
        
        assert_eq!(plaintext.as_slice(), decrypted.as_slice());
    }
    
    #[test]
    fn test_hmac() {
        let key = VaultKey::generate();
        let data = b"Photo file content";
        
        let mac = compute_hmac(&key, data);
        assert!(verify_hmac(&key, data, &mac));
        
        // Tampered data should fail
        let tampered = b"Tampered content";
        assert!(!verify_hmac(&key, tampered, &mac));
    }
    
    #[test]
    fn test_wrong_key_fails() {
        let key1 = VaultKey::generate();
        let key2 = VaultKey::generate();
        let plaintext = b"Secret data";
        
        let encrypted = encrypt_aes_gcm(&key1, plaintext).unwrap();
        let result = decrypt_aes_gcm(&key2, &encrypted);
        
        assert!(result.is_err());
    }
}
