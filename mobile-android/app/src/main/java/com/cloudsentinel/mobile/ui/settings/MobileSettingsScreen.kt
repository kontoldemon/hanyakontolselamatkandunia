package com.cloudsentinel.mobile.ui.settings

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.platform.LocalContext
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Smartphone
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.cloudsentinel.mobile.R
import com.cloudsentinel.mobile.core.network.ClusterStatsResponse
import com.cloudsentinel.mobile.core.network.MobileAlertPolicyInfo
import com.cloudsentinel.mobile.core.security.PairedSession
import com.cloudsentinel.mobile.core.theme.ElectricBlue
import com.cloudsentinel.mobile.core.theme.ElectricBlueSoft
import com.cloudsentinel.mobile.core.theme.EmeraldLive
import com.cloudsentinel.mobile.core.theme.ObsidianBg
import com.cloudsentinel.mobile.core.theme.ObsidianBorder
import com.cloudsentinel.mobile.core.theme.ObsidianCard
import com.cloudsentinel.mobile.core.theme.ObsidianSurfaceElevated
import com.cloudsentinel.mobile.core.theme.RoseCritical
import com.cloudsentinel.mobile.core.theme.TextMutedDark
import com.cloudsentinel.mobile.core.theme.TextPrimaryDark
import com.cloudsentinel.mobile.core.theme.ThemeMode
import kotlin.math.roundToInt

private val COOLDOWN_OPTIONS = listOf(
    0 to "0s",
    30 to "30s",
    60 to "1m",
    300 to "5m"
)

private enum class SettingsSheet {
    ALERT_POLICY,
    SENSOR_DEFENSE,
    GATEWAY
}

private fun Context.findActivity(): Activity? {
    var current: Context = this
    while (current is ContextWrapper) {
        if (current is Activity) return current
        current = current.baseContext
    }
    return null
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MobileSettingsScreen(
    session: PairedSession,
    stats: ClusterStatsResponse? = null,
    themeMode: ThemeMode = ThemeMode.LIGHT,
    onThemeModeChange: (ThemeMode) -> Unit = {},
    onUpdatePolicy: (MobileAlertPolicyInfo) -> Unit = {},
    onUpdateRuntimeControls: (String?, Boolean?, String?) -> Unit = { _, _, _ -> },
    onBack: () -> Unit,
    onUnpair: () -> Unit
) {
    var showUnpairConfirm by remember { mutableStateOf(false) }
    var activeSheet by remember { mutableStateOf<SettingsSheet?>(null) }
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val haptic = LocalHapticFeedback.current

    val policy = stats?.alert_policy ?: MobileAlertPolicyInfo()
    val currentDeception = (stats?.deception_level ?: "full").lowercase()
    val currentDryRun = stats?.soar_dry_run ?: false
    val currentHassh = (stats?.hassh_action ?: "monitor").lowercase()

    val cooldownLabel = COOLDOWN_OPTIONS.firstOrNull { it.first == policy.cooldownSeconds }?.second
        ?: "${policy.cooldownSeconds}s"
    val alertSummary = if (policy.enabled) {
        "Active · Risk >= ${policy.minRiskScore} · $cooldownLabel cooldown"
    } else {
        "Paused · Risk >= ${policy.minRiskScore}"
    }
    val defenseSummary = "${currentDeception.replaceFirstChar { it.uppercase() }} · " +
        "${if (currentDryRun) "SOAR Dry Run" else "SOAR Live"} · " +
        "HASSH ${if (currentHassh == "drop") "Drop" else "Monitor"}"
    val gatewayHost = session.serverUrl.removePrefix("https://").removePrefix("http://")

    Scaffold(
        containerColor = ObsidianBg,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(containerColor = ObsidianBg),
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Image(
                            painter = painterResource(id = R.drawable.ic_shield_logo),
                            contentDescription = "CloudSentinel",
                            modifier = Modifier.size(28.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = "Settings",
                            style = MaterialTheme.typography.titleLarge.copy(
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 20.sp,
                                letterSpacing = (-0.3).sp
                            ),
                            color = TextPrimaryDark
                        )
                    }
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp)
        ) {
            // 1. Device Identity Card
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = ObsidianCard,
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, ObsidianBorder, RoundedCornerShape(20.dp))
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(18.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(46.dp)
                            .clip(CircleShape)
                            .background(ElectricBlue.copy(alpha = 0.14f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Smartphone,
                            contentDescription = null,
                            tint = ElectricBlueSoft,
                            modifier = Modifier.size(22.dp)
                        )
                    }

                    Spacer(modifier = Modifier.width(14.dp))

                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = session.deviceName,
                            style = MaterialTheme.typography.titleSmall.copy(
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 15.sp
                            ),
                            color = TextPrimaryDark
                        )
                        Spacer(modifier = Modifier.height(3.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(7.dp)
                                    .clip(CircleShape)
                                    .background(EmeraldLive)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "Connected",
                                style = MaterialTheme.typography.bodySmall,
                                color = EmeraldLive,
                                fontSize = 12.sp
                            )
                        }
                    }
                }
            }

            // 2. Clean Drill-Down Settings Menu (fits calmly on one screen)
            SettingsGroup(title = "Preferences & Controls") {
                SettingsMenuRow(
                    icon = Icons.Default.NotificationsActive,
                    title = "Alert Policy",
                    subtitle = alertSummary,
                    onClick = { activeSheet = SettingsSheet.ALERT_POLICY }
                )
                SettingsDivider()
                SettingsMenuRow(
                    icon = Icons.Default.Shield,
                    title = "Sensor Defense",
                    subtitle = defenseSummary,
                    onClick = { activeSheet = SettingsSheet.SENSOR_DEFENSE }
                )
                SettingsDivider()
                SettingsMenuRow(
                    icon = Icons.Default.Link,
                    title = "Gateway & Connection",
                    subtitle = "$gatewayHost · Port 22 → ${stats?.ingress_exposure?.port ?: 2222}",
                    onClick = { activeSheet = SettingsSheet.GATEWAY }
                )
            }

            // 3. Appearance
            SettingsGroup(title = "Appearance") {
                var showThemeMenu by remember { mutableStateOf(false) }
                Box(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                showThemeMenu = true
                            }
                            .padding(horizontal = 16.dp, vertical = 15.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "Theme",
                                style = MaterialTheme.typography.bodyMedium.copy(
                                    fontWeight = FontWeight.Medium
                                ),
                                color = TextPrimaryDark,
                                fontSize = 14.sp
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = themeMode.label,
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMutedDark,
                                fontSize = 12.sp
                            )
                        }
                        Icon(
                            imageVector = Icons.Default.KeyboardArrowDown,
                            contentDescription = "Select theme",
                            tint = TextMutedDark
                        )
                    }
                    DropdownMenu(
                        expanded = showThemeMenu,
                        onDismissRequest = { showThemeMenu = false }
                    ) {
                        ThemeMode.entries.forEach { mode ->
                            DropdownMenuItem(
                                text = {
                                    Text(
                                        text = mode.label,
                                        color = if (themeMode == mode) ElectricBlueSoft else TextPrimaryDark
                                    )
                                },
                                onClick = {
                                    showThemeMenu = false
                                    onThemeModeChange(mode)
                                },
                                trailingIcon = {
                                    if (themeMode == mode) {
                                        Icon(
                                            imageVector = Icons.Default.Check,
                                            contentDescription = null,
                                            tint = ElectricBlueSoft
                                        )
                                    }
                                }
                            )
                        }
                    }
                }
            }

            // 4. About
            SettingsGroup(title = "About") {
                SettingsInfoRow(
                    icon = Icons.Default.Info,
                    title = "CloudSentinel Mobile",
                    subtitle = "Version 1.0.0"
                )
            }

            // 5. Unlink Device
            OutlinedButton(
                onClick = { showUnpairConfirm = true },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                shape = RoundedCornerShape(14.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, RoseCritical.copy(alpha = 0.4f)),
                colors = ButtonDefaults.outlinedButtonColors(
                    containerColor = RoseCritical.copy(alpha = 0.08f)
                )
            ) {
                Text(
                    text = "Unlink Device",
                    color = RoseCritical,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 14.sp
                )
            }
        }
    }

    // Bottom Sheets for each Settings section
    activeSheet?.let { sheet ->
        ModalBottomSheet(
            onDismissRequest = { activeSheet = null },
            sheetState = sheetState,
            containerColor = ObsidianCard,
            contentWindowInsets = { WindowInsets(0) },
            dragHandle = null
        ) {
            val context = LocalContext.current
            DisposableEffect(Unit) {
                val window = context.findActivity()?.window
                val controller = window?.let { WindowCompat.getInsetsController(it, it.decorView) }
                controller?.systemBarsBehavior =
                    WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                controller?.hide(WindowInsetsCompat.Type.navigationBars())
                onDispose {
                    controller?.show(WindowInsetsCompat.Type.navigationBars())
                }
            }
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .navigationBarsPadding()
                    .padding(horizontal = 20.dp, vertical = 20.dp)
            ) {
                val sheetTitle = when (sheet) {
                    SettingsSheet.ALERT_POLICY -> "Alert Policy"
                    SettingsSheet.SENSOR_DEFENSE -> "Sensor Defense"
                    SettingsSheet.GATEWAY -> "Gateway & Connection"
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = sheetTitle,
                        style = MaterialTheme.typography.titleMedium.copy(
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 18.sp
                        ),
                        color = TextPrimaryDark
                    )
                    IconButton(onClick = { activeSheet = null }) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close",
                            tint = TextMutedDark
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                when (sheet) {
                    SettingsSheet.ALERT_POLICY -> {
                        var sliderRisk by remember { mutableFloatStateOf(policy.minRiskScore.toFloat()) }
                        LaunchedEffect(policy.minRiskScore) {
                            sliderRisk = policy.minRiskScore.toFloat()
                        }

                        PolicyToggleRow(
                            title = "Push Notifications",
                            subtitle = "Real-time threat alerts to this phone",
                            checked = policy.enabled,
                            onCheckedChange = { checked ->
                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                onUpdatePolicy(policy.copy(enabled = checked))
                            }
                        )

                        HorizontalDivider(color = ObsidianBorder, modifier = Modifier.padding(vertical = 8.dp))

                        // Min Risk Slider
                        Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = "Minimum Risk Score",
                                        style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
                                        color = TextPrimaryDark,
                                        fontSize = 14.sp
                                    )
                                    Text(
                                        text = "Silence events below this threshold",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextMutedDark,
                                        fontSize = 12.sp
                                    )
                                }
                                Text(
                                    text = "${sliderRisk.roundToInt()}/100",
                                    style = MaterialTheme.typography.labelLarge.copy(
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.SemiBold
                                    ),
                                    color = RoseCritical
                                )
                            }
                            Spacer(modifier = Modifier.height(6.dp))
                            Slider(
                                value = sliderRisk,
                                onValueChange = { sliderRisk = (it / 5f).roundToInt() * 5f },
                                onValueChangeFinished = {
                                    val snapped = sliderRisk.roundToInt().coerceIn(0, 100)
                                    haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                    onUpdatePolicy(policy.copy(minRiskScore = snapped))
                                },
                                valueRange = 0f..100f,
                                steps = 19,
                                colors = SliderDefaults.colors(
                                    thumbColor = Color.White,
                                    activeTrackColor = RoseCritical,
                                    inactiveTrackColor = ObsidianSurfaceElevated
                                )
                            )
                        }

                        HorizontalDivider(color = ObsidianBorder, modifier = Modifier.padding(vertical = 8.dp))

                        // Cooldown
                        Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                            Text(
                                text = "Per-IP Alert Cooldown",
                                style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
                                color = TextPrimaryDark,
                                fontSize = 14.sp
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = "Prevent repeated alerts from the same IP",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMutedDark,
                                fontSize = 12.sp
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                COOLDOWN_OPTIONS.forEach { (seconds, label) ->
                                    val selected = policy.cooldownSeconds == seconds
                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .clip(RoundedCornerShape(10.dp))
                                            .background(if (selected) ElectricBlue.copy(alpha = 0.18f) else ObsidianBg)
                                            .border(1.dp, if (selected) ElectricBlueSoft else ObsidianBorder, RoundedCornerShape(10.dp))
                                            .clickable {
                                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                                onUpdatePolicy(policy.copy(cooldownSeconds = seconds))
                                            }
                                            .padding(vertical = 9.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            text = label,
                                            fontFamily = FontFamily.Monospace,
                                            fontSize = 12.sp,
                                            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                                            color = if (selected) ElectricBlueSoft else TextMutedDark
                                        )
                                    }
                                }
                            }
                        }

                        HorizontalDivider(color = ObsidianBorder, modifier = Modifier.padding(vertical = 8.dp))

                        PolicyToggleRow(
                            title = "SSH Brute Force",
                            subtitle = "Repeated failed credential attempts",
                            checked = policy.notifyBruteForce,
                            onCheckedChange = {
                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                onUpdatePolicy(policy.copy(notifyBruteForce = it))
                            }
                        )
                        PolicyToggleRow(
                            title = "Command Execution",
                            subtitle = "Interactive shell commands in honeypot",
                            checked = policy.notifyCommandExec,
                            onCheckedChange = {
                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                onUpdatePolicy(policy.copy(notifyCommandExec = it))
                            }
                        )
                        PolicyToggleRow(
                            title = "SOAR Containment",
                            subtitle = "Automated Azure NSG or firewall blocks",
                            checked = policy.notifySoarBlock,
                            onCheckedChange = {
                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                onUpdatePolicy(policy.copy(notifySoarBlock = it))
                            }
                        )
                    }

                    SettingsSheet.SENSOR_DEFENSE -> {
                        // Deception Level
                        Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                            Text(
                                text = "Deception Level",
                                style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
                                color = TextPrimaryDark,
                                fontSize = 14.sp
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = "Virtual shell depth & canary exposure",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMutedDark,
                                fontSize = 12.sp
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                listOf("full" to "Full", "restricted" to "Restricted", "listener" to "Listener").forEach { (key, label) ->
                                    val selected = currentDeception == key
                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .clip(RoundedCornerShape(10.dp))
                                            .background(if (selected) ElectricBlue.copy(alpha = 0.18f) else ObsidianBg)
                                            .border(1.dp, if (selected) ElectricBlueSoft else ObsidianBorder, RoundedCornerShape(10.dp))
                                            .clickable {
                                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                                onUpdateRuntimeControls(key, null, null)
                                            }
                                            .padding(vertical = 9.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            text = label,
                                            fontSize = 12.sp,
                                            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                                            color = if (selected) ElectricBlueSoft else TextMutedDark
                                        )
                                    }
                                }
                            }
                        }

                        HorizontalDivider(color = ObsidianBorder, modifier = Modifier.padding(vertical = 10.dp))

                        PolicyToggleRow(
                            title = "SOAR Live Blocking",
                            subtitle = if (currentDryRun) "Dry-Run simulation only (no firewall drop)" else "Enforcing real Azure NSG / firewall blocks",
                            checked = !currentDryRun,
                            onCheckedChange = { liveEnabled ->
                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                onUpdateRuntimeControls(null, !liveEnabled, null)
                            }
                        )

                        HorizontalDivider(color = ObsidianBorder, modifier = Modifier.padding(vertical = 10.dp))

                        Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                            Text(
                                text = "HASSH Fingerprint Policy",
                                style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
                                color = TextPrimaryDark,
                                fontSize = 14.sp
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = "Action when known malicious SSH tools connect",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMutedDark,
                                fontSize = 12.sp
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                listOf("monitor" to "Monitor", "drop" to "Auto-Drop").forEach { (key, label) ->
                                    val selected = currentHassh == key
                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .clip(RoundedCornerShape(10.dp))
                                            .background(if (selected) ElectricBlue.copy(alpha = 0.18f) else ObsidianBg)
                                            .border(1.dp, if (selected) ElectricBlueSoft else ObsidianBorder, RoundedCornerShape(10.dp))
                                            .clickable {
                                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                                onUpdateRuntimeControls(null, null, key)
                                            }
                                            .padding(vertical = 9.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            text = label,
                                            fontSize = 12.sp,
                                            fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                                            color = if (selected) ElectricBlueSoft else TextMutedDark
                                        )
                                    }
                                }
                            }
                        }
                    }

                    SettingsSheet.GATEWAY -> {
                        SettingsInfoRow(
                            icon = Icons.Default.Link,
                            title = "Endpoint",
                            subtitle = session.serverUrl
                        )
                        HorizontalDivider(color = ObsidianBorder)
                        SettingsInfoRow(
                            icon = Icons.Default.Fingerprint,
                            title = "Device ID",
                            subtitle = session.deviceId,
                            isMono = true
                        )
                        HorizontalDivider(color = ObsidianBorder)
                        SettingsInfoRow(
                            icon = Icons.Default.Security,
                            title = "Session Token",
                            subtitle = "${session.deviceToken.take(12)}..."
                        )
                        HorizontalDivider(color = ObsidianBorder)
                        SettingsInfoRow(
                            icon = Icons.Default.PowerSettingsNew,
                            title = "Ingress Control",
                            subtitle = "Port 22 → ${stats?.ingress_exposure?.port ?: 2222} · ${stats?.ingress_exposure?.provider ?: "azure-nsg"}"
                        )
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))
            }
        }
    }

    if (showUnpairConfirm) {
        AlertDialog(
            onDismissRequest = { showUnpairConfirm = false },
            containerColor = ObsidianSurfaceElevated,
            icon = {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = null,
                    tint = RoseCritical,
                    modifier = Modifier.size(28.dp)
                )
            },
            title = {
                Text(
                    text = "Unlink this device?",
                    color = TextPrimaryDark,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 18.sp
                )
            },
            text = {
                Text(
                    text = "Your local pairing token will be cleared. Scan a new QR code from Web Settings to reconnect.",
                    color = TextMutedDark,
                    fontSize = 14.sp,
                    lineHeight = 20.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showUnpairConfirm = false
                        onUnpair()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = RoseCritical),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text(text = "Unlink", color = Color.White, fontWeight = FontWeight.SemiBold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showUnpairConfirm = false }) {
                    Text(text = "Cancel", color = TextMutedDark)
                }
            }
        )
    }
}

@Composable
private fun SettingsMenuRow(
    icon: ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 18.dp, vertical = 15.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = ElectricBlueSoft,
            modifier = Modifier.size(20.dp)
        )
        Spacer(modifier = Modifier.width(16.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
                color = TextPrimaryDark,
                fontSize = 14.sp
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = TextMutedDark,
                fontSize = 12.sp
            )
        }
        Spacer(modifier = Modifier.width(8.dp))
        Icon(
            imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
            contentDescription = null,
            tint = TextMutedDark,
            modifier = Modifier.size(20.dp)
        )
    }
}

@Composable
private fun PolicyToggleRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onCheckedChange(!checked) }
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
                color = TextPrimaryDark,
                fontSize = 14.sp
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = TextMutedDark,
                fontSize = 12.sp
            )
        }
        Spacer(modifier = Modifier.width(12.dp))
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(
                checkedThumbColor = Color.White,
                checkedTrackColor = EmeraldLive,
                uncheckedThumbColor = TextMutedDark,
                uncheckedTrackColor = ObsidianSurfaceElevated,
                uncheckedBorderColor = ObsidianBorder
            )
        )
    }
}

@Composable
private fun SettingsGroup(
    title: String,
    content: @Composable () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall.copy(
                fontWeight = FontWeight.SemiBold,
                fontSize = 13.sp
            ),
            color = TextMutedDark,
            modifier = Modifier.padding(start = 4.dp)
        )
        Surface(
            shape = RoundedCornerShape(18.dp),
            color = ObsidianCard,
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, ObsidianBorder, RoundedCornerShape(18.dp))
        ) {
            Column(modifier = Modifier.padding(vertical = 4.dp)) {
                content()
            }
        }
    }
}

@Composable
private fun SettingsInfoRow(
    icon: ImageVector,
    title: String,
    subtitle: String,
    isMono: Boolean = false
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 18.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = TextMutedDark,
            modifier = Modifier.size(20.dp)
        )
        Spacer(modifier = Modifier.width(16.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
                color = TextPrimaryDark,
                fontSize = 14.sp
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall.copy(
                    fontFamily = if (isMono) FontFamily.Monospace else FontFamily.Default
                ),
                color = TextMutedDark,
                fontSize = 12.sp
            )
        }
    }
}

@Composable
private fun SettingsDivider() {
    HorizontalDivider(
        color = ObsidianBorder,
        modifier = Modifier.padding(horizontal = 18.dp)
    )
}
