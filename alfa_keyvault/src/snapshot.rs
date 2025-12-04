//! PQX Snapshots - podpisane migawki stanu vault

use std::path::{Path, PathBuf};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::error::{AlfaKeyVaultError, Result};
use crate::crypto::{derive_subkey_fixed, SecretKey};
use secrecy::{SecretBox, ExposeSecret};

/// Snapshot vault z podpisem
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PqxSnapshot {
    /// Wersja snapshotu
    pub version: String,

    /// Epoch (numer rotacji)
    pub epoch: u64,

    /// Timestamp utworzenia
    pub timestamp: DateTime<Utc>,

    /// Parametry KDF
    pub kdf_params: KdfParams,

    /// Użycie kluczy
    pub key_usages: HashMap<String, u64>,

    /// Hash poprzedniego snapshotu (chain)
    pub prev_hash: Option<String>,

    /// Podpis HMAC-SHA256 (lub w przyszłości Dilithium)
    pub signature: String,

    /// Metadane
    pub metadata: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KdfParams {
    pub algorithm: String,
    pub time_cost: u32,
    pub memory_cost_kib: u32,
    pub parallelism: u32,
}

impl PqxSnapshot {
    /// Tworzy nowy snapshot
    pub fn new(
        epoch: u64,
        kdf_params: KdfParams,
        key_usages: HashMap<String, u64>,
        prev_hash: Option<String>,
    ) -> Self {
        Self {
            version: "4.0-PQX".to_string(),
            epoch,
            timestamp: Utc::now(),
            kdf_params,
            key_usages,
            prev_hash,
            signature: String::new(),
            metadata: HashMap::new(),
        }
    }

    /// Oblicza hash snapshotu (bez podpisu)
    pub fn compute_hash(&self) -> String {
        use sha2::{Sha256, Digest};

        let mut hasher = Sha256::new();
        hasher.update(self.version.as_bytes());
        hasher.update(self.epoch.to_le_bytes());
        hasher.update(self.timestamp.to_rfc3339().as_bytes());
        hasher.update(self.kdf_params.algorithm.as_bytes());
        hasher.update(self.kdf_params.time_cost.to_le_bytes());
        hasher.update(self.kdf_params.memory_cost_kib.to_le_bytes());

        for (key, count) in &self.key_usages {
            hasher.update(key.as_bytes());
            hasher.update(count.to_le_bytes());
        }

        if let Some(ref prev) = self.prev_hash {
            hasher.update(prev.as_bytes());
        }

        hex::encode(hasher.finalize())
    }

    /// Podpisuje snapshot używając klucza derywowanego z seed
    pub fn sign(&mut self, seed: &SecretBox<[u8; 32]>) {
        use hmac::{Hmac, Mac};
        use sha2::Sha256;

        // Derywuj klucz do podpisywania
        let sign_key: SecretBox<[u8; 32]> = derive_subkey_fixed(seed, "ALFA:snapshot:sign");

        // HMAC-SHA256
        let mut mac = Hmac::<Sha256>::new_from_slice(sign_key.expose_secret())
            .expect("HMAC key size invalid");

        let hash = self.compute_hash();
        mac.update(hash.as_bytes());

        self.signature = hex::encode(mac.finalize().into_bytes());
    }

    /// Weryfikuje podpis snapshotu
    pub fn verify(&self, seed: &SecretBox<[u8; 32]>) -> bool {
        use hmac::{Hmac, Mac};
        use sha2::Sha256;

        let sign_key: SecretBox<[u8; 32]> = derive_subkey_fixed(seed, "ALFA:snapshot:sign");

        let mut mac = Hmac::<Sha256>::new_from_slice(sign_key.expose_secret())
            .expect("HMAC key size invalid");

        let hash = self.compute_hash();
        mac.update(hash.as_bytes());

        let expected = hex::decode(&self.signature).unwrap_or_default();
        mac.verify_slice(&expected).is_ok()
    }

    /// Zapisuje snapshot do pliku
    pub fn save<P: AsRef<Path>>(&self, path: P) -> Result<()> {
        let json = serde_json::to_string_pretty(self)?;
        std::fs::write(path, json)?;
        Ok(())
    }

    /// Wczytuje snapshot z pliku
    pub fn load<P: AsRef<Path>>(path: P) -> Result<Self> {
        let json = std::fs::read_to_string(path)?;
        let snapshot: PqxSnapshot = serde_json::from_str(&json)?;
        Ok(snapshot)
    }
}

/// Manager snapshotów
pub struct SnapshotManager {
    /// Katalog ze snapshotami
    snapshots_dir: PathBuf,

    /// Maksymalna liczba snapshotów do przechowywania
    max_snapshots: usize,

    /// Aktualny epoch
    current_epoch: u64,

    /// Hash ostatniego snapshotu
    last_hash: Option<String>,
}

impl SnapshotManager {
    pub fn new<P: AsRef<Path>>(snapshots_dir: P, max_snapshots: usize) -> Self {
        let dir = snapshots_dir.as_ref().to_path_buf();
        std::fs::create_dir_all(&dir).ok();

        Self {
            snapshots_dir: dir,
            max_snapshots,
            current_epoch: 0,
            last_hash: None,
        }
    }

    /// Tworzy nowy snapshot
    pub fn create_snapshot(
        &mut self,
        seed: &SecretBox<[u8; 32]>,
        kdf_params: KdfParams,
        key_usages: HashMap<String, u64>,
    ) -> Result<PqxSnapshot> {
        self.current_epoch += 1;

        let mut snapshot = PqxSnapshot::new(
            self.current_epoch,
            kdf_params,
            key_usages,
            self.last_hash.clone(),
        );

        snapshot.sign(seed);
        self.last_hash = Some(snapshot.compute_hash());

        // Zapisz snapshot
        let filename = format!(
            "snapshot_{:06}_{}.json",
            self.current_epoch,
            Utc::now().format("%Y%m%d_%H%M%S")
        );
        let path = self.snapshots_dir.join(&filename);
        snapshot.save(&path)?;

        // Usuń stare snapshoty
        self.cleanup_old_snapshots()?;

        Ok(snapshot)
    }

    /// Wczytuje najnowszy snapshot
    pub fn load_latest(&self) -> Result<Option<PqxSnapshot>> {
        let mut entries: Vec<_> = std::fs::read_dir(&self.snapshots_dir)?
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.path()
                    .extension()
                    .map(|ext| ext == "json")
                    .unwrap_or(false)
            })
            .collect();

        entries.sort_by(|a, b| b.path().cmp(&a.path()));

        if let Some(entry) = entries.first() {
            let snapshot = PqxSnapshot::load(entry.path())?;
            return Ok(Some(snapshot));
        }

        Ok(None)
    }

    /// Wczytuje snapshot o danym epoch
    pub fn load_by_epoch(&self, epoch: u64) -> Result<Option<PqxSnapshot>> {
        let pattern = format!("snapshot_{:06}_", epoch);

        for entry in std::fs::read_dir(&self.snapshots_dir)? {
            let entry = entry?;
            let filename = entry.file_name().to_string_lossy().to_string();

            if filename.starts_with(&pattern) && filename.ends_with(".json") {
                let snapshot = PqxSnapshot::load(entry.path())?;
                return Ok(Some(snapshot));
            }
        }

        Ok(None)
    }

    /// Listuje wszystkie snapshoty
    pub fn list_snapshots(&self) -> Result<Vec<SnapshotInfo>> {
        let mut snapshots = Vec::new();

        for entry in std::fs::read_dir(&self.snapshots_dir)? {
            let entry = entry?;
            if entry.path().extension().map(|e| e == "json").unwrap_or(false) {
                if let Ok(snapshot) = PqxSnapshot::load(entry.path()) {
                    snapshots.push(SnapshotInfo {
                        epoch: snapshot.epoch,
                        timestamp: snapshot.timestamp,
                        path: entry.path(),
                        hash: snapshot.compute_hash(),
                    });
                }
            }
        }

        snapshots.sort_by(|a, b| b.epoch.cmp(&a.epoch));
        Ok(snapshots)
    }

    /// Weryfikuje łańcuch snapshotów
    pub fn verify_chain(&self, seed: &SecretBox<[u8; 32]>) -> Result<ChainVerification> {
        let snapshots = self.list_snapshots()?;
        let mut result = ChainVerification {
            total: snapshots.len(),
            valid: 0,
            invalid: Vec::new(),
            chain_intact: true,
        };

        let mut expected_prev_hash: Option<String> = None;

        for info in snapshots.iter().rev() {
            let snapshot = PqxSnapshot::load(&info.path)?;

            // Weryfikuj podpis
            if !snapshot.verify(seed) {
                result.invalid.push(info.epoch);
                result.chain_intact = false;
                continue;
            }

            // Weryfikuj łańcuch
            if let Some(ref expected) = expected_prev_hash {
                if snapshot.prev_hash.as_ref() != Some(expected) {
                    result.chain_intact = false;
                }
            }

            expected_prev_hash = Some(snapshot.compute_hash());
            result.valid += 1;
        }

        Ok(result)
    }

    /// Usuwa stare snapshoty
    fn cleanup_old_snapshots(&self) -> Result<()> {
        let mut entries: Vec<_> = std::fs::read_dir(&self.snapshots_dir)?
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.path()
                    .extension()
                    .map(|ext| ext == "json")
                    .unwrap_or(false)
            })
            .collect();

        if entries.len() <= self.max_snapshots {
            return Ok(());
        }

        // Sortuj od najstarszych
        entries.sort_by(|a, b| a.path().cmp(&b.path()));

        // Usuń najstarsze
        let to_remove = entries.len() - self.max_snapshots;
        for entry in entries.into_iter().take(to_remove) {
            std::fs::remove_file(entry.path())?;
        }

        Ok(())
    }

    /// Pobiera aktualny epoch
    pub fn current_epoch(&self) -> u64 {
        self.current_epoch
    }
}

/// Informacje o snapshocie
#[derive(Debug, Clone)]
pub struct SnapshotInfo {
    pub epoch: u64,
    pub timestamp: DateTime<Utc>,
    pub path: PathBuf,
    pub hash: String,
}

/// Wynik weryfikacji łańcucha
#[derive(Debug, Clone)]
pub struct ChainVerification {
    pub total: usize,
    pub valid: usize,
    pub invalid: Vec<u64>,
    pub chain_intact: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_snapshot_sign_verify() {
        let seed = SecretBox::new(Box::new([42u8; 32]));

        let mut snapshot = PqxSnapshot::new(
            1,
            KdfParams {
                algorithm: "argon2id".into(),
                time_cost: 3,
                memory_cost_kib: 65536,
                parallelism: 2,
            },
            HashMap::new(),
            None,
        );

        snapshot.sign(&seed);
        assert!(!snapshot.signature.is_empty());
        assert!(snapshot.verify(&seed));

        // Zły seed nie powinien zweryfikować
        let bad_seed = SecretBox::new(Box::new([99u8; 32]));
        assert!(!snapshot.verify(&bad_seed));
    }

    #[test]
    fn test_snapshot_chain() {
        let seed = SecretBox::new(Box::new([42u8; 32]));

        let mut s1 = PqxSnapshot::new(
            1,
            KdfParams {
                algorithm: "argon2id".into(),
                time_cost: 3,
                memory_cost_kib: 65536,
                parallelism: 2,
            },
            HashMap::new(),
            None,
        );
        s1.sign(&seed);
        let h1 = s1.compute_hash();

        let mut s2 = PqxSnapshot::new(
            2,
            KdfParams {
                algorithm: "argon2id".into(),
                time_cost: 3,
                memory_cost_kib: 65536,
                parallelism: 2,
            },
            HashMap::new(),
            Some(h1.clone()),
        );
        s2.sign(&seed);

        assert_eq!(s2.prev_hash, Some(h1));
        assert!(s2.verify(&seed));
    }
}
