package com.alfa.mail.ui.screens.automation

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alfa.mail.automation.BehaviorMonitor
import kotlinx.coroutines.launch

/**
 * 🧠 BEHAVIOR INSIGHTS SCREEN
 * 
 * Pokazuje:
 * ✅ Wykryte intencje użytkownika
 * ✅ Wzorce zachowań
 * ✅ Analiza emocji (z pisania)
 * ✅ Predykcje AI co użytkownik zrobi następnie
 * ✅ Kontekstowe sugestie
 */
@Composable
fun BehaviorInsightsScreen(
    onBack: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val behaviorMonitor = remember { BehaviorMonitor.getInstance(androidx.compose.ui.platform.LocalContext.current) }
    
    var insights by remember { mutableStateOf<BehaviorMonitor.BehaviorInsights?>(null) }
    
    LaunchedEffect(Unit) {
        scope.launch {
            insights = behaviorMonitor.getBehaviorInsights()
        }
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("🧠 Behavior Insights", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF1F1F1F),
                    titleContentColor = Color.White
                )
            )
        },
        containerColor = Color(0xFF0A0A0A)
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .background(Color(0xFF0A0A0A))
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            insights?.let { data ->
                // Current State Card
                item {
                    CurrentStateCard(data)
                }
                
                // Intent Predictions
                item {
                    Text(
                        "🎯 Predicted Intents",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                }
                
                items(data.recentPredictions.take(5)) { prediction ->
                    IntentPredictionCard(prediction)
                }
                
                // Behavior Patterns
                item {
                    Text(
                        "📊 Detected Patterns",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White,
                        modifier = Modifier.padding(top = 16.dp)
                    )
                }
                
                items(data.detectedPatterns) { pattern ->
                    PatternCard(pattern)
                }
            } ?: item {
                // Loading state
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(32.dp),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = Color(0xFF00D4FF))
                }
            }
        }
    }
}

@Composable
fun CurrentStateCard(insights: BehaviorMonitor.BehaviorInsights) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                brush = androidx.compose.ui.graphics.Brush.horizontalGradient(
                    colors = listOf(Color(0xFF1A237E), Color(0xFF311B92))
                ),
                shape = RoundedCornerShape(16.dp)
            )
            .padding(20.dp)
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                "Current Status",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
            
            Divider(color = Color.White.copy(alpha = 0.3f))
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("Top Intent", fontSize = 12.sp, color = Color.White.copy(alpha = 0.7f))
                    Text(
                        insights.topIntent.replace("_", " "),
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF00D4FF)
                    )
                }
                
                Column(horizontalAlignment = Alignment.End) {
                    Text("Confidence", fontSize = 12.sp, color = Color.White.copy(alpha = 0.7f))
                    Text(
                        "${(insights.averageConfidence * 100).toInt()}%",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF00FF00)
                    )
                }
            }
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("Current Emotion", fontSize = 12.sp, color = Color.White.copy(alpha = 0.7f))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(getEmotionEmoji(insights.currentEmotion), fontSize = 20.sp)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            insights.currentEmotion.capitalize(),
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }
                }
                
                Column(horizontalAlignment = Alignment.End) {
                    Text("Trend", fontSize = 12.sp, color = Color.White.copy(alpha = 0.7f))
                    Text(
                        insights.emotionalTrend.capitalize(),
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = when (insights.emotionalTrend) {
                            "improving" -> Color(0xFF00FF00)
                            "declining" -> Color(0xFFFF3333)
                            else -> Color(0xFFFFAA00)
                        }
                    )
                }
            }
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                StatChip("${insights.totalEventsLogged} events", Color(0xFF00D4FF))
                StatChip("${insights.patternsDetected} patterns", Color(0xFFFF6B9D))
            }
        }
    }
}

@Composable
fun IntentPredictionCard(prediction: BehaviorMonitor.IntentPrediction) {
    val confidenceColor = when {
        prediction.confidence > 0.8f -> Color(0xFF00FF00)
        prediction.confidence > 0.6f -> Color(0xFFFFAA00)
        else -> Color(0xFFFF6B9D)
    }
    
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFF2A2A2A), RoundedCornerShape(12.dp))
            .padding(16.dp)
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        prediction.predictedIntent.replace("_", " "),
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                    Text(
                        formatTimestamp(prediction.timestamp),
                        fontSize = 11.sp,
                        color = Color.Gray
                    )
                }
                
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(confidenceColor.copy(alpha = 0.2f))
                        .padding(horizontal = 12.dp, vertical = 6.dp)
                ) {
                    Text(
                        "${(prediction.confidence * 100).toInt()}%",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        color = confidenceColor
                    )
                }
            }
            
            Text(
                prediction.reasoning,
                fontSize = 13.sp,
                color = Color(0xFFCCCCCC)
            )
            
            Divider(color = Color(0xFF444444))
            
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    "💡 Suggested Action",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF00D4FF)
                )
                Text(
                    prediction.suggestedAction,
                    fontSize = 12.sp,
                    color = Color(0xFFAAAAAA)
                )
            }
            
            Row(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.padding(top = 4.dp)
            ) {
                prediction.contextTriggers.take(3).forEach { trigger ->
                    Box(
                        modifier = Modifier
                            .background(Color(0xFF444444), RoundedCornerShape(4.dp))
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Text(
                            trigger.replace("_", " "),
                            fontSize = 10.sp,
                            color = Color.White
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun PatternCard(pattern: BehaviorMonitor.BehaviorPattern) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFF1F1F1F), RoundedCornerShape(12.dp))
            .padding(16.dp)
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    pattern.patternName,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
                
                Text(
                    pattern.frequency.capitalize(),
                    fontSize = 12.sp,
                    color = Color(0xFF00D4FF)
                )
            }
            
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Default.AccessTime,
                    contentDescription = null,
                    tint = Color(0xFFFFAA00),
                    modifier = Modifier.size(16.dp)
                )
                Text(
                    pattern.timeWindows.joinToString(", "),
                    fontSize = 12.sp,
                    color = Color(0xFFCCCCCC)
                )
            }
            
            Text(
                "Confidence: ${(pattern.confidence * 100).toInt()}%",
                fontSize = 11.sp,
                color = Color.Gray
            )
            
            Divider(color = Color(0xFF333333))
            
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    "Triggers:",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF00D4FF)
                )
                Row(
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    modifier = Modifier.padding(start = 8.dp)
                ) {
                    pattern.triggers.take(4).forEach { trigger ->
                        Text(
                            "• ${trigger.replace("_", " ")}",
                            fontSize = 10.sp,
                            color = Color.White
                        )
                    }
                }
            }
            
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    "Typical Actions:",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF00FF88)
                )
                Column(modifier = Modifier.padding(start = 8.dp)) {
                    pattern.typicalActions.take(3).forEach { action ->
                        Text(
                            "→ ${action.replace("_", " ")}",
                            fontSize = 10.sp,
                            color = Color.White
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun StatChip(label: String, color: Color) {
    Box(
        modifier = Modifier
            .background(color.copy(alpha = 0.2f), RoundedCornerShape(8.dp))
            .padding(horizontal = 12.dp, vertical = 6.dp)
    ) {
        Text(
            label,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = color
        )
    }
}

fun getEmotionEmoji(emotion: String): String {
    return when (emotion.lowercase()) {
        "happy" -> "😊"
        "confident" -> "💪"
        "focused" -> "🎯"
        "stressed" -> "😰"
        "frustrated" -> "😤"
        "tired" -> "😴"
        "thoughtful" -> "🤔"
        else -> "😐"
    }
}

fun formatTimestamp(timestamp: Long): String {
    val now = System.currentTimeMillis()
    val diff = now - timestamp
    
    return when {
        diff < 60000 -> "Just now"
        diff < 3600000 -> "${diff / 60000}m ago"
        diff < 86400000 -> "${diff / 3600000}h ago"
        else -> "${diff / 86400000}d ago"
    }
}
