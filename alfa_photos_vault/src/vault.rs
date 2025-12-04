//! ALFA Photos Vault - Main Vault Implementation
//!
//! The core vault that manages photos, encryption, and all operations.

use std::path::{Path, PathBuf};
use std::sync::Arc;
use parking_lot::RwLock;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::crypto::{KeyManager, VaultKey, encrypt_aes_gcm, decrypt_aes_gcm, compute_hmac, verify_hmac, EncryptedData};
use crate::index::PhotoIndex;
use crate::thumbs::ThumbnailEngine;
use crate::ai::SelfHealingAI;
use crate::secure_fs::SecureFs;
use crate::error::{VaultError, VaultResult};

/// Vault state
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VaultState {
    Locked,
    Unlocked,
    Lockdown,
}

/// Vault configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VaultConfig {
    /// Vault name
    pub name: String,
    /// Created timestamp
    pub created_at: DateTime<Utc>,
    /// Last access timestamp
    pub last_access: DateTime<Utc>,
    /// Version
    pub version: String,
    /// Max thumbnail size
    pub thumb_size: u32,
    /// Enable AI features
    pub ai_enabled: bool,
    /// Failed attempts before lockdown
    pub max_failed_attempts: u8,
}

impl Default for VaultConfig {
    fn default() -> Self {
        Self {
            name: "ALFA Photos Vault".into(),
            created_at: Utc::now(),
            last_access: Utc::now(),
            version: crate::VERSION.into(),
            thumb_size: 256,
            ai_enabled: true,
            max_failed_attempts: 5,
        }
    }
}

/// Photo metadata (stored encrypted)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhotoMeta {
    /// Unique ID
    pub id: String,
    /// Original filename
    pub original_name: String,
    /// File size (encrypted)
    pub encrypted_size: u64,
    /// Original size
    pub original_size: u64,
    /// MIME type
    pub mime_type: String,
    /// Import timestamp
    pub imported_at: DateTime<Utc>,
    /// Original creation date (from EXIF)
    pub created_at: Option<DateTime<Utc>>,
    /// HMAC for integrity
    pub hmac: [u8; 32],
    /// Tags (user-defined)
    pub tags: Vec<String>,
    /// Is hidden
    pub is_hidden: bool,
    /// Is favorite
    pub is_favorite: bool,
    /// Perceptual hash (for duplicate detection)
    pub phash: Option<String>,
}

/// Photo Vault - Main entry point
pub struct PhotoVault {
    /// Vault root path
    root: PathBuf,
    /// Configuration
    config: RwLock<VaultConfig>,
    /// Vault state
    state: RwLock<VaultState>,
    /// Key manager (only when unlocked)
    keys: RwLock<Option<Arc<KeyManager>>>,
    /// Photo index
    index: RwLock<Option<PhotoIndex>>,
    /// Thumbnail engine
    thumbs: RwLock<Option<ThumbnailEngine>>,
    /// Self-healing AI
    ai: RwLock<Option<SelfHealingAI>>,
    /// Secure filesystem
    fs: SecureFs,
    /// Failed unlock attempts
    failed_attempts: RwLock<u8>,
}

impl PhotoVault {
    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Create a new vault at the given path
    pub fn create<P: AsRef<Path>>(path: P, pin: &str) -> VaultResult<Self> {
        let root = path.as_ref().to_path_buf();
        
        if root.exists() {
            return Err(VaultError::VaultAlreadyExists(root.display().to_string()));
        }
        
        // Create directory structure
        std::fs::create_dir_all(&root)?;
        std::fs::create_dir_all(root.join("photos"))?;
        std::fs::create_dir_all(root.join("thumbs"))?;
        std::fs::create_dir_all(root.join("db"))?;
        
        // Generate master seed from PIN
        let seed = Self::derive_seed_from_pin(pin)?;
        let keys = Arc::new(KeyManager::from_master_seed(&seed)?);
        
        // Create and save encrypted config
        let config = VaultConfig::default();
        let fs = SecureFs::new(&root);
        
        // Encrypt and save manifest
        let manifest = serde_json::to_vec(&config)?;
        let encrypted = encrypt_aes_gcm(keys.index_key(), &manifest)?;
        fs.write_file("manifest.enc", &encrypted.to_bytes())?;
        
        // Initialize index
        let index = PhotoIndex::create(&root, &keys)?;
        
        // Initialize thumbnail engine
        let thumbs = ThumbnailEngine::new(&root, config.thumb_size);
        
        // Initialize AI (if enabled)
        let ai = if config.ai_enabled {
            Some(SelfHealingAI::new(&root)?)
        } else {
            None
        };
        
        Ok(Self {
            root,
            config: RwLock::new(config),
            state: RwLock::new(VaultState::Unlocked),
            keys: RwLock::new(Some(keys)),
            index: RwLock::new(Some(index)),
            thumbs: RwLock::new(Some(thumbs)),
            ai: RwLock::new(ai),
            fs,
            failed_attempts: RwLock::new(0),
        })
    }
    
    /// Open an existing vault
    pub fn open<P: AsRef<Path>>(path: P) -> VaultResult<Self> {
        let root = path.as_ref().to_path_buf();
        
        if !root.exists() {
            return Err(VaultError::VaultNotFound(root.display().to_string()));
        }
        
        let fs = SecureFs::new(&root);
        
        // Vault starts locked
        Ok(Self {
            root,
            config: RwLock::new(VaultConfig::default()),
            state: RwLock::new(VaultState::Locked),
            keys: RwLock::new(None),
            index: RwLock::new(None),
            thumbs: RwLock::new(None),
            ai: RwLock::new(None),
            fs,
            failed_attempts: RwLock::new(0),
        })
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UNLOCK / LOCK
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Unlock vault with PIN
    pub fn unlock(&self, pin: &str) -> VaultResult<()> {
        // Check if in lockdown
        if *self.state.read() == VaultState::Lockdown {
            return Err(VaultError::TooManyAttempts);
        }
        
        // Derive keys from PIN
        let seed = Self::derive_seed_from_pin(pin)?;
        let keys = Arc::new(KeyManager::from_master_seed(&seed)?);
        
        // Try to decrypt manifest
        let manifest_enc = self.fs.read_file("manifest.enc")?;
        let encrypted = EncryptedData::from_bytes_aes(&manifest_enc)?;
        
        match decrypt_aes_gcm(keys.index_key(), &encrypted) {
            Ok(manifest_data) => {
                // Parse config
                let config: VaultConfig = serde_json::from_slice(&manifest_data)?;
                
                // Initialize components
                let index = PhotoIndex::open(&self.root, &keys)?;
                let thumbs = ThumbnailEngine::new(&self.root, config.thumb_size);
                let ai = if config.ai_enabled {
                    Some(SelfHealingAI::load(&self.root)?)
                } else {
                    None
                };
                
                // Update state
                *self.config.write() = config;
                *self.keys.write() = Some(keys);
                *self.index.write() = Some(index);
                *self.thumbs.write() = Some(thumbs);
                *self.ai.write() = ai;
                *self.state.write() = VaultState::Unlocked;
                *self.failed_attempts.write() = 0;
                
                Ok(())
            }
            Err(_) => {
                // Wrong PIN
                let mut attempts = self.failed_attempts.write();
                *attempts += 1;
                
                let max = self.config.read().max_failed_attempts;
                if *attempts >= max {
                    *self.state.write() = VaultState::Lockdown;
                    return Err(VaultError::TooManyAttempts);
                }
                
                Err(VaultError::InvalidPin)
            }
        }
    }
    
    /// Lock vault (zeroize all keys)
    pub fn lock(&self) {
        *self.keys.write() = None;
        *self.index.write() = None;
        *self.thumbs.write() = None;
        *self.ai.write() = None;
        *self.state.write() = VaultState::Locked;
    }
    
    /// Check if vault is unlocked
    pub fn is_unlocked(&self) -> bool {
        *self.state.read() == VaultState::Unlocked
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PHOTO OPERATIONS
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Import a photo into the vault
    pub fn import_photo(&self, source: &Path, original_name: &str) -> VaultResult<String> {
        self.ensure_unlocked()?;
        
        let keys = self.keys.read();
        let keys = keys.as_ref().unwrap();
        
        // Read source file
        let plaintext = std::fs::read(source)?;
        let original_size = plaintext.len() as u64;
        
        // Generate unique ID
        let id = Uuid::new_v4().to_string();
        
        // Derive file-specific key
        let file_key = keys.derive_file_key(&id)?;
        
        // Encrypt
        let encrypted = encrypt_aes_gcm(&file_key, &plaintext)?;
        let encrypted_bytes = encrypted.to_bytes();
        let encrypted_size = encrypted_bytes.len() as u64;
        
        // Compute HMAC
        let hmac = compute_hmac(keys.hmac_key(), &encrypted_bytes);
        
        // Detect MIME type
        let mime_type = Self::detect_mime(&plaintext);
        
        // Generate perceptual hash for duplicate detection
        let phash = self.compute_phash(&plaintext);
        
        // Save encrypted file
        let photo_path = format!("photos/{}.enc", id);
        self.fs.write_file(&photo_path, &encrypted_bytes)?;
        
        // Generate and save thumbnail
        if let Some(ref thumbs) = *self.thumbs.read() {
            if let Ok(thumb_data) = thumbs.generate(&plaintext) {
                let thumb_key = keys.derive_thumb_key(&id)?;
                let encrypted_thumb = encrypt_aes_gcm(&thumb_key, &thumb_data)?;
                let thumb_path = format!("thumbs/{}.enc", id);
                self.fs.write_file(&thumb_path, &encrypted_thumb.to_bytes())?;
            }
        }
        
        // Create metadata
        let meta = PhotoMeta {
            id: id.clone(),
            original_name: original_name.to_string(),
            encrypted_size,
            original_size,
            mime_type,
            imported_at: Utc::now(),
            created_at: None, // TODO: Extract from EXIF
            hmac,
            tags: Vec::new(),
            is_hidden: false,
            is_favorite: false,
            phash,
        };
        
        // Add to index
        if let Some(ref mut index) = *self.index.write() {
            index.add_photo(&meta)?;
        }
        
        // Notify AI
        if let Some(ref mut ai) = *self.ai.write() {
            ai.on_photo_imported(&id);
        }
        
        Ok(id)
    }
    
    /// Get decrypted photo by ID
    pub fn get_photo(&self, id: &str) -> VaultResult<Vec<u8>> {
        self.ensure_unlocked()?;
        
        let keys = self.keys.read();
        let keys = keys.as_ref().unwrap();
        
        // Get metadata from index
        let meta = self.get_photo_meta(id)?;
        
        // Read encrypted file
        let photo_path = format!("photos/{}.enc", id);
        let encrypted_bytes = self.fs.read_file(&photo_path)?;
        
        // Verify HMAC
        if !verify_hmac(keys.hmac_key(), &encrypted_bytes, &meta.hmac) {
            return Err(VaultError::HmacVerificationFailed);
        }
        
        // Decrypt
        let file_key = keys.derive_file_key(id)?;
        let encrypted = EncryptedData::from_bytes_aes(&encrypted_bytes)?;
        decrypt_aes_gcm(&file_key, &encrypted)
    }
    
    /// Get decrypted thumbnail by ID
    pub fn get_thumbnail(&self, id: &str) -> VaultResult<Vec<u8>> {
        self.ensure_unlocked()?;
        
        let keys = self.keys.read();
        let keys = keys.as_ref().unwrap();
        
        let thumb_path = format!("thumbs/{}.enc", id);
        let encrypted_bytes = self.fs.read_file(&thumb_path)?;
        
        let thumb_key = keys.derive_thumb_key(id)?;
        let encrypted = EncryptedData::from_bytes_aes(&encrypted_bytes)?;
        decrypt_aes_gcm(&thumb_key, &encrypted)
    }
    
    /// Get photo metadata
    pub fn get_photo_meta(&self, id: &str) -> VaultResult<PhotoMeta> {
        self.ensure_unlocked()?;
        
        if let Some(ref index) = *self.index.read() {
            index.get_photo(id)
        } else {
            Err(VaultError::VaultLocked)
        }
    }
    
    /// List all photos
    pub fn list_photos(&self) -> VaultResult<Vec<PhotoMeta>> {
        self.ensure_unlocked()?;
        
        if let Some(ref index) = *self.index.read() {
            index.list_all()
        } else {
            Err(VaultError::VaultLocked)
        }
    }
    
    /// Delete photo
    pub fn delete_photo(&self, id: &str) -> VaultResult<()> {
        self.ensure_unlocked()?;
        
        // Remove from index
        if let Some(ref mut index) = *self.index.write() {
            index.remove_photo(id)?;
        }
        
        // Delete files
        let photo_path = format!("photos/{}.enc", id);
        let thumb_path = format!("thumbs/{}.enc", id);
        
        self.fs.delete_file(&photo_path)?;
        let _ = self.fs.delete_file(&thumb_path); // Thumb might not exist
        
        // Notify AI
        if let Some(ref mut ai) = *self.ai.write() {
            ai.on_photo_deleted(id);
        }
        
        Ok(())
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // RESET BUTTON (KRÓL'S REQUIREMENT)
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Reset vault - clears cache, rebuilds index, fixes issues
    pub fn reset(&self) -> VaultResult<ResetReport> {
        self.ensure_unlocked()?;
        
        let mut report = ResetReport::default();
        
        // 1. Clear thumbnail cache
        report.thumbs_cleared = self.clear_thumb_cache()?;
        
        // 2. Verify and rebuild index
        report.index_errors = self.rebuild_index()?;
        
        // 3. Verify file integrity
        report.integrity_issues = self.verify_all_files()?;
        
        // 4. Run AI self-healing
        if let Some(ref mut ai) = *self.ai.write() {
            report.ai_fixes = ai.heal()?;
        }
        
        Ok(report)
    }
    
    /// Clear thumbnail cache
    fn clear_thumb_cache(&self) -> VaultResult<usize> {
        let thumbs_dir = self.root.join("thumbs");
        let mut count = 0;
        
        if thumbs_dir.exists() {
            for entry in std::fs::read_dir(&thumbs_dir)? {
                if let Ok(entry) = entry {
                    std::fs::remove_file(entry.path())?;
                    count += 1;
                }
            }
        }
        
        Ok(count)
    }
    
    /// Rebuild index from files
    fn rebuild_index(&self) -> VaultResult<usize> {
        let keys = self.keys.read();
        let keys = keys.as_ref().unwrap();
        
        // Scan photos directory
        let photos_dir = self.root.join("photos");
        let mut errors = 0;
        
        if photos_dir.exists() {
            let mut new_index = PhotoIndex::create(&self.root, keys)?;
            
            for entry in std::fs::read_dir(&photos_dir)? {
                if let Ok(entry) = entry {
                    let filename = entry.file_name().to_string_lossy().to_string();
                    if filename.ends_with(".enc") {
                        let id = filename.trim_end_matches(".enc");
                        
                        // Try to read and verify file
                        if self.get_photo(id).is_err() {
                            errors += 1;
                        }
                    }
                }
            }
            
            *self.index.write() = Some(new_index);
        }
        
        Ok(errors)
    }
    
    /// Verify integrity of all files
    fn verify_all_files(&self) -> VaultResult<Vec<String>> {
        let mut issues = Vec::new();
        
        if let Ok(photos) = self.list_photos() {
            for meta in photos {
                if let Err(e) = self.get_photo(&meta.id) {
                    issues.push(format!("{}: {:?}", meta.id, e));
                }
            }
        }
        
        Ok(issues)
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Derive master seed from PIN using Argon2id
    fn derive_seed_from_pin(pin: &str) -> VaultResult<[u8; 64]> {
        use argon2::{Argon2, Params, Version, Algorithm};
        
        // Fixed salt (should be stored with vault in production)
        let salt = b"ALFA_PHOTOS_VAULT_SALT_v1";
        
        let params = Params::new(65536, 3, 4, Some(64))
            .map_err(|e| VaultError::KeyDerivationFailed(e.to_string()))?;
        
        let argon2 = Argon2::new(Algorithm::Argon2id, Version::V0x13, params);
        
        let mut seed = [0u8; 64];
        argon2
            .hash_password_into(pin.as_bytes(), salt, &mut seed)
            .map_err(|e| VaultError::KeyDerivationFailed(e.to_string()))?;
        
        Ok(seed)
    }
    
    /// Ensure vault is unlocked
    fn ensure_unlocked(&self) -> VaultResult<()> {
        if *self.state.read() != VaultState::Unlocked {
            Err(VaultError::VaultLocked)
        } else {
            Ok(())
        }
    }
    
    /// Detect MIME type from file content
    fn detect_mime(data: &[u8]) -> String {
        if data.len() < 8 {
            return "application/octet-stream".into();
        }
        
        // Check magic bytes
        match &data[0..8] {
            [0xFF, 0xD8, 0xFF, ..] => "image/jpeg".into(),
            [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A] => "image/png".into(),
            [0x47, 0x49, 0x46, 0x38, ..] => "image/gif".into(),
            [0x52, 0x49, 0x46, 0x46, ..] => {
                if data.len() > 12 && &data[8..12] == b"WEBP" {
                    "image/webp".into()
                } else {
                    "application/octet-stream".into()
                }
            }
            _ => {
                // Check for HEIC/HEIF
                if data.len() > 12 {
                    if &data[4..8] == b"ftyp" {
                        if &data[8..12] == b"heic" || &data[8..12] == b"heix" {
                            return "image/heic".into();
                        }
                        if &data[8..12] == b"mif1" {
                            return "image/heif".into();
                        }
                    }
                }
                "application/octet-stream".into()
            }
        }
    }
    
    /// Compute perceptual hash for duplicate detection
    fn compute_phash(&self, data: &[u8]) -> Option<String> {
        use image::io::Reader as ImageReader;
        use std::io::Cursor;
        
        // Try to decode image
        let img = ImageReader::new(Cursor::new(data))
            .with_guessed_format()
            .ok()?
            .decode()
            .ok()?;
        
        // Compute perceptual hash
        let hasher = img_hash::HasherConfig::new()
            .hash_size(16, 16)
            .to_hasher();
        
        let hash = hasher.hash_image(&img);
        Some(hash.to_base64())
    }
}

/// Report from reset operation
#[derive(Debug, Default)]
pub struct ResetReport {
    pub thumbs_cleared: usize,
    pub index_errors: usize,
    pub integrity_issues: Vec<String>,
    pub ai_fixes: usize,
}

impl ResetReport {
    pub fn is_healthy(&self) -> bool {
        self.index_errors == 0 && self.integrity_issues.is_empty()
    }
}
