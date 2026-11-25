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
    val reason: String = "mobile-companion-action"
)

@Serializable
data class SimpleOkResponse(
    val ok: Boolean = false,
    val action: String = ""
)
