//! # ALFA_KEYVAULT 4.0 - Autonomiczny Sejf z Żywym AI
//!
//! ## Możliwości:
//! - Auto-polityki (dynamiczne reguły bezpieczeństwa)
//! - Self-learning engine (uczenie się wzorców)
//! - Auto-rotacja kluczy co 90 dni
//! - PQX snapshots z podpisem post-quantum
//! - Tryb Wilka (defensive mode)
//! - Samodoskonalenie parametrów
//! - API daemon dla integracji

pub mod error;
pub mod crypto;
pub mod vault;
pub mod policy;
pub mod brain;
pub mod snapshot;

// Re-exports
pub use error::{AlfaKeyVaultError, Result};
pub use vault::{AlfaKeyVault, VaultConfig, VaultStatus};
pub use policy::{AutoPolicy, ThreatLevel};
pub use brain::VaultBrain;
pub use snapshot::PqxSnapshot;

/// Wersja biblioteki
pub const VERSION: &str = "4.0.0";

/// Nazwa systemu
pub const SYSTEM_NAME: &str = "ALFA_KEYVAULT";

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_version() {
        assert_eq!(VERSION, "4.0.0");
    }
}
