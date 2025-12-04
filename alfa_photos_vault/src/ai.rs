//! ALFA Photos Vault - Self-Healing AI Module
//!
//! Local AI that learns from user behavior and maintains vault health.
//! No cloud, no network, 100% offline.

use std::path::{Path, PathBuf};
use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc, Duration};
use parking_lot::RwLock;

use crate::error::{VaultError, VaultResult};

/// AI Configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AIConfig {
    /// Enable learning
    pub learning_enabled: bool,
    /// Max events to store
    pub max_events: usize,
    /// Auto-tag threshold
    pub auto_tag_threshold: f32,
    /// Duplicate detection sensitivity (0.0 - 1.0)
    pub duplicate_sensitivity: f32,
}

impl Default for AIConfig {
    fn default() -> Self {
        Self {
            learning_enabled: true,
            max_events: 10000,
            auto_tag_threshold: 0.8,
            duplicate_sensitivity: 0.9,
        }
    }
}

/// User action event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserEvent {
    pub timestamp: DateTime<Utc>,
    pub event_type: EventType,
    pub photo_id: String,
    pub metadata: HashMap<String, String>,
}

/// Event types for learning
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum EventType {
    PhotoViewed,
    PhotoDeleted,
    PhotoHidden,
    PhotoFavorited,
    PhotoTagged,
    PhotoShared,
    SearchPerformed,
    AlbumCreated,
}

/// Learned pattern
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LearnedPattern {
    /// Pattern ID
    pub id: String,
    /// Pattern type
    pub pattern_type: PatternType,
    /// Confidence (0.0 - 1.0)
    pub confidence: f32,
    /// Times observed
    pub occurrences: usize,
    /// Last seen
    pub last_seen: DateTime<Utc>,
    /// Associated data
    pub data: HashMap<String, String>,
}

/// Types of learned patterns
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum PatternType {
    /// User prefers certain types of photos
    PhotoPreference,
    /// User has viewing time patterns
    UsagePattern,
    /// User tends to hide certain photos
    HidingPattern,
    /// User tags similarly
    TaggingPattern,
    /// Photos often viewed together
    PhotoClustering,
}

/// Self-Healing AI
pub struct SelfHealingAI {
    /// Root path
    root: PathBuf,
    /// Configuration
    config: AIConfig,
    /// Event log
    events: RwLock<Vec<UserEvent>>,
    /// Learned patterns
    patterns: RwLock<Vec<LearnedPattern>>,
    /// Photo clusters (for grouping)
    clusters: RwLock<HashMap<String, Vec<String>>>,
    /// Last heal timestamp
    last_heal: RwLock<Option<DateTime<Utc>>>,
}

impl SelfHealingAI {
    /// Create new AI module
    pub fn new(root: &Path) -> VaultResult<Self> {
        let ai_path = root.join("ai");
        std::fs::create_dir_all(&ai_path)?;
        
        Ok(Self {
            root: root.to_path_buf(),
            config: AIConfig::default(),
            events: RwLock::new(Vec::new()),
            patterns: RwLock::new(Vec::new()),
            clusters: RwLock::new(HashMap::new()),
            last_heal: RwLock::new(None),
        })
    }
    
    /// Load existing AI state
    pub fn load(root: &Path) -> VaultResult<Self> {
        let ai = Self::new(root)?;
        
        // Load events
        let events_path = root.join("ai").join("events.json");
        if events_path.exists() {
            let data = std::fs::read_to_string(&events_path)?;
            if let Ok(events) = serde_json::from_str::<Vec<UserEvent>>(&data) {
                *ai.events.write() = events;
            }
        }
        
        // Load patterns
        let patterns_path = root.join("ai").join("patterns.json");
        if patterns_path.exists() {
            let data = std::fs::read_to_string(&patterns_path)?;
            if let Ok(patterns) = serde_json::from_str::<Vec<LearnedPattern>>(&data) {
                *ai.patterns.write() = patterns;
            }
        }
        
        Ok(ai)
    }
    
    /// Save AI state
    pub fn save(&self) -> VaultResult<()> {
        let ai_path = self.root.join("ai");
        std::fs::create_dir_all(&ai_path)?;
        
        // Save events
        let events = self.events.read();
        let events_json = serde_json::to_string_pretty(&*events)?;
        std::fs::write(ai_path.join("events.json"), events_json)?;
        
        // Save patterns
        let patterns = self.patterns.read();
        let patterns_json = serde_json::to_string_pretty(&*patterns)?;
        std::fs::write(ai_path.join("patterns.json"), patterns_json)?;
        
        Ok(())
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // EVENT TRACKING
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Record a user event
    fn record_event(&self, event_type: EventType, photo_id: &str, metadata: HashMap<String, String>) {
        if !self.config.learning_enabled {
            return;
        }
        
        let event = UserEvent {
            timestamp: Utc::now(),
            event_type,
            photo_id: photo_id.to_string(),
            metadata,
        };
        
        let mut events = self.events.write();
        events.push(event);
        
        // Trim old events
        if events.len() > self.config.max_events {
            events.drain(0..events.len() - self.config.max_events);
        }
    }
    
    /// Called when photo is imported
    pub fn on_photo_imported(&self, photo_id: &str) {
        self.record_event(EventType::PhotoViewed, photo_id, HashMap::new());
    }
    
    /// Called when photo is viewed
    pub fn on_photo_viewed(&self, photo_id: &str) {
        self.record_event(EventType::PhotoViewed, photo_id, HashMap::new());
    }
    
    /// Called when photo is deleted
    pub fn on_photo_deleted(&self, photo_id: &str) {
        self.record_event(EventType::PhotoDeleted, photo_id, HashMap::new());
    }
    
    /// Called when photo is hidden
    pub fn on_photo_hidden(&self, photo_id: &str) {
        self.record_event(EventType::PhotoHidden, photo_id, HashMap::new());
    }
    
    /// Called when photo is favorited
    pub fn on_photo_favorited(&self, photo_id: &str) {
        self.record_event(EventType::PhotoFavorited, photo_id, HashMap::new());
    }
    
    /// Called when photo is tagged
    pub fn on_photo_tagged(&self, photo_id: &str, tag: &str) {
        let mut metadata = HashMap::new();
        metadata.insert("tag".to_string(), tag.to_string());
        self.record_event(EventType::PhotoTagged, photo_id, metadata);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // LEARNING & PREDICTIONS
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Analyze events and learn patterns
    pub fn learn(&self) -> VaultResult<usize> {
        let events = self.events.read();
        let mut new_patterns = 0;
        
        // Count event types per photo
        let mut photo_events: HashMap<String, HashMap<EventType, usize>> = HashMap::new();
        
        for event in events.iter() {
            photo_events
                .entry(event.photo_id.clone())
                .or_insert_with(HashMap::new)
                .entry(event.event_type.clone())
                .and_modify(|c| *c += 1)
                .or_insert(1);
        }
        
        // Learn hiding patterns
        let mut patterns = self.patterns.write();
        
        for (photo_id, event_counts) in &photo_events {
            // Detect hiding pattern
            if let Some(&hidden_count) = event_counts.get(&EventType::PhotoHidden) {
                if hidden_count > 0 {
                    let pattern = LearnedPattern {
                        id: format!("hide_{}", photo_id),
                        pattern_type: PatternType::HidingPattern,
                        confidence: 1.0,
                        occurrences: hidden_count,
                        last_seen: Utc::now(),
                        data: HashMap::new(),
                    };
                    
                    if !patterns.iter().any(|p| p.id == pattern.id) {
                        patterns.push(pattern);
                        new_patterns += 1;
                    }
                }
            }
            
            // Detect favorite patterns
            if let Some(&fav_count) = event_counts.get(&EventType::PhotoFavorited) {
                if fav_count > 0 {
                    let pattern = LearnedPattern {
                        id: format!("fav_{}", photo_id),
                        pattern_type: PatternType::PhotoPreference,
                        confidence: 1.0,
                        occurrences: fav_count,
                        last_seen: Utc::now(),
                        data: HashMap::new(),
                    };
                    
                    if !patterns.iter().any(|p| p.id == pattern.id) {
                        patterns.push(pattern);
                        new_patterns += 1;
                    }
                }
            }
        }
        
        drop(patterns);
        self.save()?;
        
        Ok(new_patterns)
    }
    
    /// Predict if user might want to hide a photo (based on learned patterns)
    pub fn predict_should_hide(&self, photo_id: &str) -> f32 {
        let patterns = self.patterns.read();
        
        // Look for hiding patterns
        for pattern in patterns.iter() {
            if pattern.pattern_type == PatternType::HidingPattern 
                && pattern.id.contains(photo_id) 
            {
                return pattern.confidence;
            }
        }
        
        0.0
    }
    
    /// Suggest tags based on learned patterns
    pub fn suggest_tags(&self, photo_id: &str) -> Vec<String> {
        let events = self.events.read();
        let mut tag_counts: HashMap<String, usize> = HashMap::new();
        
        // Count tags used
        for event in events.iter() {
            if event.event_type == EventType::PhotoTagged {
                if let Some(tag) = event.metadata.get("tag") {
                    *tag_counts.entry(tag.clone()).or_insert(0) += 1;
                }
            }
        }
        
        // Return most common tags
        let mut tags: Vec<_> = tag_counts.into_iter().collect();
        tags.sort_by(|a, b| b.1.cmp(&a.1));
        
        tags.into_iter()
            .take(5)
            .map(|(tag, _)| tag)
            .collect()
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SELF-HEALING
    // ═══════════════════════════════════════════════════════════════════════
    
    /// Run self-healing process
    pub fn heal(&mut self) -> VaultResult<usize> {
        let mut fixes = 0;
        
        // 1. Clean up old events (older than 90 days)
        let cutoff = Utc::now() - Duration::days(90);
        {
            let mut events = self.events.write();
            let original_len = events.len();
            events.retain(|e| e.timestamp > cutoff);
            fixes += original_len - events.len();
        }
        
        // 2. Remove stale patterns
        {
            let mut patterns = self.patterns.write();
            let original_len = patterns.len();
            patterns.retain(|p| p.last_seen > cutoff);
            fixes += original_len - patterns.len();
        }
        
        // 3. Consolidate duplicate patterns
        {
            let mut patterns = self.patterns.write();
            let mut seen_ids: std::collections::HashSet<String> = std::collections::HashSet::new();
            patterns.retain(|p| {
                if seen_ids.contains(&p.id) {
                    fixes += 1;
                    false
                } else {
                    seen_ids.insert(p.id.clone());
                    true
                }
            });
        }
        
        // 4. Re-learn from cleaned data
        self.learn()?;
        
        // Update last heal time
        *self.last_heal.write() = Some(Utc::now());
        
        // Save state
        self.save()?;
        
        Ok(fixes)
    }
    
    /// Get health status
    pub fn health_status(&self) -> AIHealthStatus {
        let events = self.events.read();
        let patterns = self.patterns.read();
        
        AIHealthStatus {
            total_events: events.len(),
            total_patterns: patterns.len(),
            last_heal: *self.last_heal.read(),
            learning_enabled: self.config.learning_enabled,
        }
    }
}

/// AI Health Status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AIHealthStatus {
    pub total_events: usize,
    pub total_patterns: usize,
    pub last_heal: Option<DateTime<Utc>>,
    pub learning_enabled: bool,
}
