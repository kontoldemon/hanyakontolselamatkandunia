package com.cloudsentinel.mobile.data.repository

import android.os.Build
import com.cloudsentinel.mobile.core.network.ApiClient
import com.cloudsentinel.mobile.core.network.BlockIpRequest
import com.cloudsentinel.mobile.core.network.ClusterStatsResponse
import com.cloudsentinel.mobile.core.network.ExposureToggleRequest
import com.cloudsentinel.mobile.core.network.ExposureToggleResponse
import com.cloudsentinel.mobile.core.network.MobileAlertPolicyInfo
import com.cloudsentinel.mobile.core.network.MobileCopilotRequest
import com.cloudsentinel.mobile.core.network.MobileSessionItem
import com.cloudsentinel.mobile.core.network.PairDeviceRequest
import com.cloudsentinel.mobile.core.network.RefreshFcmTokenRequest
import com.cloudsentinel.mobile.core.network.RuntimeControlsRequest
import com.cloudsentinel.mobile.core.network.RuntimeControlsResponse
import com.cloudsentinel.mobile.core.network.ThreatAlertItem
import com.cloudsentinel.mobile.core.security.PairedSession
import com.cloudsentinel.mobile.core.security.SecureSessionStore
import java.util.UUID
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow

enum class CopilotSender {
    USER, COPILOT
}

data class CopilotMessage(
    val id: String = UUID.randomUUID().toString(),
    val sender: CopilotSender,
    val text: String,
    val timestampMs: Long = System.currentTimeMillis()
)

class AlertRepository(private val sessionStore: SecureSessionStore) {

    private val _alerts = MutableStateFlow<List<ThreatAlertItem>>(emptyList())
    val alerts: StateFlow<List<ThreatAlertItem>> = _alerts.asStateFlow()

    private val _stats = MutableStateFlow<ClusterStatsResponse?>(null)
    val stats: StateFlow<ClusterStatsResponse?> = _stats.asStateFlow()

    private val _sessions = MutableStateFlow<List<MobileSessionItem>>(emptyList())
    val sessions: StateFlow<List<MobileSessionItem>> = _sessions.asStateFlow()

    private val _isSensorReachable = MutableStateFlow<Boolean?>(null)
    val isSensorReachable: StateFlow<Boolean?> = _isSensorReachable.asStateFlow()

    private val _incomingNotifications = MutableSharedFlow<ThreatAlertItem>(extraBufferCapacity = 16)
    val incomingNotifications: SharedFlow<ThreatAlertItem> = _incomingNotifications.asSharedFlow()

    private var hasSeededAlertIds = false
    private val seenAlertIds = mutableSetOf<String>()

    private val _copilotMessages = MutableStateFlow<List<CopilotMessage>>(
        listOf(
            CopilotMessage(
                sender = CopilotSender.COPILOT,
                text = "CloudSentinel Copilot ready. Ask about active threats, IPs, MITRE techniques, or ingress status."
            )
        )
    )
    val copilotMessages: StateFlow<List<CopilotMessage>> = _copilotMessages.asStateFlow()

    fun getActiveSession(): PairedSession? = sessionStore.getSession()

    fun activateDevSession(session: PairedSession) {
        sessionStore.saveSession(session)
    }

    fun clearSession() {
        sessionStore.clearSession()
        _alerts.value = emptyList()
        _stats.value = null
        _sessions.value = emptyList()
        _isSensorReachable.value = null
        hasSeededAlertIds = false
        seenAlertIds.clear()
    }

    suspend fun pairWithCode(
        serverUrl: String,
        pairingCode: String,
        pairingToken: String,
        fcmToken: String = ""
    ): Result<PairedSession> = runCatching {
        val api = ApiClient.create(serverUrl)
        val deviceModel = "${Build.MANUFACTURER} ${Build.MODEL}".trim()
        val response = api.pairDevice(
            PairDeviceRequest(
                pairingCode = pairingCode.trim(),
                pairingToken = pairingToken.trim(),
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
        _isSensorReachable.value = true
        session
    }

    suspend fun syncAlerts(): Result<List<ThreatAlertItem>> = runCatching {
        val session = sessionStore.getSession() ?: error("Not paired")
        val api = ApiClient.create(session.serverUrl, session.deviceToken)
        val response = api.getAlerts(limit = 50)
        val incoming = response.alerts
        if (!hasSeededAlertIds) {
            incoming.forEach { seenAlertIds.add(it.id) }
            hasSeededAlertIds = true
        } else {
            val policy = _stats.value?.alert_policy ?: MobileAlertPolicyInfo()
            incoming.filter { it.id !in seenAlertIds }.forEach { alert ->
                seenAlertIds.add(alert.id)
                val isTest = alert.eventType.contains("TEST", ignoreCase = true)
                val shouldNotify = isTest || (policy.enabled && alert.riskScore >= policy.minRiskScore)
                if (shouldNotify) {
                    _incomingNotifications.tryEmit(alert)
                }
            }
        }
        _alerts.value = incoming
        _isSensorReachable.value = true
        incoming
    }.onFailure {
        _isSensorReachable.value = false
    }

    suspend fun syncDashboardStats(): Result<ClusterStatsResponse> = runCatching {
        val session = sessionStore.getSession() ?: error("Not paired")
        val api = ApiClient.create(session.serverUrl, session.deviceToken)
        val response = api.getDashboardStats()
        _stats.value = response
        _isSensorReachable.value = true
        response
    }.onFailure {
        _isSensorReachable.value = false
    }

    suspend fun toggleExposure(enabled: Boolean): Result<ExposureToggleResponse> = runCatching {
        val session = sessionStore.getSession() ?: error("Not paired")
        val api = ApiClient.create(session.serverUrl, session.deviceToken)
        val response = api.toggleExposure(ExposureToggleRequest(enabled = enabled))
        require(response.ok) {
            response.message.ifBlank { "Exposure toggle failed" }
        }
        _isSensorReachable.value = true
        syncDashboardStats()
        response
    }.onFailure {
        _isSensorReachable.value = false
    }

    suspend fun syncSessions(): Result<List<MobileSessionItem>> = runCatching {
        val session = sessionStore.getSession() ?: error("Not paired")
        val api = ApiClient.create(session.serverUrl, session.deviceToken)
        val response = api.getSessions()
        _sessions.value = response.sessions
        _isSensorReachable.value = true
        response.sessions
    }.onFailure {
        _isSensorReachable.value = false
    }

    suspend fun blockIp(ip: String, ttlSeconds: Long? = null): Result<Unit> = runCatching {
        val session = sessionStore.getSession() ?: error("Not paired")
        val api = ApiClient.create(session.serverUrl, session.deviceToken)
        api.blockIp(BlockIpRequest(ip = ip, ttl = ttlSeconds))
        _alerts.value = _alerts.value.map { item ->
            if (item.ip == ip) item.copy(blocked = true) else item
        }
        _sessions.value = _sessions.value.map { item ->
            if (item.ip == ip) item.copy(blocked = true) else item
        }
        _isSensorReachable.value = true
        syncDashboardStats()
        Unit
    }.onFailure {
        _isSensorReachable.value = false
    }

    suspend fun askCopilot(prompt: String): Result<String> = runCatching {
        val trimmed = prompt.trim()
        require(trimmed.isNotBlank()) { "Prompt cannot be empty" }
        _copilotMessages.value = _copilotMessages.value + CopilotMessage(
            sender = CopilotSender.USER,
            text = trimmed
        )
        val session = sessionStore.getSession()
        if (session == null) {
            val offlineMsg = "Sensor not paired yet. Pair with your CloudSentinel dashboard to query the live AI Copilot."
            _copilotMessages.value = _copilotMessages.value + CopilotMessage(
                sender = CopilotSender.COPILOT,
                text = offlineMsg
            )
            return@runCatching offlineMsg
        }
        val api = ApiClient.create(session.serverUrl, session.deviceToken)
        val response = api.askAiCopilot(MobileCopilotRequest(prompt = trimmed))
        _isSensorReachable.value = true
        val answer = if (response.ok && response.response.isNotBlank()) {
            response.response
        } else {
            response.error ?: "AI Copilot unavailable on sensor."
        }
        _copilotMessages.value = _copilotMessages.value + CopilotMessage(
            sender = CopilotSender.COPILOT,
            text = answer
        )
        answer
    }.onFailure {
        _isSensorReachable.value = false
        _copilotMessages.value = _copilotMessages.value + CopilotMessage(
            sender = CopilotSender.COPILOT,
            text = "Sensor unreachable. Check your network connection or gateway endpoint in Settings."
        )
    }

    suspend fun updateAlertPolicy(policy: MobileAlertPolicyInfo): Result<MobileAlertPolicyInfo> = runCatching {
        _stats.value = (_stats.value ?: ClusterStatsResponse()).copy(alert_policy = policy)
        val session = sessionStore.getSession() ?: error("Not paired")
        val api = ApiClient.create(session.serverUrl, session.deviceToken)
        val response = api.updatePolicy(policy)
        _stats.value = (_stats.value ?: ClusterStatsResponse()).copy(alert_policy = response.policy)
        _isSensorReachable.value = true
        response.policy
    }.onFailure {
        _isSensorReachable.value = false
    }

    suspend fun updateRuntimeControls(
        deceptionLevel: String? = null,
        soarDryRun: Boolean? = null,
        hasshAction: String? = null
    ): Result<RuntimeControlsResponse> = runCatching {
        val current = _stats.value ?: ClusterStatsResponse()
        _stats.value = current.copy(
            deception_level = deceptionLevel ?: current.deception_level,
            soar_dry_run = soarDryRun ?: current.soar_dry_run,
            hassh_action = hasshAction ?: current.hassh_action
        )
        val session = sessionStore.getSession() ?: error("Not paired")
        val api = ApiClient.create(session.serverUrl, session.deviceToken)
        val response = api.updateRuntimeControls(
            RuntimeControlsRequest(
                deception_level = deceptionLevel,
                soar_dry_run = soarDryRun,
                hassh_action = hasshAction
            )
        )
        _stats.value = (_stats.value ?: ClusterStatsResponse()).copy(
            deception_level = response.deception_level,
            soar_dry_run = response.soar_dry_run,
            hassh_action = response.hassh_action
        )
        _isSensorReachable.value = true
        response
    }.onFailure {
        _isSensorReachable.value = false
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
