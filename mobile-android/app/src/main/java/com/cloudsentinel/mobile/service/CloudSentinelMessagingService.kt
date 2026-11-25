package com.cloudsentinel.mobile.service

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.cloudsentinel.mobile.CloudSentinelApp
import com.cloudsentinel.mobile.MainActivity
import com.cloudsentinel.mobile.R
import com.cloudsentinel.mobile.core.network.ThreatAlertItem
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class CloudSentinelMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        val repo = (application as? CloudSentinelApp)?.repository ?: return
        CoroutineScope(Dispatchers.IO).launch {
            repo.syncFcmToken(token)
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val data = message.data
        if (data.isEmpty()) return

        val alert = ThreatAlertItem(
            id = data["alertId"] ?: "fcm_${System.currentTimeMillis()}",
            ip = data["ip"] ?: "Unknown IP",
            country = data["country"] ?: "Unknown",
            riskScore = data["riskScore"]?.toIntOrNull() ?: 80,
            eventType = data["eventType"] ?: "THREAT_DETECTED",
            summary = data["summary"] ?: "Suspicious SSH intrusion detected",
            mitreId = data["mitreId"] ?: "",
            blocked = data["blocked"] == "true",
            timestampMs = data["timestampMs"]?.toLongOrNull() ?: System.currentTimeMillis()
        )

        (application as? CloudSentinelApp)?.repository?.prependIncomingPush(alert)
        showThreatNotification(alert)
    }

    private fun showThreatNotification(alert: ThreatAlertItem) {
        val notifId = alert.id.hashCode()
        val channelId = if (alert.riskScore >= 75) {
            NotificationChannels.CRITICAL_DEFCON_CHANNEL
        } else {
            NotificationChannels.STANDARD_ALERTS_CHANNEL
        }

        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openPending = PendingIntent.getActivity(
            this,
            notifId,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_shield_logo)
            .setContentTitle("CloudSentinel | Risk ${alert.riskScore}/100")
            .setContentText("${alert.ip} (${alert.country}) - ${alert.summary}")
            .setStyle(
                NotificationCompat.BigTextStyle()
                    .bigText("${alert.ip} (${alert.country})\n${alert.eventType}${if (alert.mitreId.isNotBlank()) " | ${alert.mitreId}" else ""}\n${alert.summary}")
            )
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openPending)

        if (!alert.blocked && alert.ip != "Unknown IP") {
            val blockIntent = Intent(this, NotificationActionReceiver::class.java).apply {
                action = NotificationActionReceiver.ACTION_BLOCK_IP
                putExtra(NotificationActionReceiver.EXTRA_IP, alert.ip)
                putExtra(NotificationActionReceiver.EXTRA_NOTIFICATION_ID, notifId)
            }
            val blockPending = PendingIntent.getBroadcast(
                this,
                notifId + 1,
                blockIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            builder.addAction(R.drawable.ic_shield_logo, "Block IP", blockPending)
        }

        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(notifId, builder.build())
    }
}
