package com.alfa.mail.ui.screens.lock

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.alfa.mail.security.DuressPin
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * 🔐 PIN LOCK SCREEN
 * 
 * Ekran blokady z obsługą Duress PIN:
 * - Normalny PIN = odblokuj prawdziwe dane
 * - Odwrotny PIN = tryb bezpieczeństwa (fałszywe dane)
 */
@Composable
fun PinLockScreen(
    onUnlocked: (isDuress: Boolean) -> Unit,
    onSetupRequired: () -> Unit
) {
    val context = LocalContext.current
    val duressPin = remember { DuressPin.getInstance(context) }
    val scope = rememberCoroutineScope()
    
    var pin by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("Wprowadź PIN") }
    var messageColor by remember { mutableStateOf(Color.Unspecified) }
    var isError by remember { mutableStateOf(false) }
    var isLocked by remember { mutableStateOf(false) }
    var attemptsLeft by remember { mutableStateOf(5) }
    
    // Sprawdź czy PIN jest ustawiony
    LaunchedEffect(Unit) {
        if (!duressPin.isPinSet()) {
            onSetupRequired()
        }
    }
    
    // Automatyczna weryfikacja po wpisaniu 4+ cyfr
    LaunchedEffect(pin) {
        if (pin.length >= 4) {
            delay(100) // Krótka pauza
            
            val result = duressPin.verifyPin(pin)
            
            when (result.result) {
                DuressPin.PinResult.CORRECT -> {
                    message = "✓ Odblokowano"
                    messageColor = Color(0xFF4CAF50)
                    delay(300)
                    onUnlocked(false)
                }
                DuressPin.PinResult.DURESS -> {
                    // Wygląda jak sukces, ale to tryb duress!
                    message = "✓ Odblokowano"
                    messageColor = Color(0xFF4CAF50)
                    delay(300)
                    onUnlocked(true) // isDuress = true
                }
                DuressPin.PinResult.INCORRECT -> {
                    message = result.message
                    messageColor = Color(0xFFF44336)
                    isError = true
                    attemptsLeft = result.attemptsLeft
                    pin = ""
                    delay(1000)
                    isError = false
                    message = "Wprowadź PIN"
                    messageColor = Color.Unspecified
                }
                DuressPin.PinResult.LOCKED -> {
                    message = result.message
                    messageColor = Color(0xFFF44336)
                    isLocked = true
                    pin = ""
                }
                DuressPin.PinResult.NOT_SET -> {
                    onSetupRequired()
                }
            }
        }
    }
    
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(32.dp)
        ) {
            // Logo / Ikona
            Icon(
                Icons.Default.Lock,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Tytuł
            Text(
                "ALFA Mail",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            // Wiadomość
            AnimatedContent(
                targetState = message,
                transitionSpec = {
                    fadeIn() togetherWith fadeOut()
                }
            ) { msg ->
                Text(
                    msg,
                    style = MaterialTheme.typography.bodyLarge,
                    color = if (messageColor != Color.Unspecified) messageColor 
                           else MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center
                )
            }
            
            Spacer(modifier = Modifier.height(32.dp))
            
            // PIN dots
            Row(
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                repeat(6) { index ->
                    PinDot(
                        filled = index < pin.length,
                        isError = isError
                    )
                }
            }
            
            Spacer(modifier = Modifier.height(48.dp))
            
            // Klawiatura numeryczna
            if (!isLocked) {
                NumericKeypad(
                    onDigit = { digit ->
                        if (pin.length < 6) {
                            pin += digit
                        }
                    },
                    onBackspace = {
                        if (pin.isNotEmpty()) {
                            pin = pin.dropLast(1)
                        }
                    },
                    onClear = {
                        pin = ""
                    }
                )
            } else {
                // Zablokowane - pokaż timer
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Icon(
                        Icons.Default.Timer,
                        contentDescription = null,
                        modifier = Modifier.size(48.dp),
                        tint = MaterialTheme.colorScheme.error
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        "Za dużo błędnych prób",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.error
                    )
                    
                    // Retry button
                    Spacer(modifier = Modifier.height(24.dp))
                    OutlinedButton(
                        onClick = {
                            isLocked = false
                            message = "Wprowadź PIN"
                            messageColor = Color.Unspecified
                        }
                    ) {
                        Text("Spróbuj ponownie")
                    }
                }
            }
            
            // Próby
            if (!isLocked && attemptsLeft < 5) {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    "Pozostało prób: $attemptsLeft",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }
        }
    }
}

@Composable
fun PinDot(
    filled: Boolean,
    isError: Boolean
) {
    val color = when {
        isError -> MaterialTheme.colorScheme.error
        filled -> MaterialTheme.colorScheme.primary
        else -> MaterialTheme.colorScheme.outlineVariant
    }
    
    Box(
        modifier = Modifier
            .size(16.dp)
            .clip(CircleShape)
            .background(color)
    )
}

@Composable
fun NumericKeypad(
    onDigit: (String) -> Unit,
    onBackspace: () -> Unit,
    onClear: () -> Unit
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Rząd 1-3
        Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            KeypadButton("1") { onDigit("1") }
            KeypadButton("2") { onDigit("2") }
            KeypadButton("3") { onDigit("3") }
        }
        
        // Rząd 4-6
        Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            KeypadButton("4") { onDigit("4") }
            KeypadButton("5") { onDigit("5") }
            KeypadButton("6") { onDigit("6") }
        }
        
        // Rząd 7-9
        Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            KeypadButton("7") { onDigit("7") }
            KeypadButton("8") { onDigit("8") }
            KeypadButton("9") { onDigit("9") }
        }
        
        // Rząd dolny
        Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            // Clear
            Box(
                modifier = Modifier
                    .size(72.dp)
                    .clip(CircleShape)
                    .clickable { onClear() },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Default.Clear,
                    contentDescription = "Clear",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            
            // 0
            KeypadButton("0") { onDigit("0") }
            
            // Backspace
            Box(
                modifier = Modifier
                    .size(72.dp)
                    .clip(CircleShape)
                    .clickable { onBackspace() },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Default.Backspace,
                    contentDescription = "Backspace",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
fun KeypadButton(
    digit: String,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .size(72.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .clickable { onClick() },
        contentAlignment = Alignment.Center
    ) {
        Text(
            digit,
            fontSize = 28.sp,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// PIN SETUP SCREEN
// ═══════════════════════════════════════════════════════════════════════════

@Composable
fun PinSetupScreen(
    onPinSet: () -> Unit
) {
    val context = LocalContext.current
    val duressPin = remember { DuressPin.getInstance(context) }
    
    var step by remember { mutableStateOf(1) } // 1 = enter, 2 = confirm
    var pin by remember { mutableStateOf("") }
    var confirmPin by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("Ustaw nowy PIN (min. 4 cyfry)") }
    var isError by remember { mutableStateOf(false) }
    var enableDuress by remember { mutableStateOf(true) }
    
    val currentPin = if (step == 1) pin else confirmPin
    
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(32.dp)
        ) {
            Icon(
                Icons.Default.Security,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            Text(
                if (step == 1) "Ustaw PIN" else "Potwierdź PIN",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                message,
                style = MaterialTheme.typography.bodyLarge,
                color = if (isError) MaterialTheme.colorScheme.error 
                       else MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
            
            Spacer(modifier = Modifier.height(32.dp))
            
            // PIN dots
            Row(
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                repeat(6) { index ->
                    PinDot(
                        filled = index < currentPin.length,
                        isError = isError
                    )
                }
            }
            
            Spacer(modifier = Modifier.height(32.dp))
            
            // Duress toggle
            if (step == 1) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(horizontal = 16.dp)
                ) {
                    Checkbox(
                        checked = enableDuress,
                        onCheckedChange = { enableDuress = it }
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Column {
                        Text(
                            "Włącz Duress PIN",
                            style = MaterialTheme.typography.bodyMedium
                        )
                        Text(
                            "Odwrotny PIN aktywuje tryb bezpieczeństwa",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Keypad
            NumericKeypad(
                onDigit = { digit ->
                    if (step == 1) {
                        if (pin.length < 6) pin += digit
                        
                        // Auto-advance po 4+ cyfrach
                        if (pin.length >= 4) {
                            // Użytkownik może kontynuować do 6
                        }
                    } else {
                        if (confirmPin.length < 6) confirmPin += digit
                        
                        // Sprawdź zgodność
                        if (confirmPin.length == pin.length) {
                            if (confirmPin == pin) {
                                duressPin.setPin(pin, enableDuress)
                                onPinSet()
                            } else {
                                isError = true
                                message = "PIN nie pasuje. Spróbuj ponownie."
                                confirmPin = ""
                            }
                        }
                    }
                },
                onBackspace = {
                    if (step == 1) {
                        if (pin.isNotEmpty()) pin = pin.dropLast(1)
                    } else {
                        if (confirmPin.isNotEmpty()) confirmPin = confirmPin.dropLast(1)
                    }
                    isError = false
                },
                onClear = {
                    if (step == 1) pin = "" else confirmPin = ""
                    isError = false
                }
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Next / Back buttons
            Row(
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                if (step == 2) {
                    OutlinedButton(
                        onClick = {
                            step = 1
                            confirmPin = ""
                            message = "Ustaw nowy PIN (min. 4 cyfry)"
                            isError = false
                        }
                    ) {
                        Text("Wstecz")
                    }
                }
                
                if (step == 1 && pin.length >= 4) {
                    Button(
                        onClick = {
                            step = 2
                            message = "Potwierdź PIN"
                            isError = false
                        }
                    ) {
                        Text("Dalej")
                    }
                }
            }
            
            // Info o Duress
            if (enableDuress && step == 1 && pin.length >= 4) {
                Spacer(modifier = Modifier.height(24.dp))
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer
                    )
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            "🛡️ Twój Duress PIN: ${pin.reversed()}",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            "Wpisanie tego PIN-u aktywuje tryb bezpieczeństwa",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
        }
    }
}
