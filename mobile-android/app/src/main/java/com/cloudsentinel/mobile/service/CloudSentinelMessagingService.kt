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
        ThreatNotificationDispatcher.show(this, alert)
    }
}
