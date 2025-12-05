package com.alfa.mail

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.alfa.mail.security.DuressPin
import com.alfa.mail.ui.theme.AlfaMailTheme
import com.alfa.mail.ui.navigation.AlfaMailNavHost
import com.alfa.mail.ui.screens.lock.PinLockScreen
import com.alfa.mail.ui.screens.lock.PinSetupScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            AlfaMailTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val duressPin = remember { DuressPin.getInstance(this@MainActivity) }
                    
                    // Stan aplikacji
                    var isUnlocked by remember { mutableStateOf(false) }
                    var isDuressMode by remember { mutableStateOf(false) }
                    var needsSetup by remember { mutableStateOf(!duressPin.isPinSet()) }
                    
                    when {
                        needsSetup -> {
                            // Pierwszy raz - ustaw PIN
                            PinSetupScreen(
                                onPinSet = {
                                    needsSetup = false
                                    isUnlocked = true
                                }
                            )
                        }
                        !isUnlocked -> {
                            // Zablokowane - wpisz PIN
                            PinLockScreen(
                                onUnlocked = { isDuress ->
                                    isUnlocked = true
                                    isDuressMode = isDuress
                                },
                                onSetupRequired = {
                                    needsSetup = true
                                }
                            )
                        }
                        else -> {
                            // Odblokowane - główna nawigacja
                            AlfaMailNavHost(isDuressMode = isDuressMode)
                        }
                    }
                }
            }
        }
    }
}
