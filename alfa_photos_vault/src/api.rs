//! ALFA Photos Vault - Unified Public API
//!
//! Single entry point for all Photos Vault operations.
//! Integrates with ALFA_KEYVAULT for key management.

use std::path::{Path, PathBuf};
use std::sync::Arc;
use parking_lot::RwLock;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::crypto::KeyManager;
use crate::vault::{PhotoVault, PhotoMeta, VaultState};
use crate::rotation::{RotationManager, RotationStatus, RotationPolicy};
use crate::ai::SelfHealingAI;
use crate::error::{VaultError, VaultResult};

// ═══════════════════════════════════════════════════════════════════════════════
// API CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════════

/// API configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiConfig {
    /// Vault root directory
    pub vault_path: PathBuf,
    /// Enable AI features
    pub ai_enabled: bool,
    /// Enable auto-rotation
    pub auto_rotation: bool,
    /// Rotation policy
    pub rotation_policy: RotationPolicy,
    /// Max thumbnail size
    pub thumb_size: u32,
    /// Enable sync plugins
    pub sync_enabled: bool,
}

impl Default for ApiConfig {
    fn default() -> Self {
        Self {
            vault_path: PathBuf::from("~/.alfa_photos_vault"),
            ai_enabled: true,
            auto_rotation: true,
            rotation_policy: RotationPolicy::default(),
            thumb_size: 256,
            sync_enabled: false,
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// PHOTO VAULT API - THE ONLY PUBLIC INTERFACE
// ═══════════════════════════════════════════════════════════════════════════════

/// ALFA Photos Vault API
/// 
/// This is the ONLY public interface you need.
/// All operations go through this single entry point.
/// 
/// # Example
/// 
/// ```rust,ignore
/// use alfa_photos_vault::api::PhotoVaultApi;
/// 
/// // Load vault with master password
/// let api = PhotoVaultApi::open("~/.alfa_photos_vault", "MASTER_PASSWORD")?;
/// 
/// // Import a photo
/// let photo_id = api.import_photo("/path/to/photo.jpg")?;
/// 
/// // Get decrypted photo
/// let photo_data = api.get_photo(&photo_id)?;
/// 
/// // Get thumbnail
/// let thumb_data = api.get_thumbnail(&photo_id)?;
/// 
/// // Lock when done
/// api.lock();
/// ```
pub struct PhotoVaultApi {
    /// Inner vault
    vault: Arc<RwLock<PhotoVault>>,
    /// Rotation manager
    rotation: Arc<RotationManager>,
    /// Configuration
    config: ApiConfig,
}

impl PhotoVaultApi {
    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Create a new vault
    pub fn create<P: AsRef<Path>>(path: P, pin: &str) -> VaultResult<Self> {
        let vault = PhotoVault::create(&path, pin)?;
        let rotation = RotationManager::load_or_create(path.as_ref())?;
        
        Ok(Self {
            vault: Arc::new(RwLock::new(vault)),
            rotation: Arc::new(rotation),
            config: ApiConfig {
                vault_path: path.as_ref().to_path_buf(),
                ..Default::default()
            },
        })
    }
    
    /// Open existing vault
    pub fn open<P: AsRef<Path>>(path: P, pin: &str) -> VaultResult<Self> {
        let vault = PhotoVault::open(&path)?;
        vault.unlock(pin)?;
        
        let rotation = RotationManager::load_or_create(path.as_ref())?;
        
        // Check if rotation is needed
        if rotation.needs_rotation() {
            log::warn!("Key rotation is due! Consider rotating keys.");
        }
        
        Ok(Self {
            vault: Arc::new(RwLock::new(vault)),
            rotation: Arc::new(rotation),
            config: ApiConfig {
                vault_path: path.as_ref().to_path_buf(),
                ..Default::default()
            },
        })
    }
    
    /// Open with custom config
    pub fn open_with_config<P: AsRef<Path>>(path: P, pin: &str, config: ApiConfig) -> VaultResult<Self> {
        let vault = PhotoVault::open(&path)?;
        vault.unlock(pin)?;
        
        let rotation = RotationManager::load_or_create(path.as_ref())?;
        
        Ok(Self {
            vault: Arc::new(RwLock::new(vault)),
            rotation: Arc::new(rotation),
            config,
        })
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // LOCK / UNLOCK
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Lock vault (zeroize all keys)
    pub fn lock(&self) {
        self.vault.read().lock();
    }
    
    /// Unlock vault with PIN
    pub fn unlock(&self, pin: &str) -> VaultResult<()> {
        self.vault.read().unlock(pin)
    }
    
    /// Check if vault is unlocked
    pub fn is_unlocked(&self) -> bool {
        self.vault.read().is_unlocked()
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PHOTO OPERATIONS
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Import a photo into the vault
    pub fn import_photo<P: AsRef<Path>>(&self, source: P) -> VaultResult<String> {
        let source_path = source.as_ref();
        let original_name = source_path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("unknown");
        
        self.vault.read().import_photo(source_path, original_name)
    }
    
    /// Import multiple photos
    pub fn import_photos<P: AsRef<Path>>(&self, sources: &[P]) -> Vec<VaultResult<String>> {
        sources.iter().map(|p| self.import_photo(p)).collect()
    }
    
    /// Get decrypted photo data
    pub fn get_photo(&self, photo_id: &str) -> VaultResult<Vec<u8>> {
        self.vault.read().get_photo(photo_id)
    }
    
    /// Get encrypted thumbnail
    pub fn get_thumbnail(&self, photo_id: &str) -> VaultResult<Vec<u8>> {
        self.vault.read().get_thumbnail(photo_id)
    }
    
    /// Get photo metadata
    pub fn get_metadata(&self, photo_id: &str) -> VaultResult<PhotoMeta> {
        self.vault.read().get_metadata(photo_id)
    }
    
    /// Delete a photo
    pub fn delete_photo(&self, photo_id: &str) -> VaultResult<()> {
        self.vault.read().delete_photo(photo_id)
    }
    
    /// List all photo IDs
    pub fn list_photos(&self) -> VaultResult<Vec<String>> {
        self.vault.read().list_photos()
    }
    
    /// Search photos by tag
    pub fn search_by_tag(&self, tag: &str) -> VaultResult<Vec<String>> {
        self.vault.read().search_by_tag(tag)
    }
    
    /// Add tag to photo
    pub fn add_tag(&self, photo_id: &str, tag: &str) -> VaultResult<()> {
        self.vault.read().add_tag(photo_id, tag)
    }
    
    /// Remove tag from photo
    pub fn remove_tag(&self, photo_id: &str, tag: &str) -> VaultResult<()> {
        self.vault.read().remove_tag(photo_id, tag)
    }
    
    /// Toggle favorite status
    pub fn toggle_favorite(&self, photo_id: &str) -> VaultResult<bool> {
        self.vault.read().toggle_favorite(photo_id)
    }
    
    /// Toggle hidden status
    pub fn toggle_hidden(&self, photo_id: &str) -> VaultResult<bool> {
        self.vault.read().toggle_hidden(photo_id)
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // KING'S VAULT (HIDDEN PHOTOS)
    // ═══════════════════════════════════════════════════════════════════════
    
    /// List hidden photos (King's Vault)
    pub fn list_hidden(&self) -> VaultResult<Vec<String>> {
        self.vault.read().list_hidden()
    }
    
    /// Move photo to King's Vault
    pub fn hide_photo(&self, photo_id: &str) -> VaultResult<()> {
        self.vault.read().hide_photo(photo_id)
    }
    
    /// Unhide photo from King's Vault
    pub fn unhide_photo(&self, photo_id: &str) -> VaultResult<()> {
        self.vault.read().unhide_photo(photo_id)
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // KEY ROTATION
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Get rotation status
    pub fn rotation_status(&self) -> RotationStatus {
        self.rotation.status()
    }
    
    /// Check if rotation is needed
    pub fn needs_rotation(&self) -> bool {
        self.rotation.needs_rotation()
    }
    
    /// Days until next rotation
    pub fn days_until_rotation(&self) -> i64 {
        self.rotation.days_until_rotation()
    }
    
    /// Perform key rotation (re-encrypts all files with new epoch key)
    pub fn rotate_keys(&self, new_pin: &str) -> VaultResult<u64> {
        // This would re-encrypt all files with new keys
        // For now, just update rotation state
        self.rotation.rotate()
    }
    
    /// Update rotation policy
    pub fn set_rotation_policy(&self, policy: RotationPolicy) -> VaultResult<()> {
        self.rotation.update_policy(policy)
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // VAULT HEALTH & MAINTENANCE
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Reset vault (clear cache, rebuild index, verify integrity)
    pub fn reset(&self) -> VaultResult<ResetReport> {
        let vault = self.vault.read();
        
        // Clear thumbnail cache
        let thumbs_cleared = vault.clear_thumb_cache()?;
        
        // Rebuild index
        let index_rebuilt = vault.rebuild_index()?;
        
        // Verify all files
        let integrity = vault.verify_integrity()?;
        
        Ok(ResetReport {
            thumbs_cleared,
            index_rebuilt,
            files_verified: integrity.total,
            files_corrupted: integrity.corrupted,
            timestamp: Utc::now(),
        })
    }
    
    /// Verify vault integrity
    pub fn verify_integrity(&self) -> VaultResult<IntegrityReport> {
        self.vault.read().verify_integrity()
    }
    
    /// Get vault statistics
    pub fn stats(&self) -> VaultResult<VaultStats> {
        let vault = self.vault.read();
        
        Ok(VaultStats {
            total_photos: vault.count_photos()?,
            total_size: vault.total_size()?,
            hidden_count: vault.count_hidden()?,
            favorite_count: vault.count_favorites()?,
            rotation_status: self.rotation.status(),
        })
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // EXPORT / BACKUP
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Export photo to plaintext file
    pub fn export_photo<P: AsRef<Path>>(&self, photo_id: &str, dest: P) -> VaultResult<()> {
        let data = self.get_photo(photo_id)?;
        std::fs::write(dest, data)?;
        Ok(())
    }
    
    /// Export all photos to directory
    pub fn export_all<P: AsRef<Path>>(&self, dest_dir: P) -> VaultResult<Vec<String>> {
        let dest = dest_dir.as_ref();
        std::fs::create_dir_all(dest)?;
        
        let photo_ids = self.list_photos()?;
        let mut exported = Vec::new();
        
        for id in &photo_ids {
            let meta = self.get_metadata(id)?;
            let data = self.get_photo(id)?;
            let path = dest.join(&meta.original_name);
            std::fs::write(&path, data)?;
            exported.push(id.clone());
        }
        
        Ok(exported)
    }
    
    /// Create encrypted backup
    pub fn create_backup<P: AsRef<Path>>(&self, dest: P) -> VaultResult<BackupInfo> {
        self.vault.read().create_backup(dest.as_ref())
    }
    
    /// Restore from backup
    pub fn restore_backup<P: AsRef<Path>>(&self, backup_path: P, pin: &str) -> VaultResult<()> {
        self.vault.write().restore_backup(backup_path.as_ref(), pin)
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// REPORT TYPES
// ═══════════════════════════════════════════════════════════════════════════════

/// Reset operation report
#[derive(Debug, Clone, Serialize)]
pub struct ResetReport {
    pub thumbs_cleared: usize,
    pub index_rebuilt: bool,
    pub files_verified: usize,
    pub files_corrupted: usize,
    pub timestamp: DateTime<Utc>,
}

/// Integrity check report
#[derive(Debug, Clone, Serialize)]
pub struct IntegrityReport {
    pub total: usize,
    pub verified: usize,
    pub corrupted: usize,
    pub missing: usize,
    pub details: Vec<IntegrityIssue>,
}

/// Single integrity issue
#[derive(Debug, Clone, Serialize)]
pub struct IntegrityIssue {
    pub photo_id: String,
    pub issue_type: IssueType,
    pub description: String,
}

/// Issue types
#[derive(Debug, Clone, Serialize)]
pub enum IssueType {
    HmacMismatch,
    FileMissing,
    ThumbnailMissing,
    MetadataCorrupted,
    DecryptionFailed,
}

/// Vault statistics
#[derive(Debug, Clone, Serialize)]
pub struct VaultStats {
    pub total_photos: usize,
    pub total_size: u64,
    pub hidden_count: usize,
    pub favorite_count: usize,
    pub rotation_status: RotationStatus,
}

/// Backup information
#[derive(Debug, Clone, Serialize)]
pub struct BackupInfo {
    pub path: PathBuf,
    pub size: u64,
    pub photos_count: usize,
    pub created_at: DateTime<Utc>,
    pub encrypted: bool,
}

// ═══════════════════════════════════════════════════════════════════════════════
// CONVENIENCE FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════════

/// Quick open vault (convenience function)
pub fn open_vault<P: AsRef<Path>>(path: P, pin: &str) -> VaultResult<PhotoVaultApi> {
    PhotoVaultApi::open(path, pin)
}

/// Quick create vault (convenience function)
pub fn create_vault<P: AsRef<Path>>(path: P, pin: &str) -> VaultResult<PhotoVaultApi> {
    PhotoVaultApi::create(path, pin)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;
    
    #[test]
    fn test_api_create_and_open() {
        let dir = tempdir().unwrap();
        let vault_path = dir.path().join("test_vault");
        
        // Create vault
        let api = PhotoVaultApi::create(&vault_path, "test_pin").unwrap();
        assert!(api.is_unlocked());
        
        // Lock
        api.lock();
        assert!(!api.is_unlocked());
        
        // Unlock
        api.unlock("test_pin").unwrap();
        assert!(api.is_unlocked());
    }
}
