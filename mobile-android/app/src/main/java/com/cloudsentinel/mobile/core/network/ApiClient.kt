package com.cloudsentinel.mobile.core.network

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

object ApiClient {

    val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
    }

    fun create(baseUrl: String, deviceToken: String? = null): CloudSentinelApi {
        val normalizedBase = baseUrl.trim().trimEnd('/') + "/"
        val authInterceptor = Interceptor { chain ->
            val reqBuilder = chain.request().newBuilder()
                .header("Accept", "application/json")
            if (!deviceToken.isNullOrBlank()) {
                reqBuilder.header("Authorization", "Bearer $deviceToken")
            }
            chain.proceed(reqBuilder.build())
        }

        val client = OkHttpClient.Builder()
            .connectTimeout(8, TimeUnit.SECONDS)
            .readTimeout(12, TimeUnit.SECONDS)
            .writeTimeout(12, TimeUnit.SECONDS)
            .addInterceptor(authInterceptor)
            .build()

        return Retrofit.Builder()
            .baseUrl(normalizedBase)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(CloudSentinelApi::class.java)
    }
}
