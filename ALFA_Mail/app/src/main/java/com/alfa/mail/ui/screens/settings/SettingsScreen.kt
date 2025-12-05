package com.alfa.mail.ui.screens.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.alfa.mail.ai.AiAssistService
import com.alfa.mail.email.EmailService
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val emailService = remember { EmailService.getInstance(context) }
    val aiAssist = remember { AiAssistService.getInstance(context) }
    val scope = rememberCoroutineScope()
    
    var showAddAccountDialog by remember { mutableStateOf(false) }
    var showSmtpDialog by remember { mutableStateOf(false) }
    var showAiDialog by remember { mutableStateOf(false) }
    
    // Test status
    var testResult by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            item {
                SettingsSection(title = "Accounts") {
                    SettingsItem(
                        icon = Icons.Default.Add,
                        title = "Add Account",
                        subtitle = "Connect an email account",
                        onClick = { showAddAccountDialog = true }
                    )
                }
            }

            item {
                SettingsSection(title = "Sync") {
                    SettingsItem(
                        icon = Icons.Default.Sync,
                        title = "Sync Frequency",
                        subtitle = "Every 15 minutes",
                        onClick = { /* TODO */ }
                    )
                }
            }
            
            item {
                SettingsSection(title = "📧 SMTP") {
                    SettingsItem(
                        icon = Icons.Default.Send,
                        title = "Konfiguracja SMTP",
                        subtitle = "Wysyłanie emaili",
                        onClick = { showSmtpDialog = true }
                    )
                }
            }
            
            item {
                SettingsSection(title = "🤖 AI Assist") {
                    SettingsItem(
                        icon = Icons.Default.Psychology,
                        title = "Konfiguracja AI",
                        subtitle = "Gemini / Ollama / Szablony",
                        onClick = { showAiDialog = true }
                    )
                }
            }
            
            testResult?.let { result ->
                item {
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = if (result.startsWith("✅")) 
                                MaterialTheme.colorScheme.primaryContainer
                            else MaterialTheme.colorScheme.errorContainer
                        )
                    ) {
                        Text(
                            result,
                            modifier = Modifier.padding(16.dp),
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }
        }
    }

    if (showAddAccountDialog) {
        AddAccountDialog(
            onDismiss = { showAddAccountDialog = false },
            onAccountAdded = { showAddAccountDialog = false }
        )
    }
    
    if (showSmtpDialog) {
        SmtpConfigDialog(
            emailService = emailService,
            onDismiss = { showSmtpDialog = false },
            onTestResult = { testResult = it }
        )
    }
    
    if (showAiDialog) {
        AiConfigDialog(
            aiAssist = aiAssist,
            onDismiss = { showAiDialog = false }
        )
    }
}

@Composable
fun SettingsSection(
    title: String,
    content: @Composable () -> Unit
) {
    Column {
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(16.dp)
        )
        content()
        HorizontalDivider()
    }
}

@Composable
fun SettingsItem(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(16.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.width(16.dp))
        Column {
            Text(text = title, style = MaterialTheme.typography.bodyLarge)
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
fun AddAccountDialog(
    onDismiss: () -> Unit,
    onAccountAdded: () -> Unit
) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var imapServer by remember { mutableStateOf("") }
    var smtpServer by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add Email Account") },
        text = {
            Column {
                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it },
                    label = { Text("Email") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Password") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = imapServer,
                    onValueChange = { imapServer = it },
                    label = { Text("IMAP Server") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = smtpServer,
                    onValueChange = { smtpServer = it },
                    label = { Text("SMTP Server") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    // TODO: Save account securely
                    onAccountAdded()
                },
                enabled = email.isNotBlank() && password.isNotBlank()
            ) {
                Text("Add")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}

@Composable
fun SmtpConfigDialog(
    emailService: EmailService,
    onDismiss: () -> Unit,
    onTestResult: (String) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    
    var smtpHost by remember { mutableStateOf("smtp.gmail.com") }
    var smtpPort by remember { mutableStateOf("587") }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var senderName by remember { mutableStateOf("ALFA Mail") }
    var showPassword by remember { mutableStateOf(false) }
    var isTesting by remember { mutableStateOf(false) }
    
    // Load saved
    LaunchedEffect(Unit) {
        val prefs = context.getSharedPreferences("alfa_mail_config", android.content.Context.MODE_PRIVATE)
        smtpHost = prefs.getString("smtp_host", "smtp.gmail.com") ?: "smtp.gmail.com"
        smtpPort = prefs.getInt("smtp_port", 587).toString()
        username = prefs.getString("smtp_username", "") ?: ""
        password = prefs.getString("smtp_password", "") ?: ""
        senderName = prefs.getString("sender_name", "ALFA Mail") ?: "ALFA Mail"
    }
    
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("📧 Konfiguracja SMTP") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = smtpHost,
                        onValueChange = { smtpHost = it },
                        label = { Text("Host") },
                        modifier = Modifier.weight(2f),
                        singleLine = true
                    )
                    OutlinedTextField(
                        value = smtpPort,
                        onValueChange = { smtpPort = it },
                        label = { Text("Port") },
                        modifier = Modifier.weight(1f),
                        singleLine = true
                    )
                }
                OutlinedTextField(
                    value = username,
                    onValueChange = { username = it },
                    label = { Text("Email") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("App Password") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    visualTransformation = if (showPassword) VisualTransformation.None 
                                           else PasswordVisualTransformation(),
                    trailingIcon = {
                        IconButton(onClick = { showPassword = !showPassword }) {
                            Icon(
                                if (showPassword) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                null
                            )
                        }
                    }
                )
                OutlinedTextField(
                    value = senderName,
                    onValueChange = { senderName = it },
                    label = { Text("Nazwa nadawcy") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                
                OutlinedButton(
                    onClick = {
                        scope.launch {
                            isTesting = true
                            emailService.configure(EmailService.EmailConfig(
                                smtpHost = smtpHost,
                                smtpPort = smtpPort.toIntOrNull() ?: 587,
                                username = username,
                                password = password,
                                senderEmail = username,
                                senderName = senderName
                            ))
                            val result = emailService.testConnection()
                            onTestResult(when (result) {
                                is EmailService.SendResult.Success -> "✅ Połączenie SMTP OK!"
                                is EmailService.SendResult.Error -> "❌ ${result.message}"
                                else -> "⚠️ Unknown"
                            })
                            isTesting = false
                        }
                    },
                    enabled = !isTesting && username.isNotBlank() && password.isNotBlank(),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    if (isTesting) {
                        CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    } else {
                        Text("🔌 Test połączenia")
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    scope.launch {
                        emailService.saveConfig(EmailService.EmailConfig(
                            smtpHost = smtpHost,
                            smtpPort = smtpPort.toIntOrNull() ?: 587,
                            username = username,
                            password = password,
                            senderEmail = username,
                            senderName = senderName
                        ))
                        onDismiss()
                    }
                }
            ) { Text("💾 Zapisz") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Anuluj") }
        }
    )
}

@Composable
fun AiConfigDialog(
    aiAssist: AiAssistService,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    
    var provider by remember { mutableStateOf(AiAssistService.AiProvider.GEMINI) }
    var geminiKey by remember { mutableStateOf("") }
    var ollamaUrl by remember { mutableStateOf("http://localhost:11434") }
    var ollamaModel by remember { mutableStateOf("llama3") }
    var showKey by remember { mutableStateOf(false) }
    
    // Load saved
    LaunchedEffect(Unit) {
        val prefs = context.getSharedPreferences("alfa_ai_config", android.content.Context.MODE_PRIVATE)
        provider = try {
            AiAssistService.AiProvider.valueOf(prefs.getString("provider", "GEMINI") ?: "GEMINI")
        } catch (e: Exception) { AiAssistService.AiProvider.GEMINI }
        geminiKey = prefs.getString("gemini_key", "") ?: ""
        ollamaUrl = prefs.getString("ollama_url", "http://localhost:11434") ?: "http://localhost:11434"
        ollamaModel = prefs.getString("ollama_model", "llama3") ?: "llama3"
    }
    
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("🤖 Konfiguracja AI") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Provider:", style = MaterialTheme.typography.labelMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = provider == AiAssistService.AiProvider.GEMINI,
                        onClick = { provider = AiAssistService.AiProvider.GEMINI },
                        label = { Text("Gemini") }
                    )
                    FilterChip(
                        selected = provider == AiAssistService.AiProvider.OLLAMA,
                        onClick = { provider = AiAssistService.AiProvider.OLLAMA },
                        label = { Text("Ollama") }
                    )
                    FilterChip(
                        selected = provider == AiAssistService.AiProvider.TEMPLATE,
                        onClick = { provider = AiAssistService.AiProvider.TEMPLATE },
                        label = { Text("Szablony") }
                    )
                }
                
                if (provider == AiAssistService.AiProvider.GEMINI) {
                    OutlinedTextField(
                        value = geminiKey,
                        onValueChange = { geminiKey = it },
                        label = { Text("Gemini API Key") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        visualTransformation = if (showKey) VisualTransformation.None 
                                               else PasswordVisualTransformation(),
                        trailingIcon = {
                            IconButton(onClick = { showKey = !showKey }) {
                                Icon(
                                    if (showKey) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                    null
                                )
                            }
                        }
                    )
                }
                
                if (provider == AiAssistService.AiProvider.OLLAMA) {
                    OutlinedTextField(
                        value = ollamaUrl,
                        onValueChange = { ollamaUrl = it },
                        label = { Text("Ollama URL") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                    OutlinedTextField(
                        value = ollamaModel,
                        onValueChange = { ollamaModel = it },
                        label = { Text("Model") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    scope.launch {
                        val prefs = context.getSharedPreferences("alfa_ai_config", android.content.Context.MODE_PRIVATE)
                        prefs.edit().apply {
                            putString("provider", provider.name)
                            putString("gemini_key", geminiKey)
                            putString("ollama_url", ollamaUrl)
                            putString("ollama_model", ollamaModel)
                            apply()
                        }
                        aiAssist.configure(AiAssistService.AiConfig(
                            provider = provider,
                            geminiApiKey = geminiKey.ifBlank { null },
                            ollamaUrl = ollamaUrl,
                            ollamaModel = ollamaModel
                        ))
                        onDismiss()
                    }
                }
            ) { Text("💾 Zapisz") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Anuluj") }
        }
    )
}
