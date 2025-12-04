//! ALFA Photos Vault - Sync Plugin
//!
//! Optional sync to external services (Ente, Nextcloud, NAS).
//! ALWAYS encrypted - external service only sees blobs.

use std::path::Path;
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

use crate::error::{VaultError, VaultResult};

/// Sync provider type
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum SyncProvider {
    /// Ente Photos (encrypted cloud)
    Ente,
    /// Nextcloud WebDAV
    Nextcloud,
    /// Local NAS (SMB/CIFS)
    LocalNas,
    /// Custom WebDAV
    CustomWebDav,
    /// USB/External drive
    UsbDrive,
}

/// Sync configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncConfig {
    /// Provider type
    pub provider: SyncProvider,
    /// Server URL (for cloud providers)
    pub server_url: Option<String>,
    /// Username
    pub username: Option<String>,
    /// Encrypted credentials (encrypted with vault key)
    pub encrypted_credentials: Option<Vec<u8>>,
    /// Remote path
    pub remote_path: String,
    /// Auto-sync enabled
    pub auto_sync: bool,
    /// Sync interval (seconds)
    pub sync_interval: u64,
    /// Last sync time
    pub last_sync: Option<DateTime<Utc>>,
}

impl Default for SyncConfig {
    fn default() -> Self {
        Self {
            provider: SyncProvider::UsbDrive,
            server_url: None,
            username: None,
            encrypted_credentials: None,
            remote_path: "/ALFA_Backup".into(),
            auto_sync: false,
            sync_interval: 3600, // 1 hour
            last_sync: None,
        }
    }
}

/// Sync status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncStatus {
    /// Is syncing
    pub syncing: bool,
    /// Progress (0.0 - 1.0)
    pub progress: f32,
    /// Files synced
    pub files_synced: usize,
    /// Total files
    pub total_files: usize,
    /// Last error
    pub last_error: Option<String>,
}

/// Sync Plugin Manager
pub struct SyncPlugin {
    config: Option<SyncConfig>,
    status: SyncStatus,
}

impl SyncPlugin {
    /// Create new sync plugin (not configured)
    pub fn new() -> Self {
        Self {
            config: None,
            status: SyncStatus {
                syncing: false,
                progress: 0.0,
                files_synced: 0,
                total_files: 0,
                last_error: None,
            },
        }
    }
    
    /// Configure sync
    pub fn configure(&mut self, config: SyncConfig) -> VaultResult<()> {
        // Validate config
        match config.provider {
            SyncProvider::Ente | SyncProvider::Nextcloud | SyncProvider::CustomWebDav => {
                if config.server_url.is_none() {
                    return Err(VaultError::PluginNotConfigured(
                        "Server URL required".into()
                    ));
                }
            }
            _ => {}
        }
        
        self.config = Some(config);
        Ok(())
    }
    
    /// Check if configured
    pub fn is_configured(&self) -> bool {
        self.config.is_some()
    }
    
    /// Get current status
    pub fn status(&self) -> &SyncStatus {
        &self.status
    }
    
    /// Sync a single file (already encrypted)
    pub async fn sync_file(&mut self, file_id: &str, encrypted_data: &[u8]) -> VaultResult<()> {
        let config = self.config.as_ref()
            .ok_or_else(|| VaultError::PluginNotConfigured("Sync not configured".into()))?;
        
        self.status.syncing = true;
        
        let result = match config.provider {
            SyncProvider::UsbDrive | SyncProvider::LocalNas => {
                self.sync_to_local(file_id, encrypted_data, &config.remote_path).await
            }
            SyncProvider::Ente => {
                self.sync_to_ente(file_id, encrypted_data, config).await
            }
            SyncProvider::Nextcloud | SyncProvider::CustomWebDav => {
                self.sync_to_webdav(file_id, encrypted_data, config).await
            }
        };
        
        self.status.syncing = false;
        
        if let Err(ref e) = result {
            self.status.last_error = Some(e.to_string());
        } else {
            self.status.files_synced += 1;
        }
        
        result
    }
    
    /// Sync to local path (USB/NAS)
    async fn sync_to_local(&self, file_id: &str, data: &[u8], base_path: &str) -> VaultResult<()> {
        let path = Path::new(base_path).join(format!("{}.enc", file_id));
        
        // Ensure directory exists
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        
        std::fs::write(&path, data)?;
        Ok(())
    }
    
    /// Sync to Ente (stub - requires Ente API integration)
    async fn sync_to_ente(&self, _file_id: &str, _data: &[u8], _config: &SyncConfig) -> VaultResult<()> {
        // TODO: Implement Ente API
        // Ente already uses E2E encryption, but we send pre-encrypted data
        // so even Ente can't see the content
        Err(VaultError::PluginNotConfigured("Ente sync not implemented".into()))
    }
    
    /// Sync to WebDAV (Nextcloud, etc.)
    async fn sync_to_webdav(&self, _file_id: &str, _data: &[u8], _config: &SyncConfig) -> VaultResult<()> {
        // TODO: Implement WebDAV client
        Err(VaultError::PluginNotConfigured("WebDAV sync not implemented".into()))
    }
    
    /// Full sync (all files)
    pub async fn full_sync<F>(&mut self, get_files: F) -> VaultResult<SyncReport>
    where
        F: Fn() -> Vec<(String, Vec<u8>)>,
    {
        let files = get_files();
        self.status.total_files = files.len();
        self.status.files_synced = 0;
        
        let mut report = SyncReport {
            total: files.len(),
            synced: 0,
            failed: 0,
            errors: Vec::new(),
        };
        
        for (file_id, data) in files {
            match self.sync_file(&file_id, &data).await {
                Ok(_) => report.synced += 1,
                Err(e) => {
                    report.failed += 1;
                    report.errors.push(format!("{}: {}", file_id, e));
                }
            }
            
            self.status.progress = report.synced as f32 / report.total as f32;
        }
        
        // Update last sync time
        if let Some(ref mut config) = self.config {
            config.last_sync = Some(Utc::now());
        }
        
        Ok(report)
    }
}

impl Default for SyncPlugin {
    fn default() -> Self {
        Self::new()
    }
}

/// Sync report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncReport {
    pub total: usize,
    pub synced: usize,
    pub failed: usize,
    pub errors: Vec<String>,
}

impl SyncReport {
    pub fn success(&self) -> bool {
        self.failed == 0
    }
}
