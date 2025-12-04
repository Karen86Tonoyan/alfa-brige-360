//! # ALFA Photos Vault
//! 
//! Military-grade encrypted photo gallery with self-healing AI.
//! 
//! ## Architecture
//! 
//! ```text
//! ┌─────────────────────────────────────────────────────────┐
//! │                   ALFA PHOTOS VAULT                      │
//! │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
//! │  │  BIOMETRICS │  │  VAULT CORE │  │  SYNC PLUGIN    │  │
//! │  │  + PIN      │  │  AES-256-GCM│  │  (Ente/NAS)     │  │
//! │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │
//! │         │                │                   │           │
//! │  ┌──────┴────────────────┴───────────────────┴────────┐ │
//! │  │              ALFA_KEYVAULT INTEGRATION              │ │
//! │  │         HKDF → K_photos / K_thumbs / K_index        │ │
//! │  └─────────────────────────────────────────────────────┘ │
//! │                                                          │
//! │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
//! │  │  THUMBNAIL  │  │  INDEX DB   │  │  SELF-HEALING   │  │
//! │  │  ENGINE     │  │  (encrypted)│  │  AI MODULE      │  │
//! │  └─────────────┘  └─────────────┘  └─────────────────┘  │
//! └─────────────────────────────────────────────────────────┘
//! ```
//! 
//! ## Security Model
//! 
//! - All photos encrypted with AES-256-GCM
//! - Per-file unique keys derived via HKDF
//! - Thumbnails also encrypted
//! - Index database encrypted with XChaCha20-Poly1305
//! - Zero plaintext on disk
//! - RAM zeroized after use

pub mod crypto;
pub mod vault;
pub mod index;
pub mod thumbs;
pub mod secure_fs;
pub mod biometrics;
pub mod sync_plugin;
pub mod ai;
pub mod error;
pub mod rotation;
pub mod api;
pub mod photo_crypto;

#[cfg(feature = "android")]
pub mod android;

pub use error::{VaultError, VaultResult};
pub use vault::PhotoVault;
pub use index::PhotoIndex;
pub use thumbs::ThumbnailEngine;
pub use ai::SelfHealingAI;
pub use rotation::{RotationManager, RotationStatus};
pub use api::PhotoVaultApi;

/// ALFA Photos Vault version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// ALFA Photos Vault signature
pub const SIGNATURE: &str = "ALFA_PHOTOS_VAULT_v1";
