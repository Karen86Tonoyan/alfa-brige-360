//! ALFA Photos Vault - HKDF Key Derivation
//!
//! Advanced key derivation for hierarchical key structure.

use hkdf::Hkdf;
use sha2::Sha256;

use super::keys::{VaultKey, KEY_LEN};
use crate::error::{VaultError, VaultResult};

/// Derive a subkey from a parent key with context
pub fn derive_subkey(parent: &VaultKey, context: &[u8], info: &[u8]) -> VaultResult<VaultKey> {
    let hk = Hkdf::<Sha256>::new(Some(context), parent.expose());
    let mut okm = [0u8; KEY_LEN];
    
    hk.expand(info, &mut okm)
        .map_err(|e| VaultError::KeyDerivationFailed(e.to_string()))?;
    
    Ok(VaultKey::new(okm))
}

/// Derive an epoch-based key for rotation
pub fn derive_epoch_key(master: &VaultKey, epoch: u64) -> VaultResult<VaultKey> {
    let epoch_bytes = epoch.to_be_bytes();
    derive_subkey(master, &epoch_bytes, b"ALFA:EPOCH:v1")
}

/// Derive a dated key (for daily/monthly rotation)
pub fn derive_dated_key(master: &VaultKey, year: u16, month: u8, day: u8) -> VaultResult<VaultKey> {
    let mut date_context = [0u8; 4];
    date_context[0..2].copy_from_slice(&year.to_be_bytes());
    date_context[2] = month;
    date_context[3] = day;
    
    derive_subkey(master, &date_context, b"ALFA:DATE:v1")
}

/// Key derivation tree node
#[derive(Debug, Clone)]
pub struct KeyTree {
    depth: u8,
    path: Vec<u8>,
}

impl KeyTree {
    /// Create root of key tree
    pub fn root() -> Self {
        Self {
            depth: 0,
            path: Vec::new(),
        }
    }
    
    /// Derive child node
    pub fn child(&self, index: u8) -> Self {
        let mut path = self.path.clone();
        path.push(index);
        Self {
            depth: self.depth + 1,
            path,
        }
    }
    
    /// Derive key at this node
    pub fn derive_key(&self, master: &VaultKey) -> VaultResult<VaultKey> {
        let info = format!("ALFA:TREE:{}:{:?}", self.depth, self.path);
        derive_subkey(master, &self.path, info.as_bytes())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_epoch_keys_differ() {
        let master = VaultKey::generate();
        
        let k1 = derive_epoch_key(&master, 1).unwrap();
        let k2 = derive_epoch_key(&master, 2).unwrap();
        
        assert_ne!(k1.expose(), k2.expose());
    }
    
    #[test]
    fn test_key_tree() {
        let master = VaultKey::generate();
        let root = KeyTree::root();
        
        let child1 = root.child(0);
        let child2 = root.child(1);
        let grandchild = child1.child(0);
        
        let k1 = child1.derive_key(&master).unwrap();
        let k2 = child2.derive_key(&master).unwrap();
        let k3 = grandchild.derive_key(&master).unwrap();
        
        assert_ne!(k1.expose(), k2.expose());
        assert_ne!(k1.expose(), k3.expose());
    }
}
