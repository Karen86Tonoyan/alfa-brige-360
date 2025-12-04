//! Argon2id KDF dla derywacji KEK z hasła

use argon2::{Argon2, Params, Version, Algorithm};
use secrecy::{SecretBox, ExposeSecret};
use zeroize::Zeroize;
use serde::{Deserialize, Serialize};

use crate::error::{AlfaKeyVaultError, Result};

/// Konfiguracja Argon2id
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Argon2Config {
    /// Iteracje (time cost)
    pub time_cost: u32,
    /// Pamięć w KiB
    pub memory_cost_kib: u32,
    /// Równoległość
    pub parallelism: u32,
    /// Długość wyjściowa
    pub output_len: usize,
    /// Salt (base64)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub salt: Option<String>,
}

impl Default for Argon2Config {
    fn default() -> Self {
        Self {
            time_cost: 3,
            memory_cost_kib: 64 * 1024, // 64 MiB
            parallelism: 2,
            output_len: 32,
            salt: None,
        }
    }
}

impl Argon2Config {
    /// Tworzy konfigurację z losowym salt
    pub fn with_random_salt() -> Self {
        let mut salt = [0u8; 16];
        getrandom::getrandom(&mut salt).expect("Failed to generate random salt");
        Self {
            salt: Some(base64::Engine::encode(
                &base64::engine::general_purpose::STANDARD,
                salt,
            )),
            ..Default::default()
        }
    }

    /// Konfiguracja dla słabych urządzeń
    pub fn low_memory() -> Self {
        Self {
            time_cost: 4,
            memory_cost_kib: 16 * 1024, // 16 MiB
            parallelism: 1,
            output_len: 32,
            salt: None,
        }
    }

    /// Konfiguracja dla mocnych urządzeń
    pub fn high_security() -> Self {
        Self {
            time_cost: 4,
            memory_cost_kib: 256 * 1024, // 256 MiB
            parallelism: 4,
            output_len: 32,
            salt: None,
        }
    }

    /// Oblicz szacowany czas derywacji (ms)
    pub fn estimated_time_ms(&self) -> u64 {
        // Przybliżone oszacowanie
        let base = 50u64; // bazowy czas w ms
        let mem_factor = self.memory_cost_kib as u64 / 1024;
        let time_factor = self.time_cost as u64;
        base * time_factor * mem_factor / self.parallelism as u64
    }
}

/// Derywuje Key Encryption Key (KEK) z hasła
pub fn derive_kek(
    password: &SecretBox<String>,
    salt: &[u8],
    config: &Argon2Config,
) -> Result<SecretBox<[u8; 32]>> {
    use base64::Engine;
    
    // Pepper dla dodatkowego bezpieczeństwa
    const PEPPER: &[u8] = b"ALFA_KEYVAULT_v4_PEPPER_2025";

    // Buduj Argon2 z parametrami
    let params = Params::new(
        config.memory_cost_kib,
        config.time_cost,
        config.parallelism,
        Some(config.output_len),
    )
    .map_err(|e| AlfaKeyVaultError::Crypto(format!("Invalid Argon2 params: {}", e)))?;

    let argon2 = Argon2::new_with_secret(
        PEPPER,
        Algorithm::Argon2id,
        Version::V0x13,
        params,
    )
    .map_err(|e| AlfaKeyVaultError::Crypto(format!("Argon2 init failed: {}", e)))?;

    // Derywuj klucz
    let mut output = [0u8; 32];
    argon2
        .hash_password_into(password.expose_secret().as_bytes(), salt, &mut output)
        .map_err(|e| AlfaKeyVaultError::Crypto(format!("Hashing failed: {}", e)))?;

    Ok(SecretBox::new(Box::new(output)))
}

/// Generuje losowy salt
pub fn generate_salt() -> [u8; 16] {
    let mut salt = [0u8; 16];
    getrandom::getrandom(&mut salt).expect("Failed to generate random salt");
    salt
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_derive_kek() {
        let password = SecretBox::new(Box::new("test_password".to_string()));
        let salt = generate_salt();
        let config = Argon2Config::default();

        let kek = derive_kek(&password, &salt, &config).unwrap();
        assert_eq!(kek.expose_secret().len(), 32);
    }

    #[test]
    fn test_derive_kek_deterministic() {
        let password = SecretBox::new(Box::new("test_password".to_string()));
        let salt = [1u8; 16];
        let config = Argon2Config::default();

        let kek1 = derive_kek(&password, &salt, &config).unwrap();
        let kek2 = derive_kek(&password, &salt, &config).unwrap();

        assert_eq!(kek1.expose_secret(), kek2.expose_secret());
    }
}
