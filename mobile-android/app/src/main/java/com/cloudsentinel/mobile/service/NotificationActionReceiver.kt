package com.cloudsentinel.mobile.service

import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.cloudsentinel.mobile.CloudSentinelApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class NotificationActionReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION_BLOCK_IP) return
        val ip = intent.getStringExtra(EXTRA_IP) ?: return
        val notifId = intent.getIntExtra(EXTRA_NOTIFICATION_ID, -1)

        val pendingResult = goAsync()
        val repo = (context.applicationContext as? CloudSentinelApp)?.repository

        CoroutineScope(Dispatchers.IO).launch {
            try {
                repo?.blockIp(ip)
                if (notifId != -1) {
                    val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                    manager.cancel(notifId)
                }
            } finally {
                pendingResult.finish()
            }
        }
    }

    companion object {
        const val ACTION_BLOCK_IP = "com.cloudsentinel.mobile.ACTION_BLOCK_IP"
        const val EXTRA_IP = "extra_ip"
        const val EXTRA_NOTIFICATION_ID = "extra_notification_id"
    }
}
