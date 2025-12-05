package com.alfa.mail.ui.screens.automation

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.alfa.mail.automation.AutoResponder
import com.alfa.mail.ui.components.ThinkingCard
import com.alfa.mail.ai.AiAssistService
import kotlinx.coroutines.launch

/**
 * 🤖 AUTOMATION SCREEN
 * 
 * Konfiguracja automatyzacji:
 * - AutoResponder (odpowiadanie na emaile)
 * - Social Automation (posty na FB)
 * - Therapy Reminders (przypomnienia zdrowotne)
 * - Security Monitor (blokowanie zagrożeń)
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AutomationScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val autoResponder = remember { AutoResponder.getInstance(context) }
    val scope = rememberCoroutineScope()
    
    var selectedTab by remember { mutableStateOf(0) }
    val tabs = listOf("🤖 AutoRespond", "📱 Social", "💊 Therapy", "🔒 Security")
    
    // AutoResponder state
    var rules by remember { mutableStateOf(autoResponder.getRules()) }
    var showTestDialog by remember { mutableStateOf(false) }
    
    // Thinking card state
    var showThinking by remember { mutableStateOf(false) }
    var aiThoughts by remember { mutableStateOf<List<AiAssistService.ThinkingStep>>(emptyList()) }
    var aiProgress by remember { mutableStateOf("") }
    var aiComplete by remember { mutableStateOf(false) }
    var aiError by remember { mutableStateOf<String?>(null) }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("⚙️ Automatyzacje") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            // Tabs
            TabRow(selectedTabIndex = selectedTab) {
                tabs.forEachIndexed { index, tab ->
                    Tab(
                        text = { Text(tab, style = MaterialTheme.typography.labelSmall) },
                        selected = selectedTab == index,
                        onClick = { selectedTab = index }
                    )
                }
            }
            
            // Content
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp)
            ) {
                when (selectedTab) {
                    0 -> AutoResponderTab(
                        rules = rules,
                        onRuleToggle = { ruleId, enabled ->
                            autoResponder.toggleRule(ruleId, enabled)
                            rules = autoResponder.getRules()
                        },
                        onTest = { showTestDialog = true }
                    )
                    1 -> SocialAutomationTab()
                    2 -> TherapyReminderTab()
                    3 -> SecurityMonitorTab()
                }
                
                // Thinking card
                if (showThinking) {
                    ThinkingCard(
                        thoughts = aiThoughts,
                        currentProgress = aiProgress,
                        finalText = null,
                        isComplete = aiComplete,
                        error = aiError,
                        onDismiss = {
                            showThinking = false
                            aiThoughts = emptyList()
                            aiProgress = ""
                            aiComplete = false
                            aiError = null
                        },
                        modifier = Modifier.align(Alignment.BottomCenter)
                    )
                }
            }
        }
    }
}

@Composable
private fun AutoResponderTab(
    rules: List<AutoResponder.AutoResponderRule>,
    onRuleToggle: (String, Boolean) -> Unit,
    onTest: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        // Description
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.primaryContainer
            )
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    "🤖 AutoResponder",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "AI automatycznie odpowiada na emaile. Każda reguła może wysyłać odpowiedź automatycznie lub czekać na zatwierdzenie.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onPrimaryContainer
                )
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Rules list
        Text(
            "Reguły (${rules.size})",
            style = MaterialTheme.typography.titleSmall
        )
        Spacer(modifier = Modifier.height(8.dp))
        
        LazyColumn(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(rules) { rule ->
                RuleCard(
                    rule = rule,
                    onToggle = { enabled -> onRuleToggle(rule.id, enabled) }
                )
            }
        }
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Test button
        Button(
            onClick = onTest,
            modifier = Modifier.fillMaxWidth()
        ) {
            Icon(Icons.Default.PlayArrow, contentDescription = null)
            Spacer(modifier = Modifier.width(8.dp))
            Text("🧪 Test AutoResponder")
        }
    }
}

@Composable
private fun RuleCard(
    rule: AutoResponder.AutoResponderRule,
    onToggle: (Boolean) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth()
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
                    rule.name,
                    style = MaterialTheme.typography.titleSmall
                )
                Spacer(modifier = Modifier.height(4.dp))
                
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (rule.autoSend) {
                        Chip(
                            label = { Text("Auto send", style = MaterialTheme.typography.labelSmall) },
                            color = MaterialTheme.colorScheme.primary
                        )
                    } else {
                        Chip(
                            label = { Text("Requires approval", style = MaterialTheme.typography.labelSmall) },
                            color = MaterialTheme.colorScheme.secondary
                        )
                    }
                    
                    Text(
                        "Priority: ${rule.priority}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            
            Switch(
                checked = rule.enabled,
                onCheckedChange = onToggle
            )
        }
    }
}

@Composable
private fun Chip(
    label: @Composable () -> Unit,
    color: androidx.compose.ui.graphics.Color
) {
    Surface(
        shape = MaterialTheme.shapes.small,
        color = color.copy(alpha = 0.2f)
    ) {
        Box(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        ) {
            ProvideTextStyle(value = MaterialTheme.typography.labelSmall.copy(color = color)) {
                label()
            }
        }
    }
}

@Composable
private fun SocialAutomationTab() {
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.MoreVert,
            contentDescription = null,
            modifier = Modifier.size(48.dp),
            tint = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            "📱 Social Automation",
            style = MaterialTheme.typography.titleMedium
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            "Coming Soon - Automatyczne posty na FB, Instagram, Twitter",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun TherapyReminderTab() {
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.MoreVert,
            contentDescription = null,
            modifier = Modifier.size(48.dp),
            tint = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            "💊 Therapy Reminders",
            style = MaterialTheme.typography.titleMedium
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            "Coming Soon - Przypomnienia o lekach, terapii, sesji",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun SecurityMonitorTab() {
    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.MoreVert,
            contentDescription = null,
            modifier = Modifier.size(48.dp),
            tint = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            "🔒 Security Monitor",
            style = MaterialTheme.typography.titleMedium
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            "Coming Soon - Monitorowanie zagrożeń, blokowanie app",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
