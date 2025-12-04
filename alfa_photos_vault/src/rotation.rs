//! ALFA Photos Vault - Key Rotation
//!
//! Automatic key rotation with 90-day policy (configurable).
//! Integrates with ALFA_KEYVAULT for coordinated rotation.

use std::path::{Path, PathBuf};
use chrono::{DateTime, Utc, Duration};
use serde::{Deserialize, Serialize};
use parking_lot::RwLock;

use crate::crypto::KeyManager;
use crate::error::{VaultError, VaultResult};

/// Rotation policy configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RotationPolicy {
    /// Days between rotations
    pub rotation_interval_days: u32,
    /// Whether auto-rotation is enabled
    pub auto_rotate: bool,
    /// Warning days before rotation
    pub warning_days: u32,
    /// Keep N previous epochs for recovery
    pub keep_epochs: u8,
}

impl Default for RotationPolicy {
    fn default() -> Self {
        Self {
            rotation_interval_days: 90,
            auto_rotate: true,
            warning_days: 7,
            keep_epochs: 3,
        }
    }
}

/// Rotation state persisted to disk
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RotationState {
    /// Current epoch number
    pub current_epoch: u64,
    /// Last rotation timestamp
    pub last_rotation: DateTime<Utc>,
    /// Next scheduled rotation
    pub next_rotation: DateTime<Utc>,
    /// Policy
    pub policy: RotationPolicy,
    /// Previous epoch timestamps (for recovery)
    pub epoch_history: Vec<EpochRecord>,
}

/// Record of a past epoch
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EpochRecord {
    pub epoch: u64,
    pub started: DateTime<Utc>,
    pub ended: DateTime<Utc>,
}

impl RotationState {
    /// Create initial rotation state
    pub fn new(policy: RotationPolicy) -> Self {
        let now = Utc::now();
        let next = now + Duration::days(policy.rotation_interval_days as i64);
        
        Self {
            current_epoch: 1,
            last_rotation: now,
            next_rotation: next,
            policy,
            epoch_history: Vec::new(),
        }
    }
    
    /// Check if rotation is needed
    pub fn needs_rotation(&self) -> bool {
        Utc::now() >= self.next_rotation
    }
    
    /// Check if rotation warning should be shown
    pub fn should_warn(&self) -> bool {
        let warning_time = self.next_rotation - Duration::days(self.policy.warning_days as i64);
        Utc::now() >= warning_time
    }
    
    /// Days until next rotation
    pub fn days_until_rotation(&self) -> i64 {
        let diff = self.next_rotation - Utc::now();
        diff.num_days()
    }
    
    /// Perform rotation
    pub fn rotate(&mut self) -> u64 {
        let now = Utc::now();
        
        // Record current epoch
        let record = EpochRecord {
            epoch: self.current_epoch,
            started: self.last_rotation,
            ended: now,
        };
        
        self.epoch_history.push(record);
        
        // Trim history if too long
        while self.epoch_history.len() > self.policy.keep_epochs as usize {
            self.epoch_history.remove(0);
        }
        
        // Move to next epoch
        self.current_epoch += 1;
        self.last_rotation = now;
        self.next_rotation = now + Duration::days(self.policy.rotation_interval_days as i64);
        
        self.current_epoch
    }
}

/// Key Rotation Manager
pub struct RotationManager {
    /// State file path
    state_path: PathBuf,
    /// Current state
    state: RwLock<RotationState>,
}

impl RotationManager {
    /// Load or create rotation manager
    pub fn load_or_create(vault_root: &Path) -> VaultResult<Self> {
        let state_path = vault_root.join("db").join("rotation.json");
        
        let state = if state_path.exists() {
            let data = std::fs::read(&state_path)?;
            serde_json::from_slice(&data)
                .map_err(|e| VaultError::VaultCorrupted(format!("Rotation state: {}", e)))?
        } else {
            RotationState::new(RotationPolicy::default())
        };
        
        let manager = Self {
            state_path,
            state: RwLock::new(state),
        };
        
        manager.save()?;
        
        Ok(manager)
    }
    
    /// Save state to disk
    pub fn save(&self) -> VaultResult<()> {
        let state = self.state.read();
        let data = serde_json::to_vec_pretty(&*state)?;
        
        if let Some(parent) = self.state_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        
        std::fs::write(&self.state_path, data)?;
        Ok(())
    }
    
    /// Check if rotation is needed
    pub fn needs_rotation(&self) -> bool {
        self.state.read().needs_rotation()
    }
    
    /// Check if warning should be displayed
    pub fn should_warn(&self) -> bool {
        self.state.read().should_warn()
    }
    
    /// Get current epoch
    pub fn current_epoch(&self) -> u64 {
        self.state.read().current_epoch
    }
    
    /// Days until rotation
    pub fn days_until_rotation(&self) -> i64 {
        self.state.read().days_until_rotation()
    }
    
    /// Perform rotation
    pub fn rotate(&self) -> VaultResult<u64> {
        let new_epoch = {
            let mut state = self.state.write();
            state.rotate()
        };
        
        self.save()?;
        
        log::info!("Key rotation complete. New epoch: {}", new_epoch);
        
        Ok(new_epoch)
    }
    
    /// Get rotation status
    pub fn status(&self) -> RotationStatus {
        let state = self.state.read();
        
        RotationStatus {
            current_epoch: state.current_epoch,
            last_rotation: state.last_rotation,
            next_rotation: state.next_rotation,
            days_remaining: state.days_until_rotation(),
            needs_rotation: state.needs_rotation(),
            warning: state.should_warn(),
        }
    }
    
    /// Update policy
    pub fn update_policy(&self, policy: RotationPolicy) -> VaultResult<()> {
        {
            let mut state = self.state.write();
            state.policy = policy.clone();
            
            // Recalculate next rotation based on new interval
            state.next_rotation = state.last_rotation 
                + Duration::days(policy.rotation_interval_days as i64);
        }
        
        self.save()
    }
}

/// Rotation status for display
#[derive(Debug, Clone, Serialize)]
pub struct RotationStatus {
    pub current_epoch: u64,
    pub last_rotation: DateTime<Utc>,
    pub next_rotation: DateTime<Utc>,
    pub days_remaining: i64,
    pub needs_rotation: bool,
    pub warning: bool,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_rotation_state() {
        let mut state = RotationState::new(RotationPolicy {
            rotation_interval_days: 0, // Force immediate rotation
            ..Default::default()
        });
        
        assert!(state.needs_rotation());
        
        let new_epoch = state.rotate();
        assert_eq!(new_epoch, 2);
        assert_eq!(state.epoch_history.len(), 1);
    }
    
    #[test]
    fn test_epoch_history_limit() {
        let mut state = RotationState::new(RotationPolicy {
            rotation_interval_days: 0,
            keep_epochs: 2,
            ..Default::default()
        });
        
        for _ in 0..5 {
            state.rotate();
        }
        
        // Should only keep 2 epochs
        assert_eq!(state.epoch_history.len(), 2);
        assert_eq!(state.current_epoch, 6);
    }
}
