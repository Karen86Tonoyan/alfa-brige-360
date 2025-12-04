//! HKDF derywacja kluczy modułowych

use hkdf::Hkdf;
use sha2::Sha256;
use secrecy::{SecretBox, SecretVec, ExposeSecret};

/// Derywuje klucz o zmiennej długości
pub fn derive_subkey(
    seed: &SecretBox<[u8; 32]>,
    purpose: &str,
    length: usize,
) -> SecretVec<u8> {
    let hk = Hkdf::<Sha256>::new(None, seed.expose_secret());
    let mut okm = vec![0u8; length];
    hk.expand(purpose.as_bytes(), &mut okm)
        .expect("HKDF expand failed - length too large");

    SecretVec::new(okm)
}

/// Derywuje klucz o stałej długości
pub fn derive_subkey_fixed<const N: usize>(
    seed: &SecretBox<[u8; 32]>,
    purpose: &str,
) -> SecretBox<[u8; N]> {
    let hk = Hkdf::<Sha256>::new(None, seed.expose_secret());
    let mut output = [0u8; N];
    hk.expand(purpose.as_bytes(), &mut output)
        .expect("HKDF expand failed");

    SecretBox::new(Box::new(output))
}

/// Derywuje klucz 32-bajtowy (najczęstszy przypadek)
pub fn derive_key_32(seed: &SecretBox<[u8; 32]>, purpose: &str) -> SecretBox<[u8; 32]> {
    derive_subkey_fixed::<32>(seed, purpose)
}

/// Derywuje klucz z epoch (dla rotacji)
pub fn derive_epoch_key(
    seed: &SecretBox<[u8; 32]>,
    purpose: &str,
    epoch: u64,
) -> SecretBox<[u8; 32]> {
    let info = format!("{}:epoch:{}", purpose, epoch);
    derive_subkey_fixed::<32>(seed, &info)
}

/// Predefiniowane cele derywacji
pub mod purposes {
    pub const CONFIG: &str = "ALFA:config";
    pub const MAIL: &str = "ALFA:mail";
    pub const LOGS: &str = "ALFA:logs";
    pub const CACHE: &str = "ALFA:cache";
    pub const SESSION: &str = "ALFA:session";
    pub const PQX_META: &str = "ALFA:PQXHybrid:meta";
    pub const DEVICE_MASTER: &str = "ALFA:device:master";
    pub const SNAPSHOT_SIGN: &str = "ALFA:snapshot:sign";
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_derive_subkey() {
        let seed = SecretBox::new(Box::new([42u8; 32]));
        let key = derive_subkey(&seed, "test:purpose", 64);
        assert_eq!(key.expose_secret().len(), 64);
    }

    #[test]
    fn test_derive_deterministic() {
        let seed = SecretBox::new(Box::new([42u8; 32]));
        let key1 = derive_key_32(&seed, "test");
        let key2 = derive_key_32(&seed, "test");
        assert_eq!(key1.expose_secret(), key2.expose_secret());
    }

    #[test]
    fn test_different_purposes_different_keys() {
        let seed = SecretBox::new(Box::new([42u8; 32]));
        let key1 = derive_key_32(&seed, "ALFA:config");
        let key2 = derive_key_32(&seed, "ALFA:mail");
        assert_ne!(key1.expose_secret(), key2.expose_secret());
    }

    #[test]
    fn test_epoch_derivation() {
        let seed = SecretBox::new(Box::new([42u8; 32]));
        let key_e0 = derive_epoch_key(&seed, "ALFA:device", 0);
        let key_e1 = derive_epoch_key(&seed, "ALFA:device", 1);
        assert_ne!(key_e0.expose_secret(), key_e1.expose_secret());
    }
}
