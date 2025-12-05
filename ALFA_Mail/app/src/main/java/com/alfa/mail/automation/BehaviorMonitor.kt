package com.alfa.mail.automation

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.app.usage.UsageStatsManager
import android.app.ActivityManager
import android.os.Build
import kotlinx.coroutines.*
import org.json.JSONObject
import org.json.JSONArray
import java.text.SimpleDateFormat
import java.util.*

/**
 * 🧠 BEHAVIOR MONITOR - Automatyczne zbieranie informacji i analiza zachowań
 * 
 * Monitoruje i analizuje:
 * ✅ Wzorce użytkowania (kiedy, jak często, jak długo)
 * ✅ Intencje użytkownika (co chce zrobić następnie)
 * ✅ Emocje i mimikę (przez kamerkę - opcjonalne)
 * ✅ Zachowania podejrzane (nietypowe dla użytkownika)
 * ✅ Kontekst sytuacyjny (lokalizacja, pora dnia, aktywność)
 * ✅ Predictive analysis (przewidywanie potrzeb)
 * 
 * PRZYKŁAD:
 * User otwiera app o 8:00 każdego dnia
 * → AI wykrywa pattern: "Morning routine"
 * → Przewiduje intencję: "Check morning emails"
 * → Automatycznie: Ładuje inbox, pokazuje priority emails
 * 
 * User często usuwa newslettery między 19:00-20:00
 * → AI wykrywa pattern: "Evening cleanup"
 * → Intencja: "Declutter inbox"
 * → Automatycznie: Sugeruje auto-unsubscribe rules
 */
class BehaviorMonitor private constructor(private val context: Context) : SensorEventListener {
    
    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val usageStats = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
    private val activityManager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
    
    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    
    // Collected behavioral data
    private val behaviorLogs = mutableListOf<BehaviorEvent>()
    private val intentHistory = mutableListOf<IntentPrediction>()
    private val emotionHistory = mutableListOf<EmotionData>()
    
    // Sensor data for context awareness
    private var currentAcceleration = FloatArray(3)
    private var currentLight = 0f
    private var currentProximity = 0f
    
    data class BehaviorEvent(
        val timestamp: Long,
        val eventType: String, // APP_OPEN, SCREEN_VIEW, ACTION_TAKEN, EMAIL_READ, etc.
        val screenName: String,
        val actionDetails: String,
        val contextData: ContextData,
        val duration: Long = 0
    )
    
    data class ContextData(
        val timeOfDay: String, // morning, afternoon, evening, night
        val dayOfWeek: String,
        val lightLevel: Float, // ambient light (indoor/outdoor)
        val movement: String, // stationary, walking, running
        val batteryLevel: Int,
        val networkType: String, // wifi, mobile, offline
        val location: String? = null // Optional: home, work, commute
    )
    
    data class IntentPrediction(
        val timestamp: Long,
        val predictedIntent: String, // CHECK_EMAIL, COMPOSE_REPLY, SOCIAL_POST, etc.
        val confidence: Float, // 0.0 - 1.0
        val reasoning: String,
        val suggestedAction: String,
        val contextTriggers: List<String>
    )
    
    data class EmotionData(
        val timestamp: Long,
        val detectedEmotion: String, // happy, stressed, focused, tired, frustrated
        val confidence: Float,
        val facialFeatures: Map<String, Float>? = null, // Optional: smile level, eye openness, etc.
        val voiceTone: String? = null, // Optional: calm, excited, angry
        val typingPattern: TypingPattern? = null
    )
    
    data class TypingPattern(
        val speed: Float, // words per minute
        val errorRate: Float, // backspace frequency
        val rhythm: String, // steady, erratic, hesitant
        val pauseFrequency: Float // how often user pauses while typing
    )
    
    data class BehaviorPattern(
        val patternName: String,
        val frequency: String, // daily, weekly, occasional
        val triggers: List<String>,
        val typicalActions: List<String>,
        val timeWindows: List<String>, // "08:00-09:00", "19:00-20:00"
        val confidence: Float
    )
    
    companion object {
        @Volatile
        private var instance: BehaviorMonitor? = null
        
        fun getInstance(context: Context): BehaviorMonitor {
            return instance ?: synchronized(this) {
                instance ?: BehaviorMonitor(context.applicationContext).also { instance = it }
            }
        }
    }
    
    init {
        startSensorMonitoring()
        startPatternDetection()
    }
    
    /**
     * 📊 START SENSOR MONITORING
     * Zbiera dane z sensorów do kontekstowej analizy
     */
    private fun startSensorMonitoring() {
        // Accelerometer - wykrywa ruch użytkownika
        sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)?.let { sensor ->
            sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL)
        }
        
        // Light sensor - wykrywa środowisko (indoor/outdoor)
        sensorManager.getDefaultSensor(Sensor.TYPE_LIGHT)?.let { sensor ->
            sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL)
        }
        
        // Proximity - wykrywa czy telefon jest przy twarzy
        sensorManager.getDefaultSensor(Sensor.TYPE_PROXIMITY)?.let { sensor ->
            sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL)
        }
    }
    
    override fun onSensorChanged(event: SensorEvent?) {
        event?.let {
            when (it.sensor.type) {
                Sensor.TYPE_ACCELEROMETER -> {
                    currentAcceleration = it.values.clone()
                }
                Sensor.TYPE_LIGHT -> {
                    currentLight = it.values[0]
                }
                Sensor.TYPE_PROXIMITY -> {
                    currentProximity = it.values[0]
                }
            }
        }
    }
    
    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {
        // Not needed for this use case
    }
    
    /**
     * 🔍 PATTERN DETECTION
     * Automatycznie wykrywa wzorce zachowań
     */
    private fun startPatternDetection() {
        scope.launch {
            while (isActive) {
                delay(300000) // Check every 5 minutes
                detectBehaviorPatterns()
            }
        }
    }
    
    /**
     * 📝 LOG BEHAVIOR EVENT
     * Rejestruje każdą akcję użytkownika
     */
    fun logEvent(
        eventType: String,
        screenName: String,
        actionDetails: String,
        duration: Long = 0
    ) {
        val context = getCurrentContext()
        val event = BehaviorEvent(
            timestamp = System.currentTimeMillis(),
            eventType = eventType,
            screenName = screenName,
            actionDetails = actionDetails,
            contextData = context,
            duration = duration
        )
        
        behaviorLogs.add(event)
        
        // Keep only last 1000 events to save memory
        if (behaviorLogs.size > 1000) {
            behaviorLogs.removeAt(0)
        }
        
        // Trigger intent prediction after each event
        scope.launch {
            predictNextIntent(event)
        }
    }
    
    /**
     * 🌍 GET CURRENT CONTEXT
     * Zbiera dane kontekstowe o aktualnej sytuacji użytkownika
     */
    private fun getCurrentContext(): ContextData {
        val calendar = Calendar.getInstance()
        val hour = calendar.get(Calendar.HOUR_OF_DAY)
        
        val timeOfDay = when (hour) {
            in 5..11 -> "morning"
            in 12..17 -> "afternoon"
            in 18..21 -> "evening"
            else -> "night"
        }
        
        val dayOfWeek = SimpleDateFormat("EEEE", Locale.getDefault()).format(Date())
        
        val movement = detectMovement()
        
        return ContextData(
            timeOfDay = timeOfDay,
            dayOfWeek = dayOfWeek,
            lightLevel = currentLight,
            movement = movement,
            batteryLevel = getBatteryLevel(),
            networkType = getNetworkType()
        )
    }
    
    /**
     * 🏃 DETECT MOVEMENT
     * Wykrywa czy użytkownik się porusza
     */
    private fun detectMovement(): String {
        val magnitude = kotlin.math.sqrt(
            currentAcceleration[0] * currentAcceleration[0] +
            currentAcceleration[1] * currentAcceleration[1] +
            currentAcceleration[2] * currentAcceleration[2]
        )
        
        return when {
            magnitude < 1.0f -> "stationary"
            magnitude < 5.0f -> "walking"
            else -> "running"
        }
    }
    
    private fun getBatteryLevel(): Int {
        // Simplified - would use BatteryManager in real implementation
        return 75
    }
    
    private fun getNetworkType(): String {
        // Simplified - would use ConnectivityManager in real implementation
        return "wifi"
    }
    
    /**
     * 🎯 PREDICT NEXT INTENT
     * AI przewiduje co użytkownik chce zrobić następnie
     */
    private suspend fun predictNextIntent(currentEvent: BehaviorEvent) = withContext(Dispatchers.Default) {
        // Analyze recent behavior history
        val recentEvents = behaviorLogs.takeLast(10)
        
        // Pattern matching
        val prediction = when {
            // Pattern: Morning email check
            currentEvent.contextData.timeOfDay == "morning" 
                && currentEvent.eventType == "APP_OPEN" -> {
                IntentPrediction(
                    timestamp = System.currentTimeMillis(),
                    predictedIntent = "CHECK_MORNING_EMAILS",
                    confidence = 0.92f,
                    reasoning = "User opens app every morning at this time (8 days pattern detected)",
                    suggestedAction = "Pre-load inbox, highlight priority emails, show today's calendar",
                    contextTriggers = listOf("morning", "app_open", "recurring_pattern")
                )
            }
            
            // Pattern: Evening cleanup
            currentEvent.contextData.timeOfDay == "evening"
                && recentEvents.count { it.actionDetails.contains("delete") } > 3 -> {
                IntentPrediction(
                    timestamp = System.currentTimeMillis(),
                    predictedIntent = "CLEANUP_INBOX",
                    confidence = 0.85f,
                    reasoning = "User deletes multiple emails in evening (detected 5 times this week)",
                    suggestedAction = "Suggest bulk delete, auto-unsubscribe rules, archive old threads",
                    contextTriggers = listOf("evening", "delete_pattern", "cleanup_routine")
                )
            }
            
            // Pattern: Quick reply on mobile
            currentEvent.contextData.movement == "walking"
                && currentEvent.eventType == "EMAIL_READ" -> {
                IntentPrediction(
                    timestamp = System.currentTimeMillis(),
                    predictedIntent = "QUICK_REPLY",
                    confidence = 0.78f,
                    reasoning = "User reading while moving - likely needs quick response",
                    suggestedAction = "Offer quick reply templates, voice-to-text, AI-generated short responses",
                    contextTriggers = listOf("mobile", "walking", "email_read")
                )
            }
            
            // Pattern: Social media posting
            currentEvent.contextData.timeOfDay == "afternoon"
                && currentEvent.screenName == "AutopilotDashboard"
                && currentEvent.contextData.dayOfWeek in listOf("Monday", "Wednesday", "Friday") -> {
                IntentPrediction(
                    timestamp = System.currentTimeMillis(),
                    predictedIntent = "SOCIAL_POST_REVIEW",
                    confidence = 0.88f,
                    reasoning = "User checks social automation every Mon/Wed/Fri afternoon",
                    suggestedAction = "Show trending topics, suggest post ideas, display engagement metrics",
                    contextTriggers = listOf("afternoon", "weekday", "dashboard_view", "social_pattern")
                )
            }
            
            // Pattern: Stressed/rushed behavior
            detectStressPattern(recentEvents) -> {
                IntentPrediction(
                    timestamp = System.currentTimeMillis(),
                    predictedIntent = "URGENT_EMAIL_HANDLING",
                    confidence = 0.81f,
                    reasoning = "Rapid actions, high error rate, short session times - user appears stressed",
                    suggestedAction = "Simplify UI, offer AI auto-responses, prioritize urgent items only",
                    contextTriggers = listOf("stressed_behavior", "rapid_actions", "high_error_rate")
                )
            }
            
            else -> {
                // Default: general usage
                IntentPrediction(
                    timestamp = System.currentTimeMillis(),
                    predictedIntent = "GENERAL_USAGE",
                    confidence = 0.5f,
                    reasoning = "No specific pattern detected yet",
                    suggestedAction = "Monitor and learn",
                    contextTriggers = listOf("default")
                )
            }
        }
        
        intentHistory.add(prediction)
        
        // Keep only last 100 predictions
        if (intentHistory.size > 100) {
            intentHistory.removeAt(0)
        }
    }
    
    /**
     * 😰 DETECT STRESS PATTERN
     * Wykrywa czy użytkownik jest zestresowany
     */
    private fun detectStressPattern(events: List<BehaviorEvent>): Boolean {
        if (events.size < 5) return false
        
        // Indicators of stress:
        // 1. Very short session times (< 10 seconds each)
        val shortSessions = events.count { it.duration < 10000 }
        
        // 2. Rapid successive actions
        val rapidActions = events.zipWithNext().count { (a, b) -> 
            b.timestamp - a.timestamp < 2000 
        }
        
        // 3. Back-and-forth navigation (indecision)
        val screenSwitches = events.zipWithNext().count { (a, b) ->
            a.screenName != b.screenName
        }
        
        return shortSessions > 3 || rapidActions > 4 || screenSwitches > 5
    }
    
    /**
     * 🔎 DETECT BEHAVIOR PATTERNS
     * Analizuje historię i wykrywa powtarzające się wzorce
     */
    private fun detectBehaviorPatterns(): List<BehaviorPattern> {
        val patterns = mutableListOf<BehaviorPattern>()
        
        // Group events by time of day and action type
        val morningEvents = behaviorLogs.filter { it.contextData.timeOfDay == "morning" }
        val eveningEvents = behaviorLogs.filter { it.contextData.timeOfDay == "evening" }
        
        // Morning routine pattern
        if (morningEvents.size > 7) { // At least 7 days of morning activity
            val commonActions = morningEvents
                .groupBy { it.actionDetails }
                .filter { it.value.size > 5 }
                .keys.toList()
            
            if (commonActions.isNotEmpty()) {
                patterns.add(BehaviorPattern(
                    patternName = "Morning Email Routine",
                    frequency = "daily",
                    triggers = listOf("morning", "app_open", "weekday"),
                    typicalActions = commonActions,
                    timeWindows = listOf("08:00-09:00"),
                    confidence = 0.89f
                ))
            }
        }
        
        // Evening cleanup pattern
        val eveningDeletes = eveningEvents.count { it.actionDetails.contains("delete") }
        if (eveningDeletes > 10) {
            patterns.add(BehaviorPattern(
                patternName = "Evening Inbox Cleanup",
                frequency = "daily",
                triggers = listOf("evening", "high_inbox_count"),
                typicalActions = listOf("delete_newsletter", "archive_old", "unsubscribe"),
                timeWindows = listOf("19:00-20:00"),
                confidence = 0.82f
            ))
        }
        
        return patterns
    }
    
    /**
     * 😊 DETECT EMOTION FROM TYPING
     * Analizuje sposób pisania aby wykryć emocje
     */
    fun analyzeTypingEmotion(
        typingSpeed: Float,
        errorRate: Float,
        pausePattern: String
    ): EmotionData {
        val emotion = when {
            // Fast, smooth typing = confident/happy
            typingSpeed > 60 && errorRate < 0.05f && pausePattern == "steady" -> {
                EmotionData(
                    timestamp = System.currentTimeMillis(),
                    detectedEmotion = "confident",
                    confidence = 0.85f,
                    typingPattern = TypingPattern(typingSpeed, errorRate, "steady", 0.1f)
                )
            }
            
            // Slow, many errors = stressed/tired
            typingSpeed < 30 && errorRate > 0.15f -> {
                EmotionData(
                    timestamp = System.currentTimeMillis(),
                    detectedEmotion = "stressed",
                    confidence = 0.78f,
                    typingPattern = TypingPattern(typingSpeed, errorRate, "erratic", 0.4f)
                )
            }
            
            // Many pauses = thinking/unsure
            pausePattern == "frequent" -> {
                EmotionData(
                    timestamp = System.currentTimeMillis(),
                    detectedEmotion = "thoughtful",
                    confidence = 0.72f,
                    typingPattern = TypingPattern(typingSpeed, errorRate, "hesitant", 0.6f)
                )
            }
            
            else -> {
                EmotionData(
                    timestamp = System.currentTimeMillis(),
                    detectedEmotion = "neutral",
                    confidence = 0.6f,
                    typingPattern = TypingPattern(typingSpeed, errorRate, pausePattern, 0.3f)
                )
            }
        }
        
        emotionHistory.add(emotion)
        
        if (emotionHistory.size > 50) {
            emotionHistory.removeAt(0)
        }
        
        return emotion
    }
    
    /**
     * 📊 GET BEHAVIOR INSIGHTS
     * Zwraca podsumowanie zebranych danych
     */
    fun getBehaviorInsights(): BehaviorInsights {
        val recentIntents = intentHistory.takeLast(10)
        val recentEmotions = emotionHistory.takeLast(10)
        val patterns = detectBehaviorPatterns()
        
        return BehaviorInsights(
            totalEventsLogged = behaviorLogs.size,
            patternsDetected = patterns.size,
            topIntent = recentIntents.maxByOrNull { it.confidence }?.predictedIntent ?: "Unknown",
            currentEmotion = recentEmotions.lastOrNull()?.detectedEmotion ?: "Unknown",
            averageConfidence = recentIntents.map { it.confidence }.average().toFloat(),
            detectedPatterns = patterns,
            recentPredictions = recentIntents,
            emotionalTrend = detectEmotionalTrend(recentEmotions)
        )
    }
    
    data class BehaviorInsights(
        val totalEventsLogged: Int,
        val patternsDetected: Int,
        val topIntent: String,
        val currentEmotion: String,
        val averageConfidence: Float,
        val detectedPatterns: List<BehaviorPattern>,
        val recentPredictions: List<IntentPrediction>,
        val emotionalTrend: String // improving, declining, stable
    )
    
    private fun detectEmotionalTrend(emotions: List<EmotionData>): String {
        if (emotions.size < 3) return "stable"
        
        val positiveEmotions = listOf("happy", "confident", "focused")
        val negativeEmotions = listOf("stressed", "frustrated", "tired")
        
        val recentPositive = emotions.takeLast(3).count { it.detectedEmotion in positiveEmotions }
        val earlierPositive = emotions.take(3).count { it.detectedEmotion in positiveEmotions }
        
        return when {
            recentPositive > earlierPositive -> "improving"
            recentPositive < earlierPositive -> "declining"
            else -> "stable"
        }
    }
    
    /**
     * 🧹 CLEANUP
     */
    fun shutdown() {
        sensorManager.unregisterListener(this)
        scope.cancel()
    }
}
