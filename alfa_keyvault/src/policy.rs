//! Auto-polityki bezpieczeństwa - dynamiczne reguły

use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc, Duration};
use std::collections::HashMap;

/// Poziom zagrożenia
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ThreatLevel {
    /// Normalny tryb pracy
    Normal,
    /// Podwyższona czujność
    Elevated,
    /// Wysokie zagrożenie
    High,
    /// Krytyczne - lockdown
    Critical,
}

impl Default for ThreatLevel {
    fn default() -> Self {
        Self::Normal
    }
}

impl ThreatLevel {
    pub fn from_score(score: u32) -> Self {
        match score {
            0..=20 => Self::Normal,
            21..=50 => Self::Elevated,
            51..=80 => Self::High,
            _ => Self::Critical,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Normal => "normal",
            Self::Elevated => "elevated",
            Self::High => "high",
            Self::Critical => "critical",
        }
    }
}

/// Automatyczna polityka bezpieczeństwa
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AutoPolicy {
    /// Wersja polityki
    pub version: u32,

    /// Czas automatycznego blokowania (sekundy)
    pub auto_lock_after_seconds: u64,

    /// Parametry Argon2
    pub argon2_memory_mib: u32,
    pub argon2_time_cost: u32,
    pub argon2_parallelism: u32,

    /// Maksymalna liczba nieudanych prób
    pub max_failed_attempts: u32,

    /// Czas blokady po przekroczeniu prób (sekundy)
    pub lockout_seconds: u64,

    /// Aktualny poziom zagrożenia
    pub threat_level: ThreatLevel,

    /// Interwał auto-shadow backupu (godziny)
    pub auto_shadow_interval_hours: u32,

    /// Interwał rotacji kluczy (dni)
    pub key_rotation_days: u32,

    /// Wymagana minimalna długość hasła
    pub min_password_length: usize,

    /// Wymagaj cyfr w haśle
    pub require_digits: bool,

    /// Wymagaj znaków specjalnych
    pub require_special: bool,

    /// Dozwolone godziny dostępu (0-23)
    pub allowed_hours: Option<Vec<u8>>,

    /// Ostatnia aktualizacja polityki
    pub updated_at: DateTime<Utc>,

    /// Metryki do auto-tuningu
    #[serde(default)]
    pub metrics: PolicyMetrics,
}

impl Default for AutoPolicy {
    fn default() -> Self {
        Self {
            version: 1,
            auto_lock_after_seconds: 300, // 5 minut
            argon2_memory_mib: 64,
            argon2_time_cost: 3,
            argon2_parallelism: 2,
            max_failed_attempts: 5,
            lockout_seconds: 300,
            threat_level: ThreatLevel::Normal,
            auto_shadow_interval_hours: 24,
            key_rotation_days: 90,
            min_password_length: 8,
            require_digits: true,
            require_special: false,
            allowed_hours: None,
            updated_at: Utc::now(),
            metrics: PolicyMetrics::default(),
        }
    }
}

impl AutoPolicy {
    /// Tworzy politykę dla wysokiego bezpieczeństwa
    pub fn high_security() -> Self {
        Self {
            auto_lock_after_seconds: 60,
            argon2_memory_mib: 256,
            argon2_time_cost: 4,
            argon2_parallelism: 4,
            max_failed_attempts: 3,
            lockout_seconds: 900,
            threat_level: ThreatLevel::Elevated,
            key_rotation_days: 30,
            min_password_length: 16,
            require_digits: true,
            require_special: true,
            auto_shadow_interval_hours: 6,
            ..Default::default()
        }
    }

    /// Tworzy politykę dla słabych urządzeń
    pub fn low_resource() -> Self {
        Self {
            argon2_memory_mib: 16,
            argon2_time_cost: 2,
            argon2_parallelism: 1,
            auto_lock_after_seconds: 600,
            ..Default::default()
        }
    }

    /// Sprawdza czy hasło spełnia wymagania polityki
    pub fn validate_password(&self, password: &str) -> Result<(), Vec<String>> {
        let mut errors = Vec::new();

        if password.len() < self.min_password_length {
            errors.push(format!(
                "Password must be at least {} characters",
                self.min_password_length
            ));
        }

        if self.require_digits && !password.chars().any(|c| c.is_ascii_digit()) {
            errors.push("Password must contain at least one digit".to_string());
        }

        if self.require_special && !password.chars().any(|c| !c.is_alphanumeric()) {
            errors.push("Password must contain at least one special character".to_string());
        }

        if errors.is_empty() {
            Ok(())
        } else {
            Err(errors)
        }
    }

    /// Sprawdza czy aktualna godzina jest dozwolona
    pub fn is_access_allowed_now(&self) -> bool {
        match &self.allowed_hours {
            None => true,
            Some(hours) => {
                let current_hour = Utc::now().format("%H").to_string().parse::<u8>().unwrap_or(0);
                hours.contains(&current_hour)
            }
        }
    }

    /// Oblicza wynik zagrożenia na podstawie metryk
    pub fn calculate_threat_score(&self) -> u32 {
        let mut score = 0u32;

        // Nieudane próby
        score += self.metrics.failed_attempts_24h * 10;

        // Nietypowe godziny
        if self.metrics.unusual_hour_access {
            score += 20;
        }

        // Szybkie próby (brute force?)
        if self.metrics.rapid_access_attempts {
            score += 30;
        }

        // Nowe urządzenie
        if self.metrics.new_device_detected {
            score += 15;
        }

        score.min(100)
    }

    /// Aktualizuje poziom zagrożenia na podstawie metryk
    pub fn update_threat_level(&mut self) {
        let score = self.calculate_threat_score();
        self.threat_level = ThreatLevel::from_score(score);
        self.updated_at = Utc::now();
    }

    /// Auto-tuning parametrów Argon2 na podstawie CPU
    pub fn auto_tune_argon2(&mut self, cpu_count: usize, available_memory_mb: u64) {
        // Parallelizm = max 1/2 liczby CPU
        self.argon2_parallelism = ((cpu_count / 2).max(1).min(8)) as u32;

        // Pamięć = max 1/4 dostępnej, ale nie więcej niż 512 MiB
        let target_memory = (available_memory_mb / 4).min(512) as u32;
        self.argon2_memory_mib = target_memory.max(16);

        // Time cost zależy od pamięci
        self.argon2_time_cost = if self.argon2_memory_mib >= 128 { 2 } else { 3 };

        self.updated_at = Utc::now();
    }

    /// Sprawdza czy wymagana jest rotacja kluczy
    pub fn is_rotation_required(&self, last_rotation: DateTime<Utc>) -> bool {
        let rotation_interval = Duration::days(self.key_rotation_days as i64);
        Utc::now() - last_rotation > rotation_interval
    }
}

/// Metryki do auto-tuningu
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PolicyMetrics {
    /// Nieudane próby w ciągu 24h
    pub failed_attempts_24h: u32,

    /// Dostęp o nietypowej godzinie
    pub unusual_hour_access: bool,

    /// Szybkie próby dostępu (brute force)
    pub rapid_access_attempts: bool,

    /// Wykryto nowe urządzenie
    pub new_device_detected: bool,

    /// Średni czas derywacji (ms)
    pub avg_derivation_time_ms: u64,

    /// Liczba dostępów dziennie
    pub daily_access_count: u32,

    /// Najczęściej używane klucze
    pub top_used_keys: HashMap<String, u64>,

    /// Ostatni dostęp
    pub last_access: Option<DateTime<Utc>>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_policy() {
        let policy = AutoPolicy::default();
        assert_eq!(policy.max_failed_attempts, 5);
        assert_eq!(policy.threat_level, ThreatLevel::Normal);
    }

    #[test]
    fn test_password_validation() {
        let policy = AutoPolicy::default();

        // Za krótkie
        assert!(policy.validate_password("abc").is_err());

        // Brak cyfr
        assert!(policy.validate_password("abcdefgh").is_err());

        // OK
        assert!(policy.validate_password("abcdefgh1").is_ok());
    }

    #[test]
    fn test_threat_level_from_score() {
        assert_eq!(ThreatLevel::from_score(10), ThreatLevel::Normal);
        assert_eq!(ThreatLevel::from_score(30), ThreatLevel::Elevated);
        assert_eq!(ThreatLevel::from_score(60), ThreatLevel::High);
        assert_eq!(ThreatLevel::from_score(90), ThreatLevel::Critical);
    }

    #[test]
    fn test_auto_tune() {
        let mut policy = AutoPolicy::default();
        policy.auto_tune_argon2(8, 16000);

        assert_eq!(policy.argon2_parallelism, 4);
        assert!(policy.argon2_memory_mib >= 16);
        assert!(policy.argon2_memory_mib <= 512);
    }
}
