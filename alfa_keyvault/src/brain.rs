//! VaultBrain - Żywy moduł samouczący się

use std::collections::{HashMap, VecDeque};
use chrono::{DateTime, Utc, Timelike, Duration};
use serde::{Deserialize, Serialize};
use parking_lot::RwLock;

use crate::error::{AlfaKeyVaultError, Result};
use crate::policy::{AutoPolicy, ThreatLevel, PolicyMetrics};

/// Zdarzenie dostępu do vault
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccessEvent {
    pub timestamp: DateTime<Utc>,
    pub event_type: AccessEventType,
    pub key_purpose: Option<String>,
    pub success: bool,
    pub duration_ms: u64,
    pub source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AccessEventType {
    Unlock,
    Lock,
    DeriveKey,
    RotateKey,
    Snapshot,
    PolicyUpdate,
    ThreatDetected,
    Lockdown,
}

/// Profil użycia vault
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageProfile {
    /// Typowe godziny dostępu (histogram 0-23)
    pub hourly_access: [u32; 24],

    /// Typowe dni tygodnia (0=niedziela, 6=sobota)
    pub daily_access: [u32; 7],

    /// Najczęściej używane klucze
    pub key_usage: HashMap<String, u64>,

    /// Średni czas sesji (sekundy)
    pub avg_session_duration: u64,

    /// Liczba sesji dziennie (średnia)
    pub avg_daily_sessions: f32,

    /// Ostatnia aktualizacja profilu
    pub updated_at: DateTime<Utc>,
}

impl Default for UsageProfile {
    fn default() -> Self {
        Self {
            hourly_access: [0; 24],
            daily_access: [0; 7],
            key_usage: HashMap::new(),
            avg_session_duration: 0,
            avg_daily_sessions: 0.0,
            updated_at: Utc::now(),
        }
    }
}

/// Mózg vault - autonomiczny moduł uczący się
pub struct VaultBrain {
    /// Historia zdarzeń (ostatnie N)
    events: RwLock<VecDeque<AccessEvent>>,

    /// Maksymalna liczba zdarzeń w historii
    max_events: usize,

    /// Profil użycia
    profile: RwLock<UsageProfile>,

    /// Aktualna polityka
    policy: RwLock<AutoPolicy>,

    /// Czy tryb lockdown jest aktywny
    lockdown_active: RwLock<bool>,

    /// Czas rozpoczęcia lockdown
    lockdown_started: RwLock<Option<DateTime<Utc>>>,

    /// Liczba nieudanych prób od ostatniego sukcesu
    failed_attempts: RwLock<u32>,

    /// Czas ostatniego sukcesu
    last_success: RwLock<Option<DateTime<Utc>>>,
}

impl VaultBrain {
    pub fn new() -> Self {
        Self {
            events: RwLock::new(VecDeque::with_capacity(1000)),
            max_events: 1000,
            profile: RwLock::new(UsageProfile::default()),
            policy: RwLock::new(AutoPolicy::default()),
            lockdown_active: RwLock::new(false),
            lockdown_started: RwLock::new(None),
            failed_attempts: RwLock::new(0),
            last_success: RwLock::new(None),
        }
    }

    pub fn with_policy(policy: AutoPolicy) -> Self {
        let brain = Self::new();
        *brain.policy.write() = policy;
        brain
    }

    /// Rejestruje zdarzenie dostępu
    pub fn record_event(&self, event: AccessEvent) {
        let mut events = self.events.write();

        // Aktualizuj profil
        self.update_profile(&event);

        // Aktualizuj liczniki
        if event.success {
            *self.failed_attempts.write() = 0;
            *self.last_success.write() = Some(event.timestamp);
        } else if matches!(event.event_type, AccessEventType::Unlock) {
            *self.failed_attempts.write() += 1;
        }

        // Dodaj zdarzenie
        if events.len() >= self.max_events {
            events.pop_front();
        }
        events.push_back(event);

        // Sprawdź czy potrzebna aktualizacja polityki
        self.check_and_update_policy();
    }

    /// Aktualizuje profil na podstawie zdarzenia
    fn update_profile(&self, event: &AccessEvent) {
        let mut profile = self.profile.write();

        // Aktualizuj histogram godzinowy
        let hour = event.timestamp.hour() as usize;
        profile.hourly_access[hour] += 1;

        // Aktualizuj histogram dzienny
        let weekday = event.timestamp.weekday().num_days_from_sunday() as usize;
        profile.daily_access[weekday] += 1;

        // Aktualizuj użycie kluczy
        if let Some(ref purpose) = event.key_purpose {
            *profile.key_usage.entry(purpose.clone()).or_insert(0) += 1;
        }

        profile.updated_at = Utc::now();
    }

    /// Sprawdza i aktualizuje politykę
    fn check_and_update_policy(&self) {
        let failed = *self.failed_attempts.read();
        let policy = self.policy.read();

        // Sprawdź lockdown
        if failed >= policy.max_failed_attempts {
            drop(policy);
            self.enter_lockdown("Max failed attempts reached");
            return;
        }

        // Sprawdź czy nietypowa godzina
        let current_hour = Utc::now().hour() as usize;
        let profile = self.profile.read();
        let avg_access = profile.hourly_access.iter().sum::<u32>() / 24;
        let is_unusual = profile.hourly_access[current_hour] < avg_access / 2;

        drop(profile);
        drop(policy);

        // Aktualizuj metryki polityki
        let mut policy = self.policy.write();
        policy.metrics.failed_attempts_24h = failed;
        policy.metrics.unusual_hour_access = is_unusual;
        policy.metrics.last_access = Some(Utc::now());
        policy.update_threat_level();
    }

    /// Wchodzi w tryb lockdown
    pub fn enter_lockdown(&self, reason: &str) {
        *self.lockdown_active.write() = true;
        *self.lockdown_started.write() = Some(Utc::now());

        self.record_event(AccessEvent {
            timestamp: Utc::now(),
            event_type: AccessEventType::Lockdown,
            key_purpose: None,
            success: false,
            duration_ms: 0,
            source: reason.to_string(),
        });

        tracing::warn!("VAULT LOCKDOWN: {}", reason);
    }

    /// Sprawdza czy lockdown jest aktywny
    pub fn is_lockdown_active(&self) -> bool {
        let active = *self.lockdown_active.read();
        if !active {
            return false;
        }

        // Sprawdź czy lockdown wygasł
        let policy = self.policy.read();
        let started = *self.lockdown_started.read();

        if let Some(start_time) = started {
            let lockout_duration = Duration::seconds(policy.lockout_seconds as i64);
            if Utc::now() - start_time > lockout_duration {
                drop(policy);
                self.exit_lockdown();
                return false;
            }
        }

        true
    }

    /// Wychodzi z lockdown (po upływie czasu lub ręcznie)
    pub fn exit_lockdown(&self) {
        *self.lockdown_active.write() = false;
        *self.lockdown_started.write() = None;
        *self.failed_attempts.write() = 0;
        tracing::info!("VAULT LOCKDOWN: Exited");
    }

    /// Sprawdza czy dostęp jest dozwolony
    pub fn is_access_allowed(&self) -> Result<()> {
        if self.is_lockdown_active() {
            return Err(AlfaKeyVaultError::LockdownActive);
        }

        let policy = self.policy.read();
        if !policy.is_access_allowed_now() {
            return Err(AlfaKeyVaultError::PolicyViolation(
                "Access not allowed at this hour".into(),
            ));
        }

        if policy.threat_level == ThreatLevel::Critical {
            return Err(AlfaKeyVaultError::ThreatDetected(
                "Critical threat level active".into(),
            ));
        }

        Ok(())
    }

    /// Przewiduje czy użytkownik będzie potrzebował dostępu
    pub fn predict_access(&self) -> bool {
        let profile = self.profile.read();
        let current_hour = Utc::now().hour() as usize;
        let avg_access = profile.hourly_access.iter().sum::<u32>() / 24;

        profile.hourly_access[current_hour] > avg_access
    }

    /// Pobiera aktualne metryki
    pub fn get_metrics(&self) -> PolicyMetrics {
        self.policy.read().metrics.clone()
    }

    /// Pobiera aktualną politykę
    pub fn get_policy(&self) -> AutoPolicy {
        self.policy.read().clone()
    }

    /// Ustawia nową politykę
    pub fn set_policy(&self, policy: AutoPolicy) {
        *self.policy.write() = policy;
    }

    /// Pobiera profil użycia
    pub fn get_profile(&self) -> UsageProfile {
        self.profile.read().clone()
    }

    /// Auto-tuning na podstawie systemu
    pub fn auto_tune(&self) {
        use sysinfo::System;

        let sys = System::new_all();
        let cpu_count = sys.cpus().len();
        let total_memory_mb = sys.total_memory() / 1024 / 1024;

        let mut policy = self.policy.write();
        policy.auto_tune_argon2(cpu_count, total_memory_mb);

        tracing::info!(
            "Auto-tuned Argon2: {}MiB, t={}, p={}",
            policy.argon2_memory_mib,
            policy.argon2_time_cost,
            policy.argon2_parallelism
        );
    }

    /// Pobiera statystyki
    pub fn get_stats(&self) -> BrainStats {
        let events = self.events.read();
        let profile = self.profile.read();
        let policy = self.policy.read();

        BrainStats {
            total_events: events.len(),
            failed_attempts: *self.failed_attempts.read(),
            lockdown_active: *self.lockdown_active.read(),
            threat_level: policy.threat_level,
            top_keys: profile
                .key_usage
                .iter()
                .take(5)
                .map(|(k, v)| (k.clone(), *v))
                .collect(),
            last_success: *self.last_success.read(),
        }
    }

    /// Eksportuje profil do JSON
    pub fn export_profile(&self) -> String {
        let profile = self.profile.read();
        serde_json::to_string_pretty(&*profile).unwrap_or_default()
    }

    /// Importuje profil z JSON
    pub fn import_profile(&self, json: &str) -> Result<()> {
        let profile: UsageProfile = serde_json::from_str(json)
            .map_err(|e| AlfaKeyVaultError::BrainError(e.to_string()))?;
        *self.profile.write() = profile;
        Ok(())
    }
}

impl Default for VaultBrain {
    fn default() -> Self {
        Self::new()
    }
}

/// Statystyki mózgu
#[derive(Debug, Clone)]
pub struct BrainStats {
    pub total_events: usize,
    pub failed_attempts: u32,
    pub lockdown_active: bool,
    pub threat_level: ThreatLevel,
    pub top_keys: Vec<(String, u64)>,
    pub last_success: Option<DateTime<Utc>>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_brain_new() {
        let brain = VaultBrain::new();
        assert!(!brain.is_lockdown_active());
    }

    #[test]
    fn test_record_event() {
        let brain = VaultBrain::new();
        brain.record_event(AccessEvent {
            timestamp: Utc::now(),
            event_type: AccessEventType::Unlock,
            key_purpose: Some("ALFA:config".into()),
            success: true,
            duration_ms: 100,
            source: "test".into(),
        });

        let stats = brain.get_stats();
        assert_eq!(stats.total_events, 1);
    }

    #[test]
    fn test_lockdown_after_failures() {
        let mut policy = AutoPolicy::default();
        policy.max_failed_attempts = 3;

        let brain = VaultBrain::with_policy(policy);

        for _ in 0..3 {
            brain.record_event(AccessEvent {
                timestamp: Utc::now(),
                event_type: AccessEventType::Unlock,
                key_purpose: None,
                success: false,
                duration_ms: 0,
                source: "test".into(),
            });
        }

        assert!(brain.is_lockdown_active());
    }

    #[test]
    fn test_access_check() {
        let brain = VaultBrain::new();
        assert!(brain.is_access_allowed().is_ok());

        brain.enter_lockdown("test");
        assert!(brain.is_access_allowed().is_err());
    }
}
