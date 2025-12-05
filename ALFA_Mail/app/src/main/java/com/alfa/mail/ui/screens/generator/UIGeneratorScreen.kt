package com.alfa.mail.ui.screens.generator

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.alfa.mail.ai.AiAssistService
import com.alfa.mail.ai.AlfaUIGenerator
import com.alfa.mail.ui.components.ThinkingCard
import kotlinx.coroutines.launch

/**
 * 🎨 UI GENERATOR SCREEN
 * 
 * Ekran gdzie Król może generować CAŁE EKRANY i KOMPONENTY!
 * 
 * Wpisz co chcesz → AI generuje kod Compose → Preview na żywo
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UIGeneratorScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val generator = remember { AlfaUIGenerator.getInstance(context) }
    val scope = rememberCoroutineScope()
    
    var prompt by remember { mutableStateOf("") }
    var isGenerating by remember { mutableStateOf(false) }
    
    // AI thinking state
    var showThinking by remember { mutableStateOf(false) }
    var aiThoughts by remember { mutableStateOf<List<AiAssistService.ThinkingStep>>(emptyList()) }
    var aiProgress by remember { mutableStateOf("") }
    var generatedUI by remember { mutableStateOf<AlfaUIGenerator.GeneratedUI?>(null) }
    var aiComplete by remember { mutableStateOf(false) }
    var aiError by remember { mutableStateOf<String?>(null) }
    
    var showCodeView by remember { mutableStateOf(false) }
    var savedFileName by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("🎨 UI Generator") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    if (generatedUI != null) {
                        IconButton(onClick = { showCodeView = !showCodeView }) {
                            Icon(
                                if (showCodeView) Icons.Default.Visibility else Icons.Default.Code,
                                contentDescription = "Toggle Code View"
                            )
                        }
                        
                        IconButton(
                            onClick = {
                                scope.launch {
                                    val fileName = "Generated_${System.currentTimeMillis()}"
                                    if (generator.exportToFile(generatedUI!!, fileName)) {
                                        savedFileName = fileName
                                    }
                                }
                            }
                        ) {
                            Icon(Icons.Default.Save, contentDescription = "Save")
                        }
                    }
                }
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp)
            ) {
                // Prompt input
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            "Opisz co chcesz stworzyć:",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onPrimaryContainer
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        
                        OutlinedTextField(
                            value = prompt,
                            onValueChange = { prompt = it },
                            modifier = Modifier.fillMaxWidth(),
                            placeholder = { Text("np. Ekran logowania z logo i formularzem") },
                            minLines = 3,
                            maxLines = 5
                        )
                        
                        Spacer(modifier = Modifier.height(16.dp))
                        
                        Button(
                            onClick = {
                                if (prompt.isNotBlank()) {
                                    scope.launch {
                                        // Reset state
                                        aiThoughts = emptyList()
                                        aiProgress = ""
                                        generatedUI = null
                                        aiComplete = false
                                        aiError = null
                                        showThinking = true
                                        isGenerating = true
                                        
                                        // Generate!
                                        generator.generateUI(
                                            userPrompt = prompt,
                                            onThought = { thought ->
                                                aiThoughts = aiThoughts + thought
                                            },
                                            onProgress = { progress ->
                                                aiProgress = progress
                                            },
                                            onComplete = { ui ->
                                                generatedUI = ui
                                                aiComplete = true
                                                isGenerating = false
                                            },
                                            onError = { error ->
                                                aiError = error
                                                aiComplete = true
                                                isGenerating = false
                                            }
                                        )
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            enabled = prompt.isNotBlank() && !isGenerating
                        ) {
                            if (isGenerating) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    strokeWidth = 2.dp,
                                    color = MaterialTheme.colorScheme.onPrimary
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                            }
                            Text(if (isGenerating) "Generuję..." else "✨ Wygeneruj UI")
                        }
                    }
                }
                
                Spacer(modifier = Modifier.height(16.dp))
                
                // Quick templates
                if (!isGenerating && generatedUI == null) {
                    Text(
                        "Szybkie wzorce:",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        AssistChip(
                            onClick = { prompt = "Ekran logowania z logo, email, hasło i przyciskiem" },
                            label = { Text("Login") }
                        )
                        AssistChip(
                            onClick = { prompt = "Lista produktów z obrazkiem, nazwą i ceną" },
                            label = { Text("Lista") }
                        )
                        AssistChip(
                            onClick = { prompt = "Formularz kontaktowy z polami imię, email, wiadomość" },
                            label = { Text("Form") }
                        )
                    }
                }
                
                Spacer(modifier = Modifier.height(16.dp))
                
                // Generated UI Preview or Code
                generatedUI?.let { ui ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f),
                        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(16.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        ui.componentName,
                                        style = MaterialTheme.typography.titleLarge
                                    )
                                    Text(
                                        "${ui.code.lines().size} lines of code",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                
                                if (savedFileName != null) {
                                    Chip(
                                        onClick = { },
                                        label = { Text("✅ Saved") },
                                        colors = ChipDefaults.chipColors(
                                            containerColor = MaterialTheme.colorScheme.primaryContainer
                                        )
                                    )
                                }
                            }
                            
                            Spacer(modifier = Modifier.height(16.dp))
                            HorizontalDivider()
                            Spacer(modifier = Modifier.height(16.dp))
                            
                            // Code view
                            if (showCodeView) {
                                Card(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .verticalScroll(rememberScrollState()),
                                    colors = CardDefaults.cardColors(
                                        containerColor = MaterialTheme.colorScheme.surfaceVariant
                                    )
                                ) {
                                    Text(
                                        text = ui.code,
                                        modifier = Modifier.padding(12.dp),
                                        style = MaterialTheme.typography.bodySmall,
                                        fontFamily = FontFamily.Monospace,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            } else {
                                // Preview placeholder
                                Box(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .clip(RoundedCornerShape(12.dp))
                                        .background(MaterialTheme.colorScheme.surface),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Column(
                                        horizontalAlignment = Alignment.CenterHorizontally
                                    ) {
                                        Icon(
                                            Icons.Default.Visibility,
                                            contentDescription = null,
                                            modifier = Modifier.size(48.dp),
                                            tint = MaterialTheme.colorScheme.primary
                                        )
                                        Spacer(modifier = Modifier.height(16.dp))
                                        Text(
                                            "Preview Coming Soon",
                                            style = MaterialTheme.typography.titleMedium
                                        )
                                        Spacer(modifier = Modifier.height(8.dp))
                                        Text(
                                            "Kliknij 👁️ aby zobaczyć kod",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
            // Thinking card overlay
            if (showThinking) {
                ThinkingCard(
                    thoughts = aiThoughts,
                    currentProgress = aiProgress,
                    finalText = generatedUI?.code,
                    isComplete = aiComplete,
                    error = aiError,
                    onDismiss = {
                        showThinking = false
                        aiThoughts = emptyList()
                        aiProgress = ""
                        aiComplete = false
                        aiError = null
                    },
                    onApply = null, // Nie używamy Apply - kod już w preview
                    modifier = Modifier.align(Alignment.BottomCenter)
                )
            }
        }
    }
}

@Composable
private fun Chip(
    onClick: () -> Unit,
    label: @Composable () -> Unit,
    colors: ChipColors = ChipDefaults.chipColors()
) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(16.dp),
        color = colors.containerColor
    ) {
        Box(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            contentAlignment = Alignment.Center
        ) {
            ProvideTextStyle(value = MaterialTheme.typography.labelMedium) {
                label()
            }
        }
    }
}
