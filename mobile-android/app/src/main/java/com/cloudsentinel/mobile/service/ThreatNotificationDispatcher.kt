package com.cloudsentinel.mobile.service

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.cloudsentinel.mobile.MainActivity
import com.cloudsentinel.mobile.R
import com.cloudsentinel.mobile.core.network.ThreatAlertItem

object ThreatNotificationDispatcher {

    fun show(context: Context, alert: ThreatAlertItem) {
        val notifId = alert.id.hashCode()
        val channelId = if (alert.riskScore >= 75 || alert.eventType.contains("TEST", ignoreCase = true)) {
            NotificationChannels.CRITICAL_DEFCON_CHANNEL
        } else {
            NotificationChannels.STANDARD_ALERTS_CHANNEL
        }

        val openIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openPending = PendingIntent.getActivity(
            context,
            notifId,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val title = if (alert.eventType.contains("TEST", ignoreCase = true)) {
            "CloudSentinel · Test Alert"
        } else {
            "CloudSentinel · Risk ${alert.riskScore}/100"
        }

        val builder = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(R.drawable.ic_shield_logo)
            .setContentTitle(title)
            .setContentText("${alert.ip} (${alert.country}) · ${alert.summary}")
            .setStyle(
                NotificationCompat.BigTextStyle()
                    .bigText("${alert.ip} (${alert.country})\n${alert.eventType}${if (alert.mitreId.isNotBlank()) " · ${alert.mitreId}" else ""}\n${alert.summary}")
            )
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openPending)

        if (!alert.blocked && alert.ip != "Unknown IP" && !alert.eventType.contains("TEST", ignoreCase = true)) {
            val blockIntent = Intent(context, NotificationActionReceiver::class.java).apply {
                action = NotificationActionReceiver.ACTION_BLOCK_IP
                putExtra(NotificationActionReceiver.EXTRA_IP, alert.ip)
                putExtra(NotificationActionReceiver.EXTRA_NOTIFICATION_ID, notifId)
            }
            val blockPending = PendingIntent.getBroadcast(
                context,
                notifId + 1,
                blockIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            builder.addAction(R.drawable.ic_shield_logo, "Block IP", blockPending)
        }

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(notifId, builder.build())
    }
}
