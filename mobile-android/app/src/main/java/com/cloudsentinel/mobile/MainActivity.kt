package com.cloudsentinel.mobile

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import com.cloudsentinel.mobile.core.theme.CloudSentinelTheme
import com.cloudsentinel.mobile.ui.alerts.AlertFeedScreen
import com.cloudsentinel.mobile.ui.pairing.PairingScreen
import com.cloudsentinel.mobile.ui.settings.MobileSettingsScreen
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { _ -> }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }

        val repo = (application as CloudSentinelApp).repository

        setContent {
            CloudSentinelTheme(darkTheme = true) {
                val scope = rememberCoroutineScope()
                val alerts by repo.alerts.collectAsState()
                var session by remember { mutableStateOf(repo.getActiveSession()) }
                var showSettings by remember { mutableStateOf(false) }
                var isPairing by remember { mutableStateOf(false) }
                var pairError by remember { mutableStateOf<String?>(null) }
                var fcmToken by remember { mutableStateOf("") }

                // Retrieve FCM token gracefully if Firebase is configured
                LaunchedEffect(Unit) {
                    runCatching {
                        FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
                            fcmToken = token ?: ""
                            if (fcmToken.isNotBlank()) {
                                scope.launch { repo.syncFcmToken(fcmToken) }
                            }
                        }
                    }
                }

                // Periodic sync fallback so LAN demo works even without Firebase configured
                LaunchedEffect(session) {
                    while (session != null) {
                        repo.syncAlerts()
                        delay(5000)
                    }
                }

                when {
                    session == null -> {
                        PairingScreen(
                            isPairing = isPairing,
                            errorMessage = pairError,
                            onPairSubmit = { serverUrl, code, token ->
                                scope.launch {
                                    isPairing = true
                                    pairError = null
                                    repo.pairWithCode(serverUrl, code, token, fcmToken)
                                        .onSuccess { paired ->
                                            session = paired
                                            repo.syncAlerts()
                                        }
                                        .onFailure { err ->
                                            pairError = err.message ?: "Unable to connect to CloudSentinel server"
                                        }
                                    isPairing = false
                                }
                            }
                        )
                    }

                    showSettings -> {
                        MobileSettingsScreen(
                            session = session!!,
                            onBack = { showSettings = false },
                            onUnpair = {
                                repo.clearSession()
                                session = null
                                showSettings = false
                            }
                        )
                    }

                    else -> {
                        AlertFeedScreen(
                            alerts = alerts,
                            onRefresh = { scope.launch { repo.syncAlerts() } },
                            onBlockIp = { ip -> scope.launch { repo.blockIp(ip) } },
                            onOpenSettings = { showSettings = true }
                        )
                    }
                }
            }
        }
    }
}
