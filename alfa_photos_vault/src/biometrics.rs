//! ALFA Photos Vault - Biometric Authentication
//!
//! PIN and biometric authentication (Android Keystore integration)

use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

use crate::error::{VaultError, VaultResult};

/// Authentication method
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum AuthMethod {
    /// PIN code
    Pin,
    /// Fingerprint
    Fingerprint,
    /// Face recognition
    Face,
    /// Pattern lock
    Pattern,
    /// Combined (e.g., PIN + Biometric)
    Combined(Vec<AuthMethod>),
}

/// Authentication configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthConfig {
    /// Primary authentication method
    pub primary_method: AuthMethod,
    /// Fallback method (if biometric fails)
    pub fallback_method: Option<AuthMethod>,
    /// Require re-auth after this many seconds
    pub timeout_seconds: u64,
    /// Lock after failed attempts
    pub max_attempts: u8,
    /// Cooldown period after lockout (seconds)
    pub lockout_duration: u64,
}

impl Default for AuthConfig {
    fn default() -> Self {
        Self {
            primary_method: AuthMethod::Pin,
            fallback_method: None,
            timeout_seconds: 300, // 5 minutes
            max_attempts: 5,
            lockout_duration: 300, // 5 minutes
        }
    }
}

/// Authentication state
#[derive(Debug, Clone)]
pub struct AuthState {
    /// Is authenticated
    pub authenticated: bool,
    /// Authentication time
    pub auth_time: Option<DateTime<Utc>>,
    /// Failed attempts
    pub failed_attempts: u8,
    /// Locked until
    pub locked_until: Option<DateTime<Utc>>,
}

impl Default for AuthState {
    fn default() -> Self {
        Self {
            authenticated: false,
            auth_time: None,
            failed_attempts: 0,
            locked_until: None,
        }
    }
}

/// Biometric authenticator (stub - actual implementation is platform-specific)
pub struct Biometrics {
    config: AuthConfig,
    state: AuthState,
}

impl Biometrics {
    /// Create new biometrics handler
    pub fn new(config: AuthConfig) -> Self {
        Self {
            config,
            state: AuthState::default(),
        }
    }
    
    /// Check if locked out
    pub fn is_locked(&self) -> bool {
        if let Some(until) = self.state.locked_until {
            Utc::now() < until
        } else {
            false
        }
    }
    
    /// Check if authentication has expired
    pub fn is_expired(&self) -> bool {
        if let Some(auth_time) = self.state.auth_time {
            let elapsed = (Utc::now() - auth_time).num_seconds();
            elapsed > self.config.timeout_seconds as i64
        } else {
            true
        }
    }
    
    /// Authenticate with PIN
    pub fn authenticate_pin(&mut self, _pin: &str, verify: impl Fn(&str) -> bool) -> VaultResult<()> {
        if self.is_locked() {
            return Err(VaultError::TooManyAttempts);
        }
        
        if verify(_pin) {
            self.state.authenticated = true;
            self.state.auth_time = Some(Utc::now());
            self.state.failed_attempts = 0;
            self.state.locked_until = None;
            Ok(())
        } else {
            self.state.failed_attempts += 1;
            
            if self.state.failed_attempts >= self.config.max_attempts {
                self.state.locked_until = Some(
                    Utc::now() + chrono::Duration::seconds(self.config.lockout_duration as i64)
                );
                Err(VaultError::TooManyAttempts)
            } else {
                Err(VaultError::InvalidPin)
            }
        }
    }
    
    /// Authenticate with biometric (platform callback)
    #[cfg(feature = "android")]
    pub fn authenticate_biometric(&mut self, callback: impl FnOnce() -> bool) -> VaultResult<()> {
        if self.is_locked() {
            return Err(VaultError::TooManyAttempts);
        }
        
        if callback() {
            self.state.authenticated = true;
            self.state.auth_time = Some(Utc::now());
            self.state.failed_attempts = 0;
            Ok(())
        } else {
            self.state.failed_attempts += 1;
            Err(VaultError::BiometricFailed)
        }
    }
    
    /// Lock (clear authentication)
    pub fn lock(&mut self) {
        self.state.authenticated = false;
        self.state.auth_time = None;
    }
    
    /// Get remaining attempts
    pub fn remaining_attempts(&self) -> u8 {
        self.config.max_attempts.saturating_sub(self.state.failed_attempts)
    }
    
    /// Get lockout remaining time (seconds)
    pub fn lockout_remaining(&self) -> Option<i64> {
        self.state.locked_until.map(|until| {
            (until - Utc::now()).num_seconds().max(0)
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_pin_auth() {
        let config = AuthConfig::default();
        let mut bio = Biometrics::new(config);
        
        // Correct PIN
        assert!(bio.authenticate_pin("1234", |p| p == "1234").is_ok());
        assert!(bio.state.authenticated);
        
        // Lock and try wrong PIN
        bio.lock();
        assert!(!bio.state.authenticated);
        
        assert!(bio.authenticate_pin("wrong", |p| p == "1234").is_err());
        assert_eq!(bio.state.failed_attempts, 1);
    }
    
    #[test]
    fn test_lockout() {
        let config = AuthConfig {
            max_attempts: 3,
            ..Default::default()
        };
        let mut bio = Biometrics::new(config);
        
        // Fail 3 times
        for _ in 0..3 {
            let _ = bio.authenticate_pin("wrong", |_| false);
        }
        
        // Should be locked
        assert!(bio.is_locked());
        assert!(matches!(
            bio.authenticate_pin("1234", |_| true),
            Err(VaultError::TooManyAttempts)
        ));
    }
}
