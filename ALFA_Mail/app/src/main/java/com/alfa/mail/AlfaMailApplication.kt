package com.alfa.mail

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class AlfaMailApplication : Application() {

    companion object {
        const val CHANNEL_ID_SYNC = "alfa_mail_sync"
        const val CHANNEL_ID_NEW_MAIL = "alfa_mail_new"
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val syncChannel = NotificationChannel(
                CHANNEL_ID_SYNC,
                "Email Sync",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Background email synchronization"
            }

            val newMailChannel = NotificationChannel(
                CHANNEL_ID_NEW_MAIL,
                "New Email",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Notifications for new emails"
            }

            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannels(listOf(syncChannel, newMailChannel))
        }
    }
}
