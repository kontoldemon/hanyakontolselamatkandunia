package com.cloudsentinel.mobile.core.security

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

data class PairedSession(
    val serverUrl: String,
    val deviceId: String,
    val deviceName: String,
    val deviceToken: String
)

class SecureSessionStore(context: Context) {

    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs = EncryptedSharedPreferences.create(
        context,
        "cloudsentinel_secure_session",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun saveSession(session: PairedSession) {
        prefs.edit()
            .putString(KEY_SERVER_URL, session.serverUrl)
            .putString(KEY_DEVICE_ID, session.deviceId)
            .putString(KEY_DEVICE_NAME, session.deviceName)
            .putString(KEY_DEVICE_TOKEN, session.deviceToken)
            .apply()
    }

    fun getSession(): PairedSession? {
        val url = prefs.getString(KEY_SERVER_URL, null) ?: return null
        val token = prefs.getString(KEY_DEVICE_TOKEN, null) ?: return null
        val id = prefs.getString(KEY_DEVICE_ID, "") ?: ""
        val name = prefs.getString(KEY_DEVICE_NAME, "Android Companion") ?: "Android Companion"
        if (url.isBlank() || token.isBlank()) return null
        return PairedSession(
            serverUrl = url,
            deviceId = id,
            deviceName = name,
            deviceToken = token
        )
    }

    fun clearSession() {
        prefs.edit().clear().apply()
    }

    companion object {
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_DEVICE_NAME = "device_name"
        private const val KEY_DEVICE_TOKEN = "device_token"
    }
}
