package com.alfa.mail.ui.screens.inbox

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.alfa.mail.security.FakeDataProvider
import com.alfa.mail.ui.navigation.LocalDuressMode
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InboxScreen(
    onComposeClick: () -> Unit,
    onSettingsClick: () -> Unit,
    onEmailClick: (Long) -> Unit,
    onUIGeneratorClick: (() -> Unit)? = null,
    onAutopilotClick: (() -> Unit)? = null,
    onBehaviorInsightsClick: (() -> Unit)? = null
) {
    // Sprawdź czy tryb duress
    val isDuressMode = LocalDuressMode.current
    
    // W trybie duress - pokaż fałszywe emaile
    val emails = remember(isDuressMode) {
        if (isDuressMode) {
            FakeDataProvider.generateFakeEmails(15)
        } else {
            emptyList() // Prawdziwe emaile z bazy
        }
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { 
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("ALFA Mail")
                        // Ukryty wskaźnik duress (tylko dla Ciebie)
                        if (isDuressMode) {
                            Spacer(modifier = Modifier.width(8.dp))
                            // Subtelna kropka - wiesz że jesteś w trybie duress
                            Text("•", color = MaterialTheme.colorScheme.error.copy(alpha = 0.3f))
                        }
                    }
                },
                actions = {
                    // 🧠 Behavior Insights button
                    onBehaviorInsightsClick?.let { onClick ->
                        IconButton(onClick = onClick) {
                            Icon(
                                Icons.Default.Psychology,
                                contentDescription = "Behavior Insights",
                                tint = Color(0xFFFF6B9D)
                            )
                        }
                    }
                    
                    // 🤖 Autopilot Dashboard button
                    onAutopilotClick?.let { onClick ->
                        IconButton(onClick = onClick) {
                            Icon(
                                Icons.Default.MoreVert,
                                contentDescription = "Autopilot",
                                tint = MaterialTheme.colorScheme.primary
                            )
                        }
                    }
                    
                    // 🎨 UI Generator button
                    onUIGeneratorClick?.let { onClick ->
                        IconButton(onClick = onClick) {
                            Icon(
                                Icons.Default.AutoAwesome, 
                                contentDescription = "UI Generator",
                                tint = MaterialTheme.colorScheme.primary
                            )
                        }
                    }
                    
                    IconButton(onClick = onSettingsClick) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                }
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onComposeClick) {
                Icon(Icons.Default.Add, contentDescription = "Compose")
            }
        }
    ) { paddingValues ->
        if (emails.isEmpty() && !isDuressMode) {
            // Brak prawdziwych emaili
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "No emails yet.\nAdd an account in Settings.",
                    style = MaterialTheme.typography.bodyLarge
                )
            }
        } else {
            // Lista emaili (fałszywych w duress, prawdziwych normalnie)
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues)
            ) {
                items(emails) { email ->
                    EmailItem(
                        sender = email.from,
                        subject = email.subject,
                        preview = email.preview,
                        time = formatTime(email.timestamp),
                        isRead = email.isRead,
                        onClick = { onEmailClick(email.id) }
                    )
                }
            }
        }
    }
}

private fun formatTime(timestamp: Long): String {
    val now = System.currentTimeMillis()
    val diff = now - timestamp
    
    return when {
        diff < 3600000 -> "${diff / 60000} min" // < 1h
        diff < 86400000 -> "${diff / 3600000} godz." // < 24h
        else -> SimpleDateFormat("dd.MM", Locale.getDefault()).format(Date(timestamp))
    }
}

@Composable
fun EmailItem(
    sender: String,
    subject: String,
    preview: String,
    time: String,
    isRead: Boolean,
    onClick: () -> Unit
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        color = if (isRead) MaterialTheme.colorScheme.surface 
                else MaterialTheme.colorScheme.surfaceVariant
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = sender,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = if (isRead) FontWeight.Normal else FontWeight.Bold,
                    modifier = Modifier.weight(1f)
                )
                Text(
                    text = time,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = subject,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = if (isRead) FontWeight.Normal else FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = preview,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
    HorizontalDivider()
}
