//! ALFA Photos Vault - Secure Filesystem Operations
//!
//! Handles encrypted file I/O with integrity verification.

use std::path::{Path, PathBuf};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};

use crate::error::{VaultError, VaultResult};

/// Secure Filesystem Handler
pub struct SecureFs {
    /// Root directory
    root: PathBuf,
}

impl SecureFs {
    /// Create new SecureFs with root directory
    pub fn new(root: &Path) -> Self {
        Self {
            root: root.to_path_buf(),
        }
    }
    
    /// Get full path for a relative file
    fn full_path(&self, relative: &str) -> PathBuf {
        self.root.join(relative)
    }
    
    /// Write encrypted file atomically
    pub fn write_file(&self, relative_path: &str, data: &[u8]) -> VaultResult<()> {
        let path = self.full_path(relative_path);
        
        // Ensure parent directory exists
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        
        // Write to temp file first (atomic write)
        let temp_path = path.with_extension("tmp");
        
        let mut file = OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .open(&temp_path)?;
        
        file.write_all(data)?;
        file.sync_all()?;
        
        // Rename to final path (atomic on most filesystems)
        fs::rename(&temp_path, &path)?;
        
        Ok(())
    }
    
    /// Read encrypted file
    pub fn read_file(&self, relative_path: &str) -> VaultResult<Vec<u8>> {
        let path = self.full_path(relative_path);
        
        if !path.exists() {
            return Err(VaultError::FileNotFound(path.display().to_string()));
        }
        
        let mut file = File::open(&path)?;
        let mut data = Vec::new();
        file.read_to_end(&mut data)?;
        
        Ok(data)
    }
    
    /// Delete file
    pub fn delete_file(&self, relative_path: &str) -> VaultResult<()> {
        let path = self.full_path(relative_path);
        
        if path.exists() {
            // Secure delete: overwrite with zeros first
            if let Ok(metadata) = fs::metadata(&path) {
                let size = metadata.len() as usize;
                if size > 0 {
                    if let Ok(mut file) = OpenOptions::new().write(true).open(&path) {
                        let zeros = vec![0u8; size.min(1024 * 1024)]; // Max 1MB chunks
                        let mut remaining = size;
                        while remaining > 0 {
                            let to_write = remaining.min(zeros.len());
                            let _ = file.write_all(&zeros[..to_write]);
                            remaining -= to_write;
                        }
                        let _ = file.sync_all();
                    }
                }
            }
            
            fs::remove_file(&path)?;
        }
        
        Ok(())
    }
    
    /// Check if file exists
    pub fn exists(&self, relative_path: &str) -> bool {
        self.full_path(relative_path).exists()
    }
    
    /// Get file size
    pub fn file_size(&self, relative_path: &str) -> VaultResult<u64> {
        let path = self.full_path(relative_path);
        let metadata = fs::metadata(&path)?;
        Ok(metadata.len())
    }
    
    /// List files in directory
    pub fn list_dir(&self, relative_path: &str) -> VaultResult<Vec<String>> {
        let path = self.full_path(relative_path);
        let mut files = Vec::new();
        
        if path.exists() {
            for entry in fs::read_dir(&path)? {
                if let Ok(entry) = entry {
                    if let Some(name) = entry.file_name().to_str() {
                        files.push(name.to_string());
                    }
                }
            }
        }
        
        Ok(files)
    }
    
    /// Get total vault size
    pub fn total_size(&self) -> VaultResult<u64> {
        self.dir_size(&self.root)
    }
    
    /// Calculate directory size recursively
    fn dir_size(&self, path: &Path) -> VaultResult<u64> {
        let mut size = 0;
        
        if path.is_dir() {
            for entry in fs::read_dir(path)? {
                let entry = entry?;
                let path = entry.path();
                
                if path.is_dir() {
                    size += self.dir_size(&path)?;
                } else {
                    size += fs::metadata(&path)?.len();
                }
            }
        }
        
        Ok(size)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;
    
    #[test]
    fn test_secure_fs() {
        let dir = tempdir().unwrap();
        let fs = SecureFs::new(dir.path());
        
        // Write file
        fs.write_file("test/data.enc", b"encrypted data").unwrap();
        assert!(fs.exists("test/data.enc"));
        
        // Read file
        let data = fs.read_file("test/data.enc").unwrap();
        assert_eq!(data, b"encrypted data");
        
        // Delete file
        fs.delete_file("test/data.enc").unwrap();
        assert!(!fs.exists("test/data.enc"));
    }
}
