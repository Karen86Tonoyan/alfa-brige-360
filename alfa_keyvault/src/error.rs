//! Typy błędów dla ALFA_KEYVAULT

use thiserror::Error;

#[derive(Debug, Error)]
pub enum AlfaKeyVaultError {
    #[error("Vault already exists at {0}")]
    VaultExists(String),

    #[error("Vault not found at {0}")]
    VaultNotFound(String),

    #[error("Invalid vault JSON: {0}")]
    InvalidJson(#[from] serde_json::Error),

    #[error("Crypto error: {0}")]
    Crypto(String),

    #[error("Authentication failed - wrong password?")]
    AuthFailed,

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Invalid base64: {0}")]
    Base64(#[from] base64::DecodeError),

    #[error("Vault is locked - call unlock() first")]
    VaultLocked,

    #[error("Version mismatch: expected {expected}, got {got}")]
    VersionMismatch { expected: String, got: String },

    #[error("Threat detected: {0}")]
    ThreatDetected(String),

    #[error("Policy violation: {0}")]
    PolicyViolation(String),

    #[error("Max failed attempts reached ({0})")]
    MaxAttemptsReached(u32),

    #[error("Vault corrupted - attempting recovery")]
    VaultCorrupted,

    #[error("Snapshot error: {0}")]
    SnapshotError(String),

    #[error("Brain error: {0}")]
    BrainError(String),

    #[error("Lockdown active - vault inaccessible")]
    LockdownActive,

    #[error("Key derivation failed: {0}")]
    KeyDerivationFailed(String),

    #[error("Rotation required")]
    RotationRequired,
}

pub type Result<T> = std::result::Result<T, AlfaKeyVaultError>;

impl AlfaKeyVaultError {
    pub fn is_security_critical(&self) -> bool {
        matches!(
            self,
            Self::ThreatDetected(_)
                | Self::MaxAttemptsReached(_)
                | Self::LockdownActive
                | Self::PolicyViolation(_)
        )
    }

    pub fn requires_lockdown(&self) -> bool {
        matches!(
            self,
            Self::ThreatDetected(_) | Self::MaxAttemptsReached(_)
        )
    }
}
