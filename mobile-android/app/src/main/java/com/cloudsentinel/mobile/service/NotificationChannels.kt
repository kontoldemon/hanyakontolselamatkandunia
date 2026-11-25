package com.cloudsentinel.mobile.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build

object NotificationChannels {
    const val CRITICAL_DEFCON_CHANNEL = "cloudsentinel_defcon_critical"
    const val STANDARD_ALERTS_CHANNEL = "cloudsentinel_standard_alerts"

    fun register(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        val critical = NotificationChannel(
            CRITICAL_DEFCON_CHANNEL,
            "DEFCON Critical Threats",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "High-risk SSH intrusions and automated containment alerts"
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 220, 120, 220)
        }

        val standard = NotificationChannel(
            STANDARD_ALERTS_CHANNEL,
            "Standard Sensor Alerts",
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = "General honeypot telemetry notifications"
        }

        manager.createNotificationChannel(critical)
        manager.createNotificationChannel(standard)
    }
}
