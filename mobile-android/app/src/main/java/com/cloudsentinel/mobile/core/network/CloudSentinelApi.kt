package com.cloudsentinel.mobile.core.network

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface CloudSentinelApi {

    @POST("mobile/pair")
    suspend fun pairDevice(@Body request: PairDeviceRequest): PairDeviceResponse

    @GET("mobile/alerts")
    suspend fun getAlerts(@Query("limit") limit: Int = 50): MobileAlertsResponse

    @POST("mobile/fcm-token")
    suspend fun updateFcmToken(@Body request: RefreshFcmTokenRequest): SimpleOkResponse

    @POST("mobile/block-ip")
    suspend fun blockIp(@Body request: BlockIpRequest): SimpleOkResponse

    @GET("mobile/dashboard")
    suspend fun getDashboardStats(): ClusterStatsResponse

    @POST("mobile/exposure")
    suspend fun toggleExposure(@Body request: ExposureToggleRequest): ExposureToggleResponse

    @GET("mobile/sessions")
    suspend fun getSessions(): MobileSessionsResponse

    @POST("mobile/ai-copilot")
    suspend fun askAiCopilot(@Body request: MobileCopilotRequest): MobileCopilotResponse

    @POST("mobile/policy")
    suspend fun updatePolicy(@Body request: MobileAlertPolicyInfo): UpdatePolicyResponse

    @POST("mobile/runtime-controls")
    suspend fun updateRuntimeControls(@Body request: RuntimeControlsRequest): RuntimeControlsResponse
}
