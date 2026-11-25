package com.cloudsentinel.mobile.data.repository

import android.os.Build
import com.cloudsentinel.mobile.core.network.ApiClient
import com.cloudsentinel.mobile.core.network.BlockIpRequest
import com.cloudsentinel.mobile.core.network.PairDeviceRequest
import com.cloudsentinel.mobile.core.network.RefreshFcmTokenRequest
import com.cloudsentinel.mobile.core.network.ThreatAlertItem
import com.cloudsentinel.mobile.core.security.PairedSession
import com.cloudsentinel.mobile.core.security.SecureSessionStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class AlertRepository(private val sessionStore: SecureSessionStore) {

    private val _alerts = MutableStateFlow<List<ThreatAlertItem>>(emptyList())
    val alerts: StateFlow<List<ThreatAlertItem>> = _alerts.asStateFlow()

    fun getActiveSession(): PairedSession? = sessionStore.getSession()

    fun clearSession() {
        sessionStore.clearSession()
        _alerts.value = emptyList()
    }

    suspend fun pairWithCode(
        serverUrl: String,
        pairingCode: String,
        fcmToken: String = ""
    ): Result<PairedSession> = runCatching {
        val api = ApiClient.create(serverUrl)
        val deviceModel = "${Build.MANUFACTURER} ${Build.MODEL}".trim()
        val response = api.pairDevice(
            PairDeviceRequest(
                pairingCode = pairingCode.trim(),
                deviceName = deviceModel.ifBlank { "Android Companion" },
                fcmToken = fcmToken
            )
        )
        require(response.ok && response.deviceToken.isNotBlank()) {
            "Pairing failed: invalid or expired code"
        }
        val session = PairedSession(
            serverUrl = serverUrl.trim().trimEnd('/'),
            deviceId = response.deviceId,
            deviceName = response.deviceName,
            deviceToken = response.deviceToken
        )
        sessionStore.saveSession(session)
        session
    }

    suspend fun syncAlerts(): Result<List<ThreatAlertItem>> = runCatching {
        val session = sessionStore.getSession() ?: error("Not paired")
        val api = ApiClient.create(session.serverUrl, session.deviceToken)
        val response = api.getAlerts(limit = 50)
        _alerts.value = response.alerts
        response.alerts
    }

    suspend fun blockIp(ip: String): Result<Unit> = runCatching {
        val session = sessionStore.getSession() ?: error("Not paired")
        val api = ApiClient.create(session.serverUrl, session.deviceToken)
        api.blockIp(BlockIpRequest(ip = ip))
        _alerts.value = _alerts.value.map { item ->
            if (item.ip == ip) item.copy(blocked = true) else item
        }
    }

    suspend fun syncFcmToken(fcmToken: String) {
        val session = sessionStore.getSession() ?: return
        runCatching {
            val api = ApiClient.create(session.serverUrl, session.deviceToken)
            api.updateFcmToken(RefreshFcmTokenRequest(fcmToken = fcmToken))
        }
    }

    fun prependIncomingPush(alert: ThreatAlertItem) {
        val current = _alerts.value
        if (current.any { it.id == alert.id }) return
        _alerts.value = listOf(alert) + current.take(99)
    }
}
