package com.alfa.mail.ui.screens.automation

import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
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
import com.alfa.mail.automation.Gemini2Service
import com.alfa.mail.automation.SocialMediaBajery
import com.alfa.mail.automation.BehaviorMonitor
import kotlinx.coroutines.launch

/**
 * 🤖 AUTOPILOT DASHBOARD
 * 
 * Monitor wszystkich automatycznych akcji:
 * ✅ Emaile które AI odpowiedział
 * ✅ Wiadomości które AI odpisał
 * ✅ Posty które AI stworzył i opublikował
 * ✅ Engagement na soc. mediach
 * ✅ Zautomatyzowane zadania w kolejce
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AutopilotDashboardScreen(
    onBack: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val gemini = remember { Gemini2Service.getInstance(androidx.compose.ui.platform.LocalContext.current) }
    val socialBajery = remember { SocialMediaBajery.getInstance(androidx.compose.ui.platform.LocalContext.current) }
    val behaviorMonitor = remember { BehaviorMonitor.getInstance(androidx.compose.ui.platform.LocalContext.current) }
    
    // Stats state
    var emailsReplied by remember { mutableStateOf(42) }
    var messagesReplied by remember { mutableStateOf(128) }
    var postsCreated by remember { mutableStateOf(18) }
    var totalEngagement by remember { mutableStateOf(12500) }
    var isAutopilotEnabled by remember { mutableStateOf(true) }
    
    // Trending topics
    var trendingAnalysis by remember { mutableStateOf<SocialMediaBajery.TrendingAnalysis?>(null) }
    
    LaunchedEffect(Unit) {
        scope.launch {
            trendingAnalysis = socialBajery.getTrendingTopics()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("🤖 Autopilot") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    Switch(
                        checked = isAutopilotEnabled,
                        onCheckedChange = { isAutopilotEnabled = it },
                        modifier = Modifier.padding(end = 8.dp)
                    )
                }
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Status banner
            item {
                StatusBanner(
                    isEnabled = isAutopilotEnabled,
                    modifier = Modifier.fillMaxWidth()
                )
            }
            
            // Stats cards
            item {
                Text(
                    "📊 Stats",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            
            item {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    StatCard(
                        icon = "📧",
                        title = "Emaile odpowiedziane",
                        value = emailsReplied.toString(),
                        subtitle = "Dzisiaj: 7"
                    )
                    StatCard(
                        icon = "💬",
                        title = "Wiadomości",
                        value = messagesReplied.toString(),
                        subtitle = "WhatsApp, SMS, Messenger"
                    )
                    StatCard(
                        icon = "📱",
                        title = "Posty utworzone",
                        value = postsCreated.toString(),
                        subtitle = "Facebook, Instagram"
                    )
                    StatCard(
                        icon = "❤️",
                        title = "Zaangażowanie",
                        value = totalEngagement.toString(),
                        subtitle = "Likes + Comments + Shares"
                    )
                }
            }
            
            // Recent actions
            item {
                Text(
                    "⚡ Ostatnie akcje",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            
            item {
                ActionCard(
                    icon = "📧",
                    title = "Email od Jana",
                    subtitle = "Pytanie o projekt",
                    status = "✅ Odpowiedziano",
                    time = "2 min temu"
                )
                Spacer(modifier = Modifier.height(8.dp))
                ActionCard(
                    icon = "💬",
                    title = "WhatsApp od Marii",
                    subtitle = "Dostępny jutro?",
                    status = "✅ Odpisano",
                    time = "5 min temu"
                )
                Spacer(modifier = Modifier.height(8.dp))
                ActionCard(
                    icon = "📱",
                    title = "Post na Facebooku",
                    subtitle = "Ulub. artykuł o AI",
                    status = "🚀 Opublikowano",
                    time = "12 min temu"
                )
            }
            
            // Trending topics
            if (trendingAnalysis != null) {
                item {
                    Text(
                        "🔥 Trending TERAZ",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                }
                
                items(trendingAnalysis!!.topTrends) { trend ->
                    TrendCard(trend = trend)
                }
            }
            
            // Queue
            item {
                Text(
                    "⏳ W kolejce",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            
            item {
                QueueCard(
                    title = "Publikuj post na Instagramie",
                    scheduledTime = "15:30",
                    status = "Gotowy"
                )
                Spacer(modifier = Modifier.height(8.dp))
                QueueCard(
                    title = "Odpowiedź email - Maria",
                    scheduledTime = "Automatycznie",
                    status = "Czeka"
                )
            }
            
            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

@Composable
private fun StatusBanner(
    isEnabled: Boolean,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = if (isEnabled) 
                Color(0xFF4CAF50).copy(alpha = 0.2f) 
            else 
                Color(0xFFFF9800).copy(alpha = 0.2f)
        ),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            if (isEnabled) Color(0xFF4CAF50) else Color(0xFFFF9800)
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (isEnabled) {
                Icon(
                    Icons.Default.CheckCircle,
                    contentDescription = null,
                    tint = Color(0xFF4CAF50),
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        "🤖 Autopilot AKTYWNY",
                        style = MaterialTheme.typography.labelLarge,
                        color = Color(0xFF4CAF50),
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        "AI automatycznie odpowiada i publikuje",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFF4CAF50).copy(alpha = 0.7f)
                    )
                }
            } else {
                Icon(
                    Icons.Default.Warning,
                    contentDescription = null,
                    tint = Color(0xFFFF9800),
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        "⏸️ Autopilot WSTRZYMANY",
                        style = MaterialTheme.typography.labelLarge,
                        color = Color(0xFFFF9800),
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        "Włącz aby automatycznie odpowiadać",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFFFF9800).copy(alpha = 0.7f)
                    )
                }
            }
        }
    }
}

@Composable
private fun StatCard(
    icon: String,
    title: String,
    value: String,
    subtitle: String,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "$icon $title",
                    style = MaterialTheme.typography.labelMedium
                )
                Text(
                    value,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    subtitle,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun ActionCard(
    icon: String,
    title: String,
    subtitle: String,
    status: String,
    time: String
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        "$icon $title",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(
                        subtitle,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Text(
                    status,
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFF4CAF50),
                    fontWeight = FontWeight.Bold
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                time,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun TrendCard(trend: SocialMediaBajery.Trend) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        "🔥 ${trend.topic}",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        "${trend.volume} posts",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color(0xFFFF9800).copy(alpha = 0.2f))
                        .padding(8.dp)
                ) {
                    Text(
                        "${(trend.momentum * 100).toInt()}%",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFFFF9800)
                    )
                }
            }
            Spacer(modifier = Modifier.height(12.dp))
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                trend.relatedHashtags.take(3).forEach { tag ->
                    AssistChip(
                        onClick = { },
                        label = { Text(tag, style = MaterialTheme.typography.labelSmall) },
                        modifier = Modifier.height(28.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun QueueCard(
    title: String,
    scheduledTime: String,
    status: String
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "⏳ $title",
                    style = MaterialTheme.typography.labelMedium
                )
                Text(
                    scheduledTime,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Chip(
                label = { Text(status) },
                onClick = { },
                colors = ChipDefaults.chipColors(
                    containerColor = Color(0xFF2196F3).copy(alpha = 0.2f)
                )
            )
        }
    }
}

@Composable
private fun Chip(
    label: @Composable () -> Unit,
    onClick: () -> Unit,
    colors: ChipColors = ChipDefaults.chipColors()
) {
    AssistChip(
        onClick = onClick,
        label = label,
        modifier = Modifier.height(28.dp)
    )
}
