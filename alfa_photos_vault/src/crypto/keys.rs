//! ALFA Photos Vault - Key Management
//!
//! Derives specialized keys from ALFA_KEYVAULT master seed.

use hkdf::Hkdf;
use sha2::Sha256;
use zeroize::{Zeroize, ZeroizeOnDrop};
use secrecy::{Secret, ExposeSecret};

use crate::error::{VaultError, VaultResult};

/// Key length for AES-256
pub const KEY_LEN: usize = 32;

/// Nonce length for AES-GCM
pub const NONCE_LEN: usize = 12;

/// Nonce length for XChaCha20
pub const XCHACHA_NONCE_LEN: usize = 24;

/// HKDF contexts for key derivation
pub mod contexts {
    /// Context for photo encryption keys
    pub const PHOTOS: &[u8] = b"ALFA:PHOTOS:v1";
    
    /// Context for thumbnail encryption keys
    pub const THUMBS: &[u8] = b"ALFA:THUMBS:v1";
    
    /// Context for index encryption key
    pub const INDEX: &[u8] = b"ALFA:INDEX:v1";
    
    /// Context for metadata encryption key
    pub const METADATA: &[u8] = b"ALFA:METADATA:v1";
    
    /// Context for per-file key derivation
    pub const FILE_KEY: &[u8] = b"ALFA:FILE:v1";
    
    /// Context for HMAC keys
    pub const HMAC: &[u8] = b"ALFA:HMAC:v1";
}

/// Secure key wrapper with automatic zeroization
#[derive(Clone, ZeroizeOnDrop)]
pub struct VaultKey {
    #[zeroize(skip)]
    inner: Secret<[u8; KEY_LEN]>,
}

impl VaultKey {
    /// Create a new vault key from bytes
    pub fn new(bytes: [u8; KEY_LEN]) -> Self {
        Self {
            inner: Secret::new(bytes),
        }
    }
    
    /// Expose the key bytes (use with caution)
    pub fn expose(&self) -> &[u8; KEY_LEN] {
        self.inner.expose_secret()
    }
    
    /// Generate a random key
    pub fn generate() -> Self {
        use rand::RngCore;
        let mut bytes = [0u8; KEY_LEN];
        rand::thread_rng().fill_bytes(&mut bytes);
        Self::new(bytes)
    }
}

/// Photo Vault Key Manager
/// 
/// Derives all specialized keys from the ALFA_KEYVAULT master seed.
#[derive(ZeroizeOnDrop)]
pub struct KeyManager {
    /// Master key from ALFA_KEYVAULT
    #[zeroize(skip)]
    master: VaultKey,
    
    /// Derived key for photos
    #[zeroize(skip)]
    photos_key: VaultKey,
    
    /// Derived key for thumbnails
    #[zeroize(skip)]
    thumbs_key: VaultKey,
    
    /// Derived key for index
    #[zeroize(skip)]
    index_key: VaultKey,
    
    /// Derived key for HMAC
    #[zeroize(skip)]
    hmac_key: VaultKey,
}

impl KeyManager {
    /// Create a new KeyManager from ALFA_KEYVAULT master seed
    pub fn from_master_seed(seed: &[u8]) -> VaultResult<Self> {
        if seed.len() < 32 {
            return Err(VaultError::InvalidKeyLength {
                expected: 32,
                actual: seed.len(),
            });
        }
        
        // Derive master key from seed
        let master = derive_key(seed, b"", contexts::PHOTOS)?;
        
        // Derive specialized keys
        let photos_key = derive_key(master.expose(), b"photos", contexts::PHOTOS)?;
        let thumbs_key = derive_key(master.expose(), b"thumbs", contexts::THUMBS)?;
        let index_key = derive_key(master.expose(), b"index", contexts::INDEX)?;
        let hmac_key = derive_key(master.expose(), b"hmac", contexts::HMAC)?;
        
        Ok(Self {
            master,
            photos_key,
            thumbs_key,
            index_key,
            hmac_key,
        })
    }
    
    /// Get the photos encryption key
    pub fn photos_key(&self) -> &VaultKey {
        &self.photos_key
    }
    
    /// Get the thumbnails encryption key
    pub fn thumbs_key(&self) -> &VaultKey {
        &self.thumbs_key
    }
    
    /// Get the index encryption key
    pub fn index_key(&self) -> &VaultKey {
        &self.index_key
    }
    
    /// Get the HMAC key
    pub fn hmac_key(&self) -> &VaultKey {
        &self.hmac_key
    }
    
    /// Derive a unique key for a specific file
    pub fn derive_file_key(&self, file_id: &str) -> VaultResult<VaultKey> {
        derive_key(self.photos_key.expose(), file_id.as_bytes(), contexts::FILE_KEY)
    }
    
    /// Derive a unique key for a specific thumbnail
    pub fn derive_thumb_key(&self, file_id: &str) -> VaultResult<VaultKey> {
        derive_key(self.thumbs_key.expose(), file_id.as_bytes(), contexts::FILE_KEY)
    }
}

/// Derive a key using HKDF-SHA256
pub fn derive_key(ikm: &[u8], salt: &[u8], info: &[u8]) -> VaultResult<VaultKey> {
    let hk = Hkdf::<Sha256>::new(Some(salt), ikm);
    let mut okm = [0u8; KEY_LEN];
    
    hk.expand(info, &mut okm)
        .map_err(|e| VaultError::KeyDerivationFailed(e.to_string()))?;
    
    Ok(VaultKey::new(okm))
}

/// Generate a random nonce for AES-GCM
pub fn generate_nonce() -> [u8; NONCE_LEN] {
    use rand::RngCore;
    let mut nonce = [0u8; NONCE_LEN];
    rand::thread_rng().fill_bytes(&mut nonce);
    nonce
}

/// Generate a random nonce for XChaCha20
pub fn generate_xchacha_nonce() -> [u8; XCHACHA_NONCE_LEN] {
    use rand::RngCore;
    let mut nonce = [0u8; XCHACHA_NONCE_LEN];
    rand::thread_rng().fill_bytes(&mut nonce);
    nonce
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_key_derivation() {
        let seed = [0x42u8; 64];
        let km = KeyManager::from_master_seed(&seed).unwrap();
        
        // Keys should be different
        assert_ne!(km.photos_key().expose(), km.thumbs_key().expose());
        assert_ne!(km.photos_key().expose(), km.index_key().expose());
        
        // File keys should be deterministic
        let fk1 = km.derive_file_key("photo_001").unwrap();
        let fk2 = km.derive_file_key("photo_001").unwrap();
        assert_eq!(fk1.expose(), fk2.expose());
        
        // Different files get different keys
        let fk3 = km.derive_file_key("photo_002").unwrap();
        assert_ne!(fk1.expose(), fk3.expose());
    }
}
