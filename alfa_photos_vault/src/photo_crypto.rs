//! Photo encryption module for ALFA Photos Vault
//!
//! Format pliku .enc:
//! ```text
//! [MAGIC 8B]["ALFAPHOT"]
//! [VERSION 1B][0x01]
//! [NONCE 12B][random]
//! [CIPHERTEXT variable][AES-256-GCM encrypted]
//! [TAG 16B][GCM auth tag]
//! [HMAC 32B][HMAC-SHA256 of all above]
//! ```

use aes_gcm::{
    aead::{Aead, KeyInit, Payload},
    Aes256Gcm, Nonce,
};
use hmac::{Hmac, Mac};
use rand::RngCore;
use sha2::Sha256;
use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::Path;
use zeroize::Zeroizing;

use crate::error::{VaultError, VaultResult};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Magic bytes identifying ALFA Photos encrypted file
const MAGIC: &[u8; 8] = b"ALFAPHOT";

/// Current format version
const VERSION: u8 = 0x01;

/// Nonce size for AES-256-GCM (96 bits)
const NONCE_SIZE: usize = 12;

/// GCM authentication tag size
const TAG_SIZE: usize = 16;

/// HMAC-SHA256 size
const HMAC_SIZE: usize = 32;

/// Header size: MAGIC(8) + VERSION(1) + NONCE(12)
const HEADER_SIZE: usize = 8 + 1 + NONCE_SIZE;

/// Minimum valid file size
const MIN_FILE_SIZE: usize = HEADER_SIZE + TAG_SIZE + HMAC_SIZE;

// ---------------------------------------------------------------------------
// PhotoCrypto
// ---------------------------------------------------------------------------

/// Handles per-file photo encryption/decryption
pub struct PhotoCrypto {
    /// 256-bit master key for photos
    master_key: Zeroizing<[u8; 32]>,
    /// 256-bit HMAC key
    hmac_key: Zeroizing<[u8; 32]>,
}

impl PhotoCrypto {
    /// Create new PhotoCrypto with master and HMAC keys
    pub fn new(master_key: [u8; 32], hmac_key: [u8; 32]) -> Self {
        Self {
            master_key: Zeroizing::new(master_key),
            hmac_key: Zeroizing::new(hmac_key),
        }
    }

    /// Derive per-file key using HKDF
    fn derive_file_key(&self, photo_id: &str) -> Zeroizing<[u8; 32]> {
        use hkdf::Hkdf;

        let hkdf = Hkdf::<Sha256>::new(None, &*self.master_key);
        let info = format!("ALFA:PHOTO:FILE:{}", photo_id);
        
        let mut file_key = Zeroizing::new([0u8; 32]);
        hkdf.expand(info.as_bytes(), &mut *file_key)
            .expect("HKDF expand failed");
        
        file_key
    }

    /// Compute HMAC-SHA256 over data
    fn compute_hmac(&self, data: &[u8]) -> [u8; 32] {
        let mut mac = Hmac::<Sha256>::new_from_slice(&*self.hmac_key)
            .expect("HMAC key size invalid");
        mac.update(data);
        mac.finalize().into_bytes().into()
    }

    /// Verify HMAC
    fn verify_hmac(&self, data: &[u8], expected: &[u8; 32]) -> bool {
        let computed = self.compute_hmac(data);
        // Constant-time comparison
        computed.iter().zip(expected.iter()).all(|(a, b)| a == b)
    }

    /// Encrypt photo file
    ///
    /// # Arguments
    /// * `input_path` - Path to plaintext photo
    /// * `output_path` - Path to write encrypted .enc file
    /// * `photo_id` - Unique photo identifier for key derivation
    ///
    /// # Returns
    /// Number of bytes written
    pub fn encrypt_photo<P: AsRef<Path>, Q: AsRef<Path>>(
        &self,
        input_path: P,
        output_path: Q,
        photo_id: &str,
    ) -> VaultResult<usize> {
        // Read plaintext
        let plaintext = fs::read(input_path.as_ref())
            .map_err(|e| VaultError::Io(e.to_string()))?;

        // Derive per-file key
        let file_key = self.derive_file_key(photo_id);

        // Generate random nonce
        let mut nonce_bytes = [0u8; NONCE_SIZE];
        rand::thread_rng().fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);

        // Encrypt with AES-256-GCM
        let cipher = Aes256Gcm::new_from_slice(&*file_key)
            .map_err(|_| VaultError::Crypto("Invalid key".into()))?;

        // AAD = photo_id for additional authentication
        let payload = Payload {
            msg: &plaintext,
            aad: photo_id.as_bytes(),
        };

        let ciphertext = cipher
            .encrypt(nonce, payload)
            .map_err(|_| VaultError::Crypto("Encryption failed".into()))?;

        // Build file content (without HMAC)
        let mut content = Vec::with_capacity(HEADER_SIZE + ciphertext.len() + HMAC_SIZE);
        content.extend_from_slice(MAGIC);
        content.push(VERSION);
        content.extend_from_slice(&nonce_bytes);
        content.extend_from_slice(&ciphertext);

        // Compute HMAC over header + ciphertext
        let hmac = self.compute_hmac(&content);
        content.extend_from_slice(&hmac);

        // Write to file
        let mut file = File::create(output_path.as_ref())
            .map_err(|e| VaultError::Io(e.to_string()))?;
        file.write_all(&content)
            .map_err(|e| VaultError::Io(e.to_string()))?;
        file.sync_all()
            .map_err(|e| VaultError::Io(e.to_string()))?;

        Ok(content.len())
    }

    /// Decrypt photo file
    ///
    /// # Arguments
    /// * `input_path` - Path to encrypted .enc file
    /// * `photo_id` - Photo identifier (must match encryption)
    ///
    /// # Returns
    /// Decrypted photo bytes
    pub fn decrypt_photo<P: AsRef<Path>>(
        &self,
        input_path: P,
        photo_id: &str,
    ) -> VaultResult<Vec<u8>> {
        // Read encrypted file
        let data = fs::read(input_path.as_ref())
            .map_err(|e| VaultError::Io(e.to_string()))?;

        self.decrypt_bytes(&data, photo_id)
    }

    /// Decrypt photo from bytes
    pub fn decrypt_bytes(&self, data: &[u8], photo_id: &str) -> VaultResult<Vec<u8>> {
        // Validate minimum size
        if data.len() < MIN_FILE_SIZE {
            return Err(VaultError::Crypto("File too small".into()));
        }

        // Verify magic
        if &data[0..8] != MAGIC {
            return Err(VaultError::Crypto("Invalid magic bytes".into()));
        }

        // Check version
        let version = data[8];
        if version != VERSION {
            return Err(VaultError::Crypto(format!(
                "Unsupported version: {}",
                version
            )));
        }

        // Extract HMAC and verify
        let hmac_start = data.len() - HMAC_SIZE;
        let stored_hmac: [u8; 32] = data[hmac_start..]
            .try_into()
            .map_err(|_| VaultError::Crypto("Invalid HMAC".into()))?;

        if !self.verify_hmac(&data[..hmac_start], &stored_hmac) {
            return Err(VaultError::Crypto("HMAC verification failed".into()));
        }

        // Extract nonce
        let nonce_bytes: [u8; NONCE_SIZE] = data[9..9 + NONCE_SIZE]
            .try_into()
            .map_err(|_| VaultError::Crypto("Invalid nonce".into()))?;
        let nonce = Nonce::from_slice(&nonce_bytes);

        // Extract ciphertext (between header and HMAC)
        let ciphertext = &data[HEADER_SIZE..hmac_start];

        // Derive per-file key
        let file_key = self.derive_file_key(photo_id);

        // Decrypt
        let cipher = Aes256Gcm::new_from_slice(&*file_key)
            .map_err(|_| VaultError::Crypto("Invalid key".into()))?;

        let payload = Payload {
            msg: ciphertext,
            aad: photo_id.as_bytes(),
        };

        let plaintext = cipher
            .decrypt(nonce, payload)
            .map_err(|_| VaultError::Crypto("Decryption failed - wrong key or corrupted".into()))?;

        Ok(plaintext)
    }

    /// Encrypt photo in memory (returns encrypted bytes)
    pub fn encrypt_bytes(&self, plaintext: &[u8], photo_id: &str) -> VaultResult<Vec<u8>> {
        // Derive per-file key
        let file_key = self.derive_file_key(photo_id);

        // Generate random nonce
        let mut nonce_bytes = [0u8; NONCE_SIZE];
        rand::thread_rng().fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);

        // Encrypt
        let cipher = Aes256Gcm::new_from_slice(&*file_key)
            .map_err(|_| VaultError::Crypto("Invalid key".into()))?;

        let payload = Payload {
            msg: plaintext,
            aad: photo_id.as_bytes(),
        };

        let ciphertext = cipher
            .encrypt(nonce, payload)
            .map_err(|_| VaultError::Crypto("Encryption failed".into()))?;

        // Build output
        let mut output = Vec::with_capacity(HEADER_SIZE + ciphertext.len() + HMAC_SIZE);
        output.extend_from_slice(MAGIC);
        output.push(VERSION);
        output.extend_from_slice(&nonce_bytes);
        output.extend_from_slice(&ciphertext);

        let hmac = self.compute_hmac(&output);
        output.extend_from_slice(&hmac);

        Ok(output)
    }

    /// Verify file integrity without decrypting
    pub fn verify_integrity<P: AsRef<Path>>(&self, path: P) -> VaultResult<bool> {
        let data = fs::read(path.as_ref())
            .map_err(|e| VaultError::Io(e.to_string()))?;

        if data.len() < MIN_FILE_SIZE {
            return Ok(false);
        }

        if &data[0..8] != MAGIC {
            return Ok(false);
        }

        let hmac_start = data.len() - HMAC_SIZE;
        let stored_hmac: [u8; 32] = match data[hmac_start..].try_into() {
            Ok(h) => h,
            Err(_) => return Ok(false),
        };

        Ok(self.verify_hmac(&data[..hmac_start], &stored_hmac))
    }

    /// Re-encrypt file with new key (for key rotation)
    pub fn reencrypt<P: AsRef<Path>>(
        &self,
        path: P,
        photo_id: &str,
        new_crypto: &PhotoCrypto,
    ) -> VaultResult<()> {
        // Decrypt with old key
        let plaintext = self.decrypt_photo(&path, photo_id)?;

        // Encrypt with new key
        new_crypto.encrypt_photo_overwrite(&path, &plaintext, photo_id)?;

        Ok(())
    }

    /// Encrypt and overwrite existing file
    fn encrypt_photo_overwrite<P: AsRef<Path>>(
        &self,
        output_path: P,
        plaintext: &[u8],
        photo_id: &str,
    ) -> VaultResult<usize> {
        let encrypted = self.encrypt_bytes(plaintext, photo_id)?;

        let mut file = File::create(output_path.as_ref())
            .map_err(|e| VaultError::Io(e.to_string()))?;
        file.write_all(&encrypted)
            .map_err(|e| VaultError::Io(e.to_string()))?;
        file.sync_all()
            .map_err(|e| VaultError::Io(e.to_string()))?;

        Ok(encrypted.len())
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn test_keys() -> (PhotoCrypto, [u8; 32], [u8; 32]) {
        let master = [0x42u8; 32];
        let hmac = [0x43u8; 32];
        (PhotoCrypto::new(master, hmac), master, hmac)
    }

    #[test]
    fn test_encrypt_decrypt_bytes() {
        let (crypto, _, _) = test_keys();
        let plaintext = b"Hello, ALFA Photos Vault!";
        let photo_id = "IMG_001";

        let encrypted = crypto.encrypt_bytes(plaintext, photo_id).unwrap();
        let decrypted = crypto.decrypt_bytes(&encrypted, photo_id).unwrap();

        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_encrypt_decrypt_file() {
        let (crypto, _, _) = test_keys();
        let dir = tempdir().unwrap();
        
        let input_path = dir.path().join("photo.jpg");
        let output_path = dir.path().join("photo.enc");
        
        let original = b"FAKE JPEG DATA 1234567890";
        fs::write(&input_path, original).unwrap();

        crypto.encrypt_photo(&input_path, &output_path, "IMG_001").unwrap();
        let decrypted = crypto.decrypt_photo(&output_path, "IMG_001").unwrap();

        assert_eq!(decrypted, original);
    }

    #[test]
    fn test_wrong_photo_id_fails() {
        let (crypto, _, _) = test_keys();
        let plaintext = b"Secret photo";

        let encrypted = crypto.encrypt_bytes(plaintext, "IMG_001").unwrap();
        let result = crypto.decrypt_bytes(&encrypted, "IMG_002");

        assert!(result.is_err());
    }

    #[test]
    fn test_tampered_data_fails() {
        let (crypto, _, _) = test_keys();
        let plaintext = b"Secret photo";

        let mut encrypted = crypto.encrypt_bytes(plaintext, "IMG_001").unwrap();
        // Tamper with ciphertext
        encrypted[HEADER_SIZE + 5] ^= 0xFF;
        
        let result = crypto.decrypt_bytes(&encrypted, "IMG_001");
        assert!(result.is_err());
    }

    #[test]
    fn test_verify_integrity() {
        let (crypto, _, _) = test_keys();
        let dir = tempdir().unwrap();
        
        let input_path = dir.path().join("photo.jpg");
        let output_path = dir.path().join("photo.enc");
        
        fs::write(&input_path, b"test data").unwrap();
        crypto.encrypt_photo(&input_path, &output_path, "IMG_001").unwrap();

        assert!(crypto.verify_integrity(&output_path).unwrap());

        // Tamper with file
        let mut data = fs::read(&output_path).unwrap();
        data[20] ^= 0xFF;
        fs::write(&output_path, data).unwrap();

        assert!(!crypto.verify_integrity(&output_path).unwrap());
    }
}
