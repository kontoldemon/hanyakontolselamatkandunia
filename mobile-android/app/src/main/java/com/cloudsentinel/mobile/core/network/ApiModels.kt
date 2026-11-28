package com.cloudsentinel.mobile.core.network

import kotlinx.serialization.Serializable

@Serializable
data class QrPairingPayload(
    val v: Int = 1,
    val serverUrl: String,
    val pairingCode: String,
    val pairingToken: String = ""
)

@Serializable
data class PairDeviceRequest(
    val pairingCode: String,
    val pairingToken: String = "",
    val deviceName: String,
    val fcmToken: String = "",
    val platform: String = "android"
)

@Serializable
data class PairDeviceResponse(
    val ok: Boolean = false,
    val deviceId: String = "",
    val deviceName: String = "",
    val deviceToken: String = "",
    val pairedAtMs: Long = 0L
)

@Serializable
data class ThreatAlertItem(
    val id: String,
    val ip: String,
    val country: String = "Unknown",
    val riskScore: Int = 0,
    val eventType: String = "THREAT_DETECTED",
    val summary: String = "",
    val mitreId: String = "",
    val blocked: Boolean = false,
    val timestampMs: Long = 0L
)

@Serializable
data class MobileAlertsResponse(
    val ok: Boolean = false,
    val deviceId: String = "",
    val alerts: List<ThreatAlertItem> = emptyList()
)

@Serializable
data class RefreshFcmTokenRequest(
    val fcmToken: String
)

@Serializable
data class BlockIpRequest(
    val ip: String,
    val reason: String = "mobile-companion-action",
    val ttl: Long? = null
)

@Serializable
data class SimpleOkResponse(
    val ok: Boolean = false,
    val action: String = ""
)

@Serializable
data class IngressExposureInfo(
    val enabled: Boolean = true,
    val port: Int = 2222,
    val provider: String = "iptables",
    val target: String = "0.0.0.0:2222/TCP"
)

@Serializable
data class MobileAlertPolicyInfo(
    val enabled: Boolean = true,
    val minRiskScore: Int = 70,
    val cooldownSeconds: Int = 60,
    val notifyBruteForce: Boolean = true,
    val notifyCommandExec: Boolean = true,
    val notifySoarBlock: Boolean = true
)

@Serializable
data class UpdatePolicyResponse(
    val ok: Boolean = false,
    val policy: MobileAlertPolicyInfo = MobileAlertPolicyInfo()
)

@Serializable
data class RuntimeControlsRequest(
    val deception_level: String? = null,
    val soar_dry_run: Boolean? = null,
    val hassh_action: String? = null
)

@Serializable
data class RuntimeControlsResponse(
    val ok: Boolean = false,
    val deception_level: String = "full",
    val soar_dry_run: Boolean = false,
    val hassh_action: String = "monitor"
)

@Serializable
data class ClusterStatsResponse(
    val ok: Boolean = false,
    val deviceId: String = "",
    val connections: Long = 0L,
    val events_total: Long = 0L,
    val mttb_seconds: Double = 0.0,
    val mitre_count: Int = 0,
    val blocked_ips_count: Int = 0,
    val sensor_status: String = "ONLINE",
    val sensor_uptime_seconds: Long = 0L,
    val ingress_exposure: IngressExposureInfo = IngressExposureInfo(),
    val top_threat_origin: String = "Unknown",
    val active_attackers_count: Int = 0,
    val blocked_ips: List<String> = emptyList(),
    val deception_level: String = "full",
    val soar_dry_run: Boolean = false,
    val hassh_action: String = "monitor",
    val alert_policy: MobileAlertPolicyInfo = MobileAlertPolicyInfo()
)

@Serializable
data class ExposureToggleRequest(
    val enabled: Boolean
)

@Serializable
data class ExposureToggleResponse(
    val ok: Boolean = false,
    val enabled: Boolean = true,
    val provider: String = "",
    val message: String = ""
)

@Serializable
data class MobileSessionItem(
    val id: String = "",
    val ip: String = "",
    val country: String = "Unknown",
    val city: String = "Unknown",
    val isp: String = "",
    val hassh: String = "",
    val risk_score: Int = 0,
    val duration: String = "",
    val mitre_techniques: List<String> = emptyList(),
    val commands: List<String> = emptyList(),
    val blocked: Boolean = false,
    val timestamp_ms: Long = 0L
)

@Serializable
data class MobileSessionsResponse(
    val ok: Boolean = false,
    val deviceId: String = "",
    val sessions: List<MobileSessionItem> = emptyList()
)

@Serializable
data class MobileCopilotRequest(
    val prompt: String,
    val context: String = ""
)

@Serializable
data class MobileCopilotResponse(
    val ok: Boolean = false,
    val response: String = "",
    val error: String? = null
)
