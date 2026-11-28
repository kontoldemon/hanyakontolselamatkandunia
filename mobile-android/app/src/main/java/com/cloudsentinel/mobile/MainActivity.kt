package com.cloudsentinel.mobile

import android.Manifest
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.ui.Alignment
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withStyle
import com.cloudsentinel.mobile.core.theme.TextPrimaryDark
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.cloudsentinel.mobile.core.network.MobileSessionItem
import com.cloudsentinel.mobile.core.theme.CloudSentinelTheme
import com.cloudsentinel.mobile.core.theme.ElectricBlueSoft
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.HorizontalDivider
import androidx.compose.ui.unit.dp
import com.cloudsentinel.mobile.core.theme.ElectricBlue
import com.cloudsentinel.mobile.core.theme.ObsidianBg
import com.cloudsentinel.mobile.core.theme.ObsidianBorder
import com.cloudsentinel.mobile.core.theme.ObsidianCard
import com.cloudsentinel.mobile.core.theme.ObsidianPanel
import com.cloudsentinel.mobile.core.theme.TextMutedDark
import com.cloudsentinel.mobile.core.theme.ThemeMode
import com.cloudsentinel.mobile.core.theme.ThemePreference
import com.cloudsentinel.mobile.service.ThreatNotificationDispatcher
import com.cloudsentinel.mobile.ui.alerts.AlertFeedScreen
import com.cloudsentinel.mobile.ui.copilot.AiCopilotScreen
import com.cloudsentinel.mobile.ui.forensics.SessionInspectorSheet
import com.cloudsentinel.mobile.ui.pairing.PairingScreen
import com.cloudsentinel.mobile.ui.sessions.SessionsScreen
import com.cloudsentinel.mobile.ui.settings.MobileSettingsScreen
import com.cloudsentinel.mobile.ui.warroom.WarRoomScreen
import androidx.core.view.WindowCompat
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { _ -> }

    @OptIn(ExperimentalMaterial3Api::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }

        val repo = (application as CloudSentinelApp).repository

        setContent {
            val themePreference = remember { ThemePreference(this) }
            var themeMode by remember { mutableStateOf(themePreference.mode) }
            val darkTheme = when (themeMode) {
                ThemeMode.LIGHT -> false
                ThemeMode.DARK -> true
                ThemeMode.SYSTEM -> isSystemInDarkTheme()
            }
            CloudSentinelTheme(darkTheme = darkTheme) {
                val statusBarColor = MaterialTheme.colorScheme.background.toArgb()
                val navBarColor = MaterialTheme.colorScheme.surfaceVariant.toArgb()
                SideEffect {
                    window.statusBarColor = statusBarColor
                    window.navigationBarColor = navBarColor
                    WindowCompat.getInsetsController(window, window.decorView).apply {
                        isAppearanceLightStatusBars = !darkTheme
                        isAppearanceLightNavigationBars = !darkTheme
                    }
                }
                val scope = rememberCoroutineScope()
                val alerts by repo.alerts.collectAsState()
                val stats by repo.stats.collectAsState()
                val sessions by repo.sessions.collectAsState()
                val copilotMessages by repo.copilotMessages.collectAsState()
                val isSensorReachable by repo.isSensorReachable.collectAsState()

                var session by remember { mutableStateOf(repo.getActiveSession()) }
                var selectedTab by remember { mutableIntStateOf(0) } // 0: WarRoom, 1: Sessions, 2: Alerts, 3: Copilot, 4: Settings
                var isPairing by remember { mutableStateOf(false) }
                var pairError by remember { mutableStateOf<String?>(null) }
                var fcmToken by remember { mutableStateOf("") }
                var isRefreshing by remember { mutableStateOf(false) }

                // Forensics inspector bottom sheet state
                var inspectingSession by remember { mutableStateOf<MobileSessionItem?>(null) }
                val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

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

                // Handle one-click deep link: cloudsentinel://pair?server=...&code=...&token=...
                LaunchedEffect(intent?.data) {
                    val data = intent?.data
                    if (session == null && data != null && data.scheme == "cloudsentinel" && data.host == "pair") {
                        val srv = data.getQueryParameter("server").orEmpty()
                        val code = data.getQueryParameter("code").orEmpty()
                        val tok = data.getQueryParameter("token").orEmpty()
                        if (srv.isNotBlank() && code.isNotBlank()) {
                            isPairing = true
                            pairError = null
                            repo.pairWithCode(srv, code, tok, fcmToken)
                                .onSuccess { paired ->
                                    session = paired
                                    repo.syncAlerts()
                                    repo.syncDashboardStats()
                                    repo.syncSessions()
                                }
                                .onFailure { err ->
                                    pairError = err.message ?: "Unable to connect to CloudSentinel server"
                                }
                            isPairing = false
                        }
                    }
                }

                // Fire real Android status-bar notifications for newly arrived alerts
                LaunchedEffect(Unit) {
                    repo.incomingNotifications.collect { alert ->
                        ThreatNotificationDispatcher.show(this@MainActivity, alert)
                    }
                }

                // Periodic telemetry sync loop
                LaunchedEffect(session) {
                    while (session != null) {
                        repo.syncAlerts()
                        repo.syncDashboardStats()
                        repo.syncSessions()
                        delay(5000)
                    }
                }

                if (session == null) {
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
                                        repo.syncDashboardStats()
                                        repo.syncSessions()
                                    }
                                    .onFailure { err ->
                                        pairError = err.message ?: "Unable to connect to CloudSentinel server"
                                    }
                                isPairing = false
                            }
                        },
                        onDemoBypass = {
                            val devSession = com.cloudsentinel.mobile.core.security.PairedSession(
                                serverUrl = "https://cloudsentinel-4nxdgq72ncekc.eastasia.cloudapp.azure.com",
                                deviceId = "dev-tester-01",
                                deviceName = "Developer Companion",
                                deviceToken = "cs_mob_dev_bypass"
                            )
                            repo.activateDevSession(devSession)
                            session = devSession
                            scope.launch {
                                repo.syncAlerts()
                                repo.syncDashboardStats()
                                repo.syncSessions()
                            }
                        }
                    )
                } else {
                    Scaffold(
                        containerColor = ObsidianBg,
                        bottomBar = {
                            Column {
                                HorizontalDivider(color = ObsidianBorder, thickness = 1.dp)
                                NavigationBar(
                                    containerColor = ObsidianPanel,
                                    contentColor = TextPrimaryDark,
                                    tonalElevation = 0.dp
                                ) {
                                    NavigationBarItem(
                                        selected = selectedTab == 0,
                                        onClick = { selectedTab = 0 },
                                        icon = {
                                            Icon(
                                                imageVector = Icons.Default.Dashboard,
                                                contentDescription = "War Room"
                                            )
                                        },
                                        label = {
                                            Text(
                                                text = "War Room",
                                                fontSize = 11.sp,
                                                fontWeight = if (selectedTab == 0) FontWeight.SemiBold else FontWeight.Normal
                                            )
                                        },
                                        colors = NavigationBarItemDefaults.colors(
                                            selectedIconColor = ElectricBlueSoft,
                                            selectedTextColor = ElectricBlueSoft,
                                            unselectedIconColor = TextMutedDark,
                                            unselectedTextColor = TextMutedDark,
                                            indicatorColor = ElectricBlue.copy(alpha = 0.14f)
                                        )
                                    )

                                    NavigationBarItem(
                                        selected = selectedTab == 1,
                                        onClick = { selectedTab = 1 },
                                        icon = {
                                            Icon(
                                                imageVector = Icons.Default.Terminal,
                                                contentDescription = "Sessions"
                                            )
                                        },
                                        label = {
                                            Text(
                                                text = "Sessions",
                                                fontSize = 11.sp,
                                                fontWeight = if (selectedTab == 1) FontWeight.SemiBold else FontWeight.Normal
                                            )
                                        },
                                        colors = NavigationBarItemDefaults.colors(
                                            selectedIconColor = ElectricBlueSoft,
                                            selectedTextColor = ElectricBlueSoft,
                                            unselectedIconColor = TextMutedDark,
                                            unselectedTextColor = TextMutedDark,
                                            indicatorColor = ElectricBlue.copy(alpha = 0.14f)
                                        )
                                    )

                                    NavigationBarItem(
                                        selected = selectedTab == 2,
                                        onClick = { selectedTab = 2 },
                                        icon = {
                                            Icon(
                                                imageVector = Icons.Default.Shield,
                                                contentDescription = "Alerts"
                                            )
                                        },
                                        label = {
                                            Text(
                                                text = "Alerts",
                                                fontSize = 11.sp,
                                                fontWeight = if (selectedTab == 2) FontWeight.SemiBold else FontWeight.Normal
                                            )
                                        },
                                        colors = NavigationBarItemDefaults.colors(
                                            selectedIconColor = ElectricBlueSoft,
                                            selectedTextColor = ElectricBlueSoft,
                                            unselectedIconColor = TextMutedDark,
                                            unselectedTextColor = TextMutedDark,
                                            indicatorColor = ElectricBlue.copy(alpha = 0.14f)
                                        )
                                    )

                                    NavigationBarItem(
                                        selected = selectedTab == 3,
                                        onClick = { selectedTab = 3 },
                                        icon = {
                                            Icon(
                                                imageVector = Icons.Default.SmartToy,
                                                contentDescription = "Copilot"
                                            )
                                        },
                                        label = {
                                            Text(
                                                text = "Copilot",
                                                fontSize = 11.sp,
                                                fontWeight = if (selectedTab == 3) FontWeight.SemiBold else FontWeight.Normal
                                            )
                                        },
                                        colors = NavigationBarItemDefaults.colors(
                                            selectedIconColor = ElectricBlueSoft,
                                            selectedTextColor = ElectricBlueSoft,
                                            unselectedIconColor = TextMutedDark,
                                            unselectedTextColor = TextMutedDark,
                                            indicatorColor = ElectricBlue.copy(alpha = 0.14f)
                                        )
                                    )

                                    NavigationBarItem(
                                        selected = selectedTab == 4,
                                        onClick = { selectedTab = 4 },
                                        icon = {
                                            Icon(
                                                imageVector = Icons.Default.Settings,
                                                contentDescription = "Settings"
                                            )
                                        },
                                        label = {
                                            Text(
                                                text = "Settings",
                                                fontSize = 11.sp,
                                                fontWeight = if (selectedTab == 4) FontWeight.SemiBold else FontWeight.Normal
                                            )
                                        },
                                        colors = NavigationBarItemDefaults.colors(
                                            selectedIconColor = ElectricBlueSoft,
                                            selectedTextColor = ElectricBlueSoft,
                                            unselectedIconColor = TextMutedDark,
                                            unselectedTextColor = TextMutedDark,
                                            indicatorColor = ElectricBlue.copy(alpha = 0.14f)
                                        )
                                    )
                                }
                            }
                        }
                    ) { innerPadding ->
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(innerPadding)
                        ) {
                            when (selectedTab) {
                                0 -> {
                                    WarRoomScreen(
                                        stats = stats,
                                        sessions = sessions,
                                        isRefreshing = isRefreshing,
                                        isSensorReachable = isSensorReachable,
                                        onRefresh = {
                                            scope.launch {
                                                isRefreshing = true
                                                repo.syncDashboardStats()
                                                repo.syncSessions()
                                                isRefreshing = false
                                            }
                                        },
                                        onToggleExposure = { enabled ->
                                            scope.launch {
                                                repo.toggleExposure(enabled).onFailure { error ->
                                                    Toast.makeText(
                                                        this@MainActivity,
                                                        error.message ?: "Exposure toggle failed",
                                                        Toast.LENGTH_LONG
                                                    ).show()
                                                }
                                            }
                                        },
                                        onBlockIp = { ip, ttl ->
                                            scope.launch {
                                                repo.blockIp(ip, ttl)
                                                    .onSuccess { Toast.makeText(this@MainActivity, "Blocked $ip", Toast.LENGTH_SHORT).show() }
                                                    .onFailure { Toast.makeText(this@MainActivity, it.message ?: "Block failed", Toast.LENGTH_LONG).show() }
                                            }
                                        }
                                    )
                                }

                                1 -> {
                                    SessionsScreen(
                                        sessions = sessions,
                                        isRefreshing = isRefreshing,
                                        isSensorReachable = isSensorReachable,
                                        onRefresh = {
                                            scope.launch {
                                                isRefreshing = true
                                                repo.syncSessions()
                                                isRefreshing = false
                                            }
                                        },
                                        onSelectSession = { s ->
                                            inspectingSession = s
                                        }
                                    )
                                }

                                2 -> {
                                    AlertFeedScreen(
                                        alerts = alerts,
                                        isRefreshing = isRefreshing,
                                        isSensorReachable = isSensorReachable,
                                        onRefresh = {
                                            scope.launch {
                                                isRefreshing = true
                                                repo.syncAlerts()
                                                isRefreshing = false
                                            }
                                        },
                                        onBlockIp = { ip ->
                                            scope.launch {
                                                repo.blockIp(ip)
                                                    .onSuccess { Toast.makeText(this@MainActivity, "Blocked $ip", Toast.LENGTH_SHORT).show() }
                                                    .onFailure { Toast.makeText(this@MainActivity, it.message ?: "Block failed", Toast.LENGTH_LONG).show() }
                                            }
                                        },
                                        onInspectAlert = { alert ->
                                            inspectingSession = MobileSessionItem(
                                                id = alert.id,
                                                ip = alert.ip,
                                                country = alert.country,
                                                risk_score = alert.riskScore,
                                                mitre_techniques = listOfNotNull(alert.mitreId.takeIf { it.isNotBlank() }),
                                                commands = emptyList(),
                                                blocked = alert.blocked,
                                                timestamp_ms = alert.timestampMs
                                            )
                                        },
                                        onOpenSettings = { selectedTab = 4 }
                                    )
                                }

                                3 -> {
                                    AiCopilotScreen(
                                        messages = copilotMessages,
                                        onSendMessage = { prompt ->
                                            scope.launch {
                                                repo.askCopilot(prompt)
                                            }
                                        }
                                    )
                                }

                                4 -> {
                                    MobileSettingsScreen(
                                        session = session!!,
                                        stats = stats,
                                        themeMode = themeMode,
                                        onThemeModeChange = { mode ->
                                            themePreference.mode = mode
                                            themeMode = mode
                                        },
                                        onUpdatePolicy = { newPolicy ->
                                            scope.launch {
                                                repo.updateAlertPolicy(newPolicy)
                                            }
                                        },
                                        onUpdateRuntimeControls = { deception, dryRun, hassh ->
                                            scope.launch {
                                                repo.updateRuntimeControls(deception, dryRun, hassh)
                                            }
                                        },
                                        onBack = { selectedTab = 0 },
                                        onUnpair = {
                                            repo.clearSession()
                                            session = null
                                            selectedTab = 0
                                        }
                                    )
                                }
                            }
                        }

                        // Keystroke Forensics & SOAR Quarantine Bottom Sheet
                        inspectingSession?.let { inspected ->
                            SessionInspectorSheet(
                                session = inspected,
                                sheetState = sheetState,
                                onDismiss = { inspectingSession = null },
                                onBlockIp = { ip, ttl ->
                                    scope.launch {
                                        repo.blockIp(ip, ttl)
                                            .onSuccess { Toast.makeText(this@MainActivity, "Blocked $ip", Toast.LENGTH_SHORT).show() }
                                            .onFailure { Toast.makeText(this@MainActivity, it.message ?: "Block failed", Toast.LENGTH_LONG).show() }
                                    }
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}
