package com.alfa.mail.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.alfa.mail.ui.screens.inbox.InboxScreen
import com.alfa.mail.ui.screens.compose.ComposeScreen
import com.alfa.mail.ui.screens.settings.SettingsScreen
import com.alfa.mail.ui.screens.generator.UIGeneratorScreen
import com.alfa.mail.ui.screens.automation.AutomationScreen
import com.alfa.mail.ui.screens.automation.AutopilotDashboardScreen
import com.alfa.mail.ui.screens.automation.BehaviorInsightsScreen

// Duress mode flag - dostępny globalnie w aplikacji
val LocalDuressMode = compositionLocalOf { false }

sealed class Screen(val route: String) {
    object Inbox : Screen("inbox")
    object Compose : Screen("compose")
    object Settings : Screen("settings")
    object UIGenerator : Screen("ui_generator")
    object AutopilotDashboard : Screen("autopilot_dashboard")
    object BehaviorInsights : Screen("behavior_insights")
    object EmailDetail : Screen("email/{emailId}") {
        fun createRoute(emailId: Long) = "email/$emailId"
    }
}

@Composable
fun AlfaMailNavHost(isDuressMode: Boolean = false) {
    val navController = rememberNavController()

    // Udostępnij isDuressMode dla całej aplikacji
    CompositionLocalProvider(LocalDuressMode provides isDuressMode) {
        NavHost(
            navController = navController,
            startDestination = Screen.Inbox.route
        ) {
            composable(Screen.Inbox.route) {
                InboxScreen(
                    onComposeClick = { navController.navigate(Screen.Compose.route) },
                    onSettingsClick = { navController.navigate(Screen.Settings.route) },
                    onEmailClick = { emailId ->
                        navController.navigate(Screen.EmailDetail.createRoute(emailId))
                    },
                    onUIGeneratorClick = { navController.navigate(Screen.UIGenerator.route) },
                    onAutopilotClick = { navController.navigate(Screen.AutopilotDashboard.route) },
                    onBehaviorInsightsClick = { navController.navigate(Screen.BehaviorInsights.route) }
                )
            }

            composable(Screen.Compose.route) {
                ComposeScreen(
                    onBack = { navController.popBackStack() },
                    onSent = { navController.popBackStack() }
                )
            }

            composable(Screen.Settings.route) {
                SettingsScreen(
                    onBack = { navController.popBackStack() }
                )
            }
            
            composable(Screen.UIGenerator.route) {
                UIGeneratorScreen(
                    onBack = { navController.popBackStack() }
                )
            }
            
            composable(Screen.AutopilotDashboard.route) {
                AutopilotDashboardScreen(
                    onBack = { navController.popBackStack() }
                )
            }
            
            composable(Screen.BehaviorInsights.route) {
                BehaviorInsightsScreen(
                    onBack = { navController.popBackStack() }
                )
            }
        }
    }
}
