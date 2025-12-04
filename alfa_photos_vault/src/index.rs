//! ALFA Photos Vault - Photo Index (Encrypted Database)
//!
//! Stores photo metadata in an encrypted SQLite database.

use std::path::{Path, PathBuf};
use rusqlite::{Connection, params};
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};
use std::sync::Arc;
use parking_lot::Mutex;

use crate::crypto::{KeyManager, encrypt_xchacha, decrypt_xchacha, EncryptedData};
use crate::vault::PhotoMeta;
use crate::error::{VaultError, VaultResult};

/// Photo Index - encrypted database for photo metadata
pub struct PhotoIndex {
    /// Database connection
    conn: Mutex<Connection>,
    /// Root path
    root: PathBuf,
    /// Key manager reference
    keys: Arc<KeyManager>,
}

impl PhotoIndex {
    /// Create a new index
    pub fn create(root: &Path, keys: &Arc<KeyManager>) -> VaultResult<Self> {
        let db_path = root.join("db").join("index.db");
        let conn = Connection::open(&db_path)?;
        
        // Create tables
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS photos (
                id TEXT PRIMARY KEY,
                data BLOB NOT NULL,
                created_at TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS tags (
                photo_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (photo_id, tag),
                FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_tags ON tags(tag);
            CREATE INDEX IF NOT EXISTS idx_created ON photos(created_at);
            "#,
        )?;
        
        Ok(Self {
            conn: Mutex::new(conn),
            root: root.to_path_buf(),
            keys: Arc::clone(keys),
        })
    }
    
    /// Open existing index
    pub fn open(root: &Path, keys: &Arc<KeyManager>) -> VaultResult<Self> {
        let db_path = root.join("db").join("index.db");
        
        if !db_path.exists() {
            return Err(VaultError::IndexCorrupted("Database not found".into()));
        }
        
        let conn = Connection::open(&db_path)?;
        
        Ok(Self {
            conn: Mutex::new(conn),
            root: root.to_path_buf(),
            keys: Arc::clone(keys),
        })
    }
    
    /// Add a photo to the index
    pub fn add_photo(&self, meta: &PhotoMeta) -> VaultResult<()> {
        // Encrypt metadata
        let meta_json = serde_json::to_vec(meta)?;
        let encrypted = encrypt_xchacha(self.keys.index_key(), &meta_json)?;
        let encrypted_bytes = encrypted.to_bytes();
        
        let conn = self.conn.lock();
        conn.execute(
            "INSERT OR REPLACE INTO photos (id, data, created_at) VALUES (?1, ?2, ?3)",
            params![meta.id, encrypted_bytes, meta.imported_at.to_rfc3339()],
        )?;
        
        // Add tags
        for tag in &meta.tags {
            conn.execute(
                "INSERT OR IGNORE INTO tags (photo_id, tag) VALUES (?1, ?2)",
                params![meta.id, tag],
            )?;
        }
        
        Ok(())
    }
    
    /// Get photo metadata by ID
    pub fn get_photo(&self, id: &str) -> VaultResult<PhotoMeta> {
        let conn = self.conn.lock();
        
        let encrypted_bytes: Vec<u8> = conn
            .query_row(
                "SELECT data FROM photos WHERE id = ?1",
                params![id],
                |row| row.get(0),
            )
            .map_err(|_| VaultError::PhotoNotFound(id.to_string()))?;
        
        // Decrypt metadata
        let encrypted = EncryptedData::from_bytes_xchacha(&encrypted_bytes)?;
        let meta_json = decrypt_xchacha(self.keys.index_key(), &encrypted)?;
        
        serde_json::from_slice(&meta_json)
            .map_err(|e| VaultError::DeserializationError(e.to_string()))
    }
    
    /// List all photos
    pub fn list_all(&self) -> VaultResult<Vec<PhotoMeta>> {
        let conn = self.conn.lock();
        
        let mut stmt = conn.prepare("SELECT data FROM photos ORDER BY created_at DESC")?;
        let rows = stmt.query_map([], |row| {
            let data: Vec<u8> = row.get(0)?;
            Ok(data)
        })?;
        
        let mut photos = Vec::new();
        for row in rows {
            if let Ok(encrypted_bytes) = row {
                if let Ok(encrypted) = EncryptedData::from_bytes_xchacha(&encrypted_bytes) {
                    if let Ok(meta_json) = decrypt_xchacha(self.keys.index_key(), &encrypted) {
                        if let Ok(meta) = serde_json::from_slice::<PhotoMeta>(&meta_json) {
                            photos.push(meta);
                        }
                    }
                }
            }
        }
        
        Ok(photos)
    }
    
    /// List hidden photos only
    pub fn list_hidden(&self) -> VaultResult<Vec<PhotoMeta>> {
        let all = self.list_all()?;
        Ok(all.into_iter().filter(|p| p.is_hidden).collect())
    }
    
    /// List favorites only
    pub fn list_favorites(&self) -> VaultResult<Vec<PhotoMeta>> {
        let all = self.list_all()?;
        Ok(all.into_iter().filter(|p| p.is_favorite).collect())
    }
    
    /// Search by tag
    pub fn search_by_tag(&self, tag: &str) -> VaultResult<Vec<PhotoMeta>> {
        let conn = self.conn.lock();
        
        let mut stmt = conn.prepare(
            "SELECT p.data FROM photos p 
             INNER JOIN tags t ON p.id = t.photo_id 
             WHERE t.tag = ?1"
        )?;
        
        let rows = stmt.query_map(params![tag], |row| {
            let data: Vec<u8> = row.get(0)?;
            Ok(data)
        })?;
        
        let mut photos = Vec::new();
        for row in rows {
            if let Ok(encrypted_bytes) = row {
                if let Ok(encrypted) = EncryptedData::from_bytes_xchacha(&encrypted_bytes) {
                    if let Ok(meta_json) = decrypt_xchacha(self.keys.index_key(), &encrypted) {
                        if let Ok(meta) = serde_json::from_slice::<PhotoMeta>(&meta_json) {
                            photos.push(meta);
                        }
                    }
                }
            }
        }
        
        Ok(photos)
    }
    
    /// Update photo metadata
    pub fn update_photo(&self, meta: &PhotoMeta) -> VaultResult<()> {
        self.add_photo(meta) // Uses INSERT OR REPLACE
    }
    
    /// Remove photo from index
    pub fn remove_photo(&self, id: &str) -> VaultResult<()> {
        let conn = self.conn.lock();
        
        conn.execute("DELETE FROM tags WHERE photo_id = ?1", params![id])?;
        conn.execute("DELETE FROM photos WHERE id = ?1", params![id])?;
        
        Ok(())
    }
    
    /// Count photos
    pub fn count(&self) -> VaultResult<usize> {
        let conn = self.conn.lock();
        
        let count: i64 = conn.query_row(
            "SELECT COUNT(*) FROM photos",
            [],
            |row| row.get(0),
        )?;
        
        Ok(count as usize)
    }
    
    /// Find duplicates by perceptual hash
    pub fn find_duplicates(&self) -> VaultResult<Vec<Vec<PhotoMeta>>> {
        let all = self.list_all()?;
        
        // Group by phash
        let mut hash_map: std::collections::HashMap<String, Vec<PhotoMeta>> = 
            std::collections::HashMap::new();
        
        for photo in all {
            if let Some(ref phash) = photo.phash {
                hash_map
                    .entry(phash.clone())
                    .or_insert_with(Vec::new)
                    .push(photo);
            }
        }
        
        // Return groups with more than 1 photo
        Ok(hash_map
            .into_values()
            .filter(|group| group.len() > 1)
            .collect())
    }
    
    /// Get statistics
    pub fn stats(&self) -> VaultResult<IndexStats> {
        let photos = self.list_all()?;
        
        let total = photos.len();
        let hidden = photos.iter().filter(|p| p.is_hidden).count();
        let favorites = photos.iter().filter(|p| p.is_favorite).count();
        let total_size: u64 = photos.iter().map(|p| p.original_size).sum();
        let encrypted_size: u64 = photos.iter().map(|p| p.encrypted_size).sum();
        
        Ok(IndexStats {
            total_photos: total,
            hidden_photos: hidden,
            favorite_photos: favorites,
            total_size,
            encrypted_size,
        })
    }
}

/// Index statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexStats {
    pub total_photos: usize,
    pub hidden_photos: usize,
    pub favorite_photos: usize,
    pub total_size: u64,
    pub encrypted_size: u64,
}
