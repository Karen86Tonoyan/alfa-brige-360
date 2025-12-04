//! ALFA Photos Vault - Error Types

use thiserror::Error;

/// Result type for vault operations
pub type VaultResult<T> = Result<T, VaultError>;

/// Vault error types
#[derive(Error, Debug)]
pub enum VaultError {
    // ═══════════════════════════════════════════════════════════════
    // CRYPTO ERRORS
    // ═══════════════════════════════════════════════════════════════
    
    #[error("Encryption failed: {0}")]
    EncryptionFailed(String),
    
    #[error("Decryption failed: {0}")]
    DecryptionFailed(String),
    
    #[error("Key derivation failed: {0}")]
    KeyDerivationFailed(String),
    
    #[error("Invalid key length: expected {expected}, got {actual}")]
    InvalidKeyLength { expected: usize, actual: usize },
    
    #[error("HMAC verification failed - file corrupted or tampered")]
    HmacVerificationFailed,
    
    // ═══════════════════════════════════════════════════════════════
    // VAULT ERRORS
    // ═══════════════════════════════════════════════════════════════
    
    #[error("Vault is locked")]
    VaultLocked,
    
    #[error("Vault already exists at: {0}")]
    VaultAlreadyExists(String),
    
    #[error("Vault not found at: {0}")]
    VaultNotFound(String),
    
    #[error("Vault corrupted: {0}")]
    VaultCorrupted(String),
    
    #[error("Invalid PIN")]
    InvalidPin,
    
    #[error("Biometric authentication failed")]
    BiometricFailed,
    
    #[error("Too many failed attempts - vault locked")]
    TooManyAttempts,
    
    // ═══════════════════════════════════════════════════════════════
    // FILE ERRORS
    // ═══════════════════════════════════════════════════════════════
    
    #[error("File not found: {0}")]
    FileNotFound(String),
    
    #[error("File already exists: {0}")]
    FileAlreadyExists(String),
    
    #[error("Invalid file format: {0}")]
    InvalidFileFormat(String),
    
    #[error("File too large: {size} bytes (max: {max})")]
    FileTooLarge { size: u64, max: u64 },
    
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
    
    // ═══════════════════════════════════════════════════════════════
    // INDEX ERRORS
    // ═══════════════════════════════════════════════════════════════
    
    #[error("Index corrupted: {0}")]
    IndexCorrupted(String),
    
    #[error("Photo not found in index: {0}")]
    PhotoNotFound(String),
    
    #[error("Database error: {0}")]
    DatabaseError(String),
    
    // ═══════════════════════════════════════════════════════════════
    // THUMBNAIL ERRORS
    // ═══════════════════════════════════════════════════════════════
    
    #[error("Thumbnail generation failed: {0}")]
    ThumbnailFailed(String),
    
    #[error("Image processing error: {0}")]
    ImageError(String),
    
    // ═══════════════════════════════════════════════════════════════
    // SYNC ERRORS
    // ═══════════════════════════════════════════════════════════════
    
    #[error("Sync failed: {0}")]
    SyncFailed(String),
    
    #[error("Plugin not configured: {0}")]
    PluginNotConfigured(String),
    
    // ═══════════════════════════════════════════════════════════════
    // AI ERRORS
    // ═══════════════════════════════════════════════════════════════
    
    #[error("AI module error: {0}")]
    AiError(String),
    
    // ═══════════════════════════════════════════════════════════════
    // SERIALIZATION ERRORS
    // ═══════════════════════════════════════════════════════════════
    
    #[error("Serialization error: {0}")]
    SerializationError(String),
    
    #[error("Deserialization error: {0}")]
    DeserializationError(String),
}

impl VaultError {
    /// Check if this is a security-critical error
    pub fn is_security_critical(&self) -> bool {
        matches!(
            self,
            VaultError::HmacVerificationFailed
                | VaultError::DecryptionFailed(_)
                | VaultError::TooManyAttempts
                | VaultError::VaultCorrupted(_)
        )
    }
    
    /// Check if vault should lock after this error
    pub fn requires_lockdown(&self) -> bool {
        matches!(
            self,
            VaultError::TooManyAttempts | VaultError::HmacVerificationFailed
        )
    }
    
    /// Check if this error is recoverable via reset
    pub fn is_recoverable(&self) -> bool {
        matches!(
            self,
            VaultError::IndexCorrupted(_)
                | VaultError::ThumbnailFailed(_)
                | VaultError::SyncFailed(_)
        )
    }
}

impl From<rusqlite::Error> for VaultError {
    fn from(e: rusqlite::Error) -> Self {
        VaultError::DatabaseError(e.to_string())
    }
}

impl From<serde_json::Error> for VaultError {
    fn from(e: serde_json::Error) -> Self {
        VaultError::SerializationError(e.to_string())
    }
}

impl From<image::ImageError> for VaultError {
    fn from(e: image::ImageError) -> Self {
        VaultError::ImageError(e.to_string())
    }
}
