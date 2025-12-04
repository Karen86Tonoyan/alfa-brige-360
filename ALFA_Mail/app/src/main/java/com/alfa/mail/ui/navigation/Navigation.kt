package com.alfa.mail.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.alfa.mail.ui.screens.inbox.InboxScreen
import com.alfa.mail.ui.screens.compose.ComposeScreen
import com.alfa.mail.ui.screens.settings.SettingsScreen

sealed class Screen(val route: String) {
    object Inbox : Screen("inbox")
    object Compose : Screen("compose")
    object Settings : Screen("settings")
    object EmailDetail : Screen("email/{emailId}") {
        fun createRoute(emailId: Long) = "email/$emailId"
    }
}

@Composable
fun AlfaMailNavHost() {
    val navController = rememberNavController()

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
                }
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
    }
}
