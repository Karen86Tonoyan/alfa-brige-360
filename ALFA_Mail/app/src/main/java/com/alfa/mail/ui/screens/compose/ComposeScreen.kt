package com.alfa.mail.ui.screens.compose

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.AutoFixHigh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.alfa.mail.ai.AlfaManus
import com.alfa.mail.ai.AiAssistService
import com.alfa.mail.email.EmailService
import com.alfa.mail.ui.components.ThinkingCard
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ComposeScreen(
    onBack: () -> Unit,
    onSent: () -> Unit
) {
    val context = LocalContext.current
    val manus = remember { AlfaManus.getInstance(context) }
    val emailService = remember { EmailService.getInstance(context) }
    val aiAssist = remember { AiAssistService.getInstance(context) }
    val scope = rememberCoroutineScope()
    
    var to by remember { mutableStateOf("") }
    var cc by remember { mutableStateOf("") }
    var subject by remember { mutableStateOf("") }
    var body by remember { mutableStateOf("") }
    var isSending by remember { mutableStateOf(false) }
    var isAiLoading by remember { mutableStateOf(false) }
    var isOffline by remember { mutableStateOf(manus.isOffline()) }
    var showVaultDialog by remember { mutableStateOf(false) }
    var showAiMenu by remember { mutableStateOf(false) }
    var aiSuggestion by remember { mutableStateOf<String?>(null) }
    var sendError by remember { mutableStateOf<String?>(null) }
    
    // 🧠 Streaming AI state (jak DeepSeek)
    var showThinking by remember { mutableStateOf(false) }
    var aiThoughts by remember { mutableStateOf<List<AiAssistService.ThinkingStep>>(emptyList()) }
    var aiProgress by remember { mutableStateOf("") }
    var aiFinalText by remember { mutableStateOf<String?>(null) }
    var aiComplete by remember { mutableStateOf(false) }
    var aiError by remember { mutableStateOf<String?>(null) }

    // Sprawdzaj status sieci
    LaunchedEffect(Unit) {
        manus.activate()
        isOffline = manus.isOffline()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { 
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Compose")
                        if (isOffline) {
                            Spacer(modifier = Modifier.width(8.dp))
                            Icon(
                                Icons.Default.Lock,
                                contentDescription = "Offline - Vault Open",
                                tint = MaterialTheme.colorScheme.primary
                            )
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    // AI Assist button z menu
                    Box {
                        IconButton(onClick = { showAiMenu = true }) {
                            if (isAiLoading) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(24.dp),
                                    strokeWidth = 2.dp
                                )
                            } else {
                                Icon(Icons.Default.Psychology, contentDescription = "AI Assist")
                            }
                        }
                        
                        DropdownMenu(
                            expanded = showAiMenu,
                            onDismissRequest = { showAiMenu = false }
                        ) {
                            DropdownMenuItem(
                                text = { Text("✨ Napisz email") },
                                onClick = {
                                    showAiMenu = false
                                    scope.launch {
                                        // Reset AI state
                                        aiThoughts = emptyList()
                                        aiProgress = ""
                                        aiFinalText = null
                                        aiComplete = false
                                        aiError = null
                                        showThinking = true
                                        isAiLoading = true
                                        
                                        // Streaming z widocznymi myślami
                                        aiAssist.suggestEmailStreaming(
                                            context = AiAssistService.EmailContext(
                                                to = to,
                                                subject = subject,
                                                purpose = "general"
                                            ),
                                            style = "professional",
                                            onThought = { thought ->
                                                aiThoughts = aiThoughts + thought
                                            },
                                            onProgress = { progress ->
                                                aiProgress = progress
                                            },
                                            onComplete = { result ->
                                                aiFinalText = result
                                                aiComplete = true
                                                isAiLoading = false
                                            },
                                            onError = { error ->
                                                aiError = error
                                                aiComplete = true
                                                isAiLoading = false
                                            }
                                        )
                                    }
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("📝 Popraw email") },
                                onClick = {
                                    showAiMenu = false
                                    if (body.isNotBlank()) {
                                        scope.launch {
                                            // Reset AI state
                                            aiThoughts = emptyList()
                                            aiProgress = ""
                                            aiFinalText = null
                                            aiComplete = false
                                            aiError = null
                                            showThinking = true
                                            isAiLoading = true
                                            
                                            // Streaming improvement
                                            aiAssist.improveEmailStreaming(
                                                currentBody = body,
                                                onThought = { thought ->
                                                    aiThoughts = aiThoughts + thought
                                                },
                                                onProgress = { progress ->
                                                    aiProgress = progress
                                                },
                                                onComplete = { result ->
                                                    aiFinalText = result
                                                    aiComplete = true
                                                    isAiLoading = false
                                                },
                                                onError = { error ->
                                                    aiError = error
                                                    aiComplete = true
                                                    isAiLoading = false
                                                }
                                            )
                                        }
                                    }
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("💡 Zaproponuj temat") },
                                onClick = {
                                    showAiMenu = false
                                    if (body.isNotBlank()) {
                                        scope.launch {
                                            isAiLoading = true
                                            val result = aiAssist.suggestSubject(body)
                                            when (result) {
                                                is AiAssistService.AiResult.Success -> {
                                                    subject = result.text
                                                }
                                                is AiAssistService.AiResult.Error -> {
                                                    sendError = result.message
                                                }
                                            }
                                            isAiLoading = false
                                        }
                                    }
                                }
                            )
                            HorizontalDivider()
                            DropdownMenuItem(
                                text = { Text("📋 Formalny szablon") },
                                onClick = {
                                    showAiMenu = false
                                    scope.launch {
                                        val result = aiAssist.suggestEmail(
                                            AiAssistService.EmailContext(to, subject, "formal"),
                                            style = "formal"
                                        )
                                        if (result is AiAssistService.AiResult.Success) {
                                            aiSuggestion = result.text
                                        }
                                    }
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("💼 Biznesowy szablon") },
                                onClick = {
                                    showAiMenu = false
                                    scope.launch {
                                        val result = aiAssist.suggestEmail(
                                            AiAssistService.EmailContext(to, subject, "business"),
                                            style = "business"
                                        )
                                        if (result is AiAssistService.AiResult.Success) {
                                            aiSuggestion = result.text
                                        }
                                    }
                                }
                            )
                        }
                    }
                    
                    // Vault button (tylko offline)
                    if (isOffline) {
                        IconButton(onClick = { showVaultDialog = true }) {
                            Icon(Icons.Default.Lock, contentDescription = "Open Vault")
                        }
                    }
                    
                    IconButton(onClick = { /* Attach file */ }) {
                        Icon(Icons.Default.AttachFile, contentDescription = "Attach")
                    }
                    IconButton(
                        onClick = {
                            isSending = true
                            sendError = null
                            scope.launch {
                                // Zapisz do sejfu jeśli offline
                                if (isOffline) {
                                    manus.storeSecret(
                                        """{"to":"$to","cc":"$cc","subject":"$subject","body":"$body"}""",
                                        "email"
                                    )
                                }
                                
                                // Wyślij przez SMTP
                                val result = emailService.sendSimple(
                                    to = to,
                                    subject = subject,
                                    body = body,
                                    cc = cc.ifBlank { null }
                                )
                                
                                when (result) {
                                    is EmailService.SendResult.Success -> {
                                        onSent()
                                    }
                                    is EmailService.SendResult.Queued -> {
                                        // Offline - zapisano do kolejki
                                        onSent()
                                    }
                                    is EmailService.SendResult.Error -> {
                                        sendError = result.message
                                        isSending = false
                                    }
                                }
                            }
                        },
                        enabled = to.isNotBlank() && subject.isNotBlank() && !isSending
                    ) {
                        Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 16.dp)
        ) {
            OutlinedTextField(
                value = to,
                onValueChange = { to = it },
                label = { Text("To") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            Spacer(modifier = Modifier.height(8.dp))
            
            OutlinedTextField(
                value = cc,
                onValueChange = { cc = it },
                label = { Text("Cc") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            Spacer(modifier = Modifier.height(8.dp))
            
            OutlinedTextField(
                value = subject,
                onValueChange = { subject = it },
                label = { Text("Subject") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            Spacer(modifier = Modifier.height(8.dp))
            
            OutlinedTextField(
                value = body,
                onValueChange = { body = it },
                label = { Text("Message") },
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                maxLines = Int.MAX_VALUE
            )
        }

        if (isSending) {
            CircularProgressIndicator(
                modifier = Modifier.align(Alignment.Center)
            )
        }
        
        // 🧠 ThinkingCard - Widoczne myśli AI (jak DeepSeek)
        if (showThinking) {
            ThinkingCard(
                thoughts = aiThoughts,
                currentProgress = aiProgress,
                finalText = aiFinalText,
                isComplete = aiComplete,
                error = aiError,
                onDismiss = {
                    showThinking = false
                    aiThoughts = emptyList()
                    aiProgress = ""
                    aiFinalText = null
                    aiComplete = false
                    aiError = null
                },
                onApply = { text ->
                    body = text
                    showThinking = false
                    aiThoughts = emptyList()
                    aiProgress = ""
                    aiFinalText = null
                    aiComplete = false
                    aiError = null
                },
                modifier = Modifier.align(Alignment.BottomCenter)
            )
        }
        
        // AI Suggestion card (old style - fallback)
        aiSuggestion?.let { suggestion ->
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .align(Alignment.BottomCenter)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("🤖 AI Suggestion", style = MaterialTheme.typography.titleSmall)
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(suggestion)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.End
                    ) {
                        TextButton(onClick = { aiSuggestion = null }) {
                            Text("Dismiss")
                        }
                        TextButton(onClick = { 
                            body = suggestion
                            aiSuggestion = null
                        }) {
                            Text("Apply")
                        }
                    }
                }
            }
        }
    }
    
    // Vault Dialog (tylko offline)
    if (showVaultDialog) {
        AlertDialog(
            onDismissRequest = { showVaultDialog = false },
            title = { Text("🔐 Offline Vault") },
            text = { 
                Column {
                    Text("Sejf jest otwarty. Prawdziwe dane są dostępne.")
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Status: OFFLINE - BEZPIECZNY", 
                         style = MaterialTheme.typography.bodySmall,
                         color = MaterialTheme.colorScheme.primary)
                }
            },
            confirmButton = {
                TextButton(onClick = { showVaultDialog = false }) {
                    Text("OK")
                }
            }
        )
    }
    
    // Error Snackbar
    sendError?.let { error ->
        AlertDialog(
            onDismissRequest = { sendError = null },
            title = { Text("❌ Błąd") },
            text = { Text(error) },
            confirmButton = {
                TextButton(onClick = { sendError = null }) {
                    Text("OK")
                }
            }
        )
    }
}
