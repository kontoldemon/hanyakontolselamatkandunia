package com.cloudsentinel.mobile.ui.warroom

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.VerticalDivider
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Block
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.cloudsentinel.mobile.R
import com.cloudsentinel.mobile.core.network.ClusterStatsResponse
import com.cloudsentinel.mobile.core.network.MobileSessionItem
import com.cloudsentinel.mobile.core.theme.AmberWarning
import com.cloudsentinel.mobile.core.theme.ElectricBlueSoft
import com.cloudsentinel.mobile.core.theme.EmeraldLive
import com.cloudsentinel.mobile.core.theme.ObsidianBg
import com.cloudsentinel.mobile.core.theme.ObsidianBorder
import com.cloudsentinel.mobile.core.theme.ObsidianCard
import com.cloudsentinel.mobile.core.theme.ObsidianSurfaceElevated
import com.cloudsentinel.mobile.core.theme.RoseCritical
import com.cloudsentinel.mobile.core.theme.TextMutedDark
import com.cloudsentinel.mobile.core.theme.TextPrimaryDark

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WarRoomScreen(
    stats: ClusterStatsResponse?,
    sessions: List<MobileSessionItem>,
    isRefreshing: Boolean,
    isSensorReachable: Boolean?,
    onRefresh: () -> Unit,
    onToggleExposure: (Boolean) -> Unit,
    onSelectSession: (MobileSessionItem) -> Unit,
    onBlockIp: (String, Long?) -> Unit = { _, _ -> }
) {
    var showKillswitchConfirm by remember { mutableStateOf(false) }
    var showBlockedSheet by remember { mutableStateOf(false) }
    val exposureEnabled = stats?.ingress_exposure?.enabled ?: true
    val haptic = LocalHapticFeedback.current
    val clipboard = LocalClipboardManager.current
    val blockedSheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    Scaffold(
        containerColor = ObsidianBg,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = ObsidianBg
                ),
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Image(
                            painter = painterResource(id = R.drawable.ic_shield_logo),
                            contentDescription = "CloudSentinel",
                            modifier = Modifier.size(28.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = "War Room",
                            style = MaterialTheme.typography.titleLarge.copy(
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 20.sp,
                                letterSpacing = (-0.3).sp
                            ),
                            color = TextPrimaryDark
                        )
                    }
                },
                actions = {
                    IconButton(onClick = onRefresh) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Refresh telemetry",
                            tint = TextMutedDark,
                            modifier = Modifier.size(22.dp)
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
        ) {
            AnimatedVisibility(visible = isSensorReachable == false) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp, vertical = 6.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(AmberWarning.copy(alpha = 0.12f))
                        .padding(horizontal = 14.dp, vertical = 9.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(7.dp)
                            .clip(CircleShape)
                            .background(AmberWarning)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Sensor unreachable · Waiting to reconnect",
                        style = MaterialTheme.typography.bodySmall,
                        color = AmberWarning,
                        fontSize = 12.sp
                    )
                }
            }

            PullToRefreshBox(
                isRefreshing = isRefreshing,
                onRefresh = onRefresh,
                modifier = Modifier.weight(1f).fillMaxWidth()
            ) {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(20.dp)
                ) {
            // 1. Primary Ingress Control Card (Clean, calm, authoritative)
            item {
                Surface(
                    shape = RoundedCornerShape(20.dp),
                    color = ObsidianCard,
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, ObsidianBorder, RoundedCornerShape(20.dp))
                ) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Box(
                                        modifier = Modifier
                                            .size(8.dp)
                                            .clip(CircleShape)
                                            .background(if (exposureEnabled) EmeraldLive else RoseCritical)
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        text = if (exposureEnabled) "Ingress Active" else "Ingress Paused",
                                        style = MaterialTheme.typography.labelMedium.copy(
                                            fontWeight = FontWeight.Medium
                                        ),
                                        color = if (exposureEnabled) EmeraldLive else RoseCritical
                                    )
                                }
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = "Honeypot Port 2222",
                                    style = MaterialTheme.typography.titleMedium.copy(
                                        fontWeight = FontWeight.SemiBold,
                                        fontSize = 17.sp
                                    ),
                                    color = TextPrimaryDark
                                )
                            }

                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = if (exposureEnabled) RoseCritical.copy(alpha = 0.14f) else EmeraldLive.copy(alpha = 0.14f),
                                modifier = Modifier
                                    .clip(RoundedCornerShape(12.dp))
                                    .clickable { showKillswitchConfirm = true }
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.PowerSettingsNew,
                                        contentDescription = null,
                                        tint = if (exposureEnabled) RoseCritical else EmeraldLive,
                                        modifier = Modifier.size(16.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        text = if (exposureEnabled) "Pause" else "Resume",
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        color = if (exposureEnabled) RoseCritical else EmeraldLive
                                    )
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(16.dp))
                        HorizontalDivider(color = ObsidianBorder, thickness = 1.dp)
                        Spacer(modifier = Modifier.height(12.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = stats?.ingress_exposure?.provider ?: "iptables",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMutedDark
                            )
                            Text(
                                text = "0.0.0.0:2222",
                                style = MaterialTheme.typography.bodySmall.copy(
                                    fontFamily = FontFamily.Monospace
                                ),
                                color = TextMutedDark
                            )
                        }
                    }
                }
            }

            // 2. Compact Unified 2x2 Overview Strip (Minimalist, space-efficient)
            item {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "Overview",
                        style = MaterialTheme.typography.titleSmall.copy(
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 13.sp
                        ),
                        color = TextMutedDark,
                        modifier = Modifier.padding(start = 2.dp)
                    )

                    Surface(
                        shape = RoundedCornerShape(18.dp),
                        color = ObsidianCard,
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, ObsidianBorder, RoundedCornerShape(18.dp))
                    ) {
                        Column(modifier = Modifier.fillMaxWidth()) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(IntrinsicSize.Min)
                            ) {
                                CompactMetricCell(
                                    label = "Events",
                                    value = "${stats?.connections ?: 0}",
                                    modifier = Modifier.weight(1f)
                                )
                                VerticalDivider(
                                    color = ObsidianBorder,
                                    thickness = 1.dp,
                                    modifier = Modifier.fillMaxHeight()
                                )
                                CompactMetricCell(
                                    label = "Avg MTTB",
                                    value = stats?.mttb_seconds?.let { "${it}s" } ?: "--",
                                    modifier = Modifier.weight(1f)
                                )
                            }

                            HorizontalDivider(color = ObsidianBorder, thickness = 1.dp)

                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(IntrinsicSize.Min)
                            ) {
                                CompactMetricCell(
                                    label = "MITRE Hits",
                                    value = "${stats?.mitre_count ?: 0}",
                                    modifier = Modifier.weight(1f)
                                )
                                VerticalDivider(
                                    color = ObsidianBorder,
                                    thickness = 1.dp,
                                    modifier = Modifier.fillMaxHeight()
                                )
                                CompactMetricCell(
                                    label = "Blocked IPs",
                                    value = "${stats?.blocked_ips_count ?: 0}",
                                    accent = if ((stats?.blocked_ips_count ?: 0) > 0) RoseCritical else TextPrimaryDark,
                                    hint = "Manage",
                                    modifier = Modifier
                                        .weight(1f)
                                        .clickable { showBlockedSheet = true }
                                )
                            }
                        }
                    }
                }
            }

            // 3. Sensor Health Summary (Clean Grouped Key-Value Rows)
            item {
                Surface(
                    shape = RoundedCornerShape(20.dp),
                    color = ObsidianCard,
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, ObsidianBorder, RoundedCornerShape(20.dp))
                ) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        Text(
                            text = "Sensor Health",
                            style = MaterialTheme.typography.titleSmall.copy(
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 15.sp
                            ),
                            color = TextPrimaryDark
                        )

                        Spacer(modifier = Modifier.height(14.dp))

                        HealthRow(
                            label = "Status",
                            value = stats?.sensor_status ?: "Online",
                            valueColor = EmeraldLive
                        )
                        HorizontalDivider(
                            color = ObsidianBorder,
                            modifier = Modifier.padding(vertical = 12.dp)
                        )
                        HealthRow(
                            label = "Uptime",
                            value = formatUptime(stats?.sensor_uptime_seconds ?: 0L)
                        )
                        HorizontalDivider(
                            color = ObsidianBorder,
                            modifier = Modifier.padding(vertical = 12.dp)
                        )
                        HealthRow(
                            label = "Top Origin",
                            value = stats?.top_threat_origin ?: "None detected"
                        )
                        HorizontalDivider(
                            color = ObsidianBorder,
                            modifier = Modifier.padding(vertical = 12.dp)
                        )
                        val deceptionLabel = (stats?.deception_level ?: "full").replaceFirstChar { it.uppercase() }
                        val soarLabel = if (stats?.soar_dry_run == true) "Dry Run" else "Live"
                        HealthRow(
                            label = "Defense Mode",
                            value = "$deceptionLabel · SOAR $soarLabel"
                        )
                    }
                }
            }

            // 4. Active Threat Sessions
            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 2.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Active Sessions",
                        style = MaterialTheme.typography.titleSmall.copy(
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 14.sp
                        ),
                        color = TextMutedDark
                    )
                    if (sessions.isNotEmpty()) {
                        Text(
                            text = "Tap to inspect",
                            style = MaterialTheme.typography.labelSmall,
                            color = ElectricBlueSoft
                        )
                    }
                }
            }

            if (sessions.isEmpty()) {
                item {
                    Surface(
                        shape = RoundedCornerShape(20.dp),
                        color = ObsidianCard,
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, ObsidianBorder, RoundedCornerShape(20.dp))
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 24.dp, vertical = 28.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Text(
                                text = "No active threat sessions",
                                style = MaterialTheme.typography.bodyMedium.copy(
                                    fontWeight = FontWeight.Medium
                                ),
                                color = TextPrimaryDark,
                                textAlign = TextAlign.Center
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "Captured SSH and honeypot sessions will appear here in real time.",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMutedDark,
                                textAlign = TextAlign.Center,
                                lineHeight = 18.sp
                            )
                        }
                    }
                }
            } else {
                items(sessions.size) { idx ->
                    val session = sessions[idx]
                    SessionQuickCard(
                        session = session,
                        onClick = { onSelectSession(session) }
                    )
                }
            }

            item { Spacer(modifier = Modifier.height(8.dp)) }
        }
            }
        }
    }

    if (showKillswitchConfirm) {
        AlertDialog(
            onDismissRequest = { showKillswitchConfirm = false },
            containerColor = ObsidianSurfaceElevated,
            icon = {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = null,
                    tint = if (exposureEnabled) RoseCritical else EmeraldLive,
                    modifier = Modifier.size(28.dp)
                )
            },
            title = {
                Text(
                    text = if (exposureEnabled) "Pause Honeypot Ingress?" else "Resume Honeypot Ingress?",
                    color = TextPrimaryDark,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 18.sp
                )
            },
            text = {
                Text(
                    text = if (exposureEnabled) {
                        "Incoming traffic on port 2222 will be blocked on the sensor host firewall. The sensor daemon remains running."
                    } else {
                        "Port 2222 will be re-opened to capture incoming threat traffic."
                    },
                    color = TextMutedDark,
                    fontSize = 14.sp,
                    lineHeight = 20.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        showKillswitchConfirm = false
                        onToggleExposure(!exposureEnabled)
                    },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (exposureEnabled) RoseCritical else EmeraldLive
                    ),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text(
                        text = if (exposureEnabled) "Pause Ingress" else "Resume Ingress",
                        fontWeight = FontWeight.SemiBold,
                        color = Color.White
                    )
                }
            },
            dismissButton = {
                TextButton(onClick = { showKillswitchConfirm = false }) {
                    Text(text = "Cancel", color = TextMutedDark)
                }
            }
        )
    }

    // Blocked IPs & Manual Quarantine Bottom Sheet
    if (showBlockedSheet) {
        var manualIp by remember { mutableStateOf("") }
        var selectedTtl by remember { mutableStateOf<Long?>(3600L) }
        val blockedList = stats?.blocked_ips.orEmpty()

        ModalBottomSheet(
            onDismissRequest = { showBlockedSheet = false },
            sheetState = blockedSheetState,
            containerColor = ObsidianCard,
            dragHandle = null
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Blocked IPs (${blockedList.size})",
                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold),
                        color = TextPrimaryDark
                    )
                    IconButton(onClick = { showBlockedSheet = false }) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close",
                            tint = TextMutedDark
                        )
                    }
                }

                // Manual IP Block Form
                OutlinedTextField(
                    value = manualIp,
                    onValueChange = { manualIp = it.trim() },
                    placeholder = { Text("Enter public IPv4 (e.g. 45.155.205.14)", fontSize = 13.sp, color = TextMutedDark) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = ObsidianBg,
                        unfocusedContainerColor = ObsidianBg,
                        focusedBorderColor = ElectricBlueSoft,
                        unfocusedBorderColor = ObsidianBorder,
                        focusedTextColor = TextPrimaryDark,
                        unfocusedTextColor = TextPrimaryDark
                    )
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    listOf(3600L to "1h", 86400L to "24h", null to "Permanent").forEach { (ttl, label) ->
                        val active = selectedTtl == ttl
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(10.dp))
                                .background(if (active) RoseCritical.copy(alpha = 0.16f) else ObsidianBg)
                                .border(1.dp, if (active) RoseCritical else ObsidianBorder, RoundedCornerShape(10.dp))
                                .clickable { selectedTtl = ttl }
                                .padding(vertical = 8.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = label,
                                fontSize = 12.sp,
                                fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                                color = if (active) RoseCritical else TextMutedDark
                            )
                        }
                    }
                }

                Button(
                    onClick = {
                        if (manualIp.isNotBlank()) {
                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                            onBlockIp(manualIp, selectedTtl)
                            manualIp = ""
                        }
                    },
                    enabled = manualIp.isNotBlank(),
                    modifier = Modifier.fillMaxWidth().height(46.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = RoseCritical)
                ) {
                    Icon(
                        imageVector = Icons.Default.Block,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(text = "Quarantine IP", fontWeight = FontWeight.SemiBold, color = Color.White)
                }

                HorizontalDivider(color = ObsidianBorder)

                if (blockedList.isEmpty()) {
                    Text(
                        text = "No IPs currently quarantined.",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMutedDark,
                        modifier = Modifier.padding(vertical = 12.dp)
                    )
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        blockedList.take(12).forEach { ip ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(12.dp))
                                    .background(ObsidianBg)
                                    .border(1.dp, ObsidianBorder, RoundedCornerShape(12.dp))
                                    .clickable {
                                        clipboard.setText(AnnotatedString(ip))
                                        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                    }
                                    .padding(horizontal = 14.dp, vertical = 11.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = ip,
                                    style = MaterialTheme.typography.bodyMedium.copy(
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Medium
                                    ),
                                    color = TextPrimaryDark
                                )
                                Icon(
                                    imageVector = Icons.Default.ContentCopy,
                                    contentDescription = "Copy IP",
                                    tint = TextMutedDark,
                                    modifier = Modifier.size(15.dp)
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))
            }
        }
    }
}

private fun formatUptime(totalSeconds: Long): String {
    if (totalSeconds <= 0L) return "--"
    val days = totalSeconds / 86400
    val hours = (totalSeconds % 86400) / 3600
    val mins = (totalSeconds % 3600) / 60
    return when {
        days > 0 -> "${days}d ${hours}h"
        hours > 0 -> "${hours}h ${mins}m"
        else -> "${mins}m"
    }
}

@Composable
private fun CompactMetricCell(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    accent: Color = TextPrimaryDark,
    hint: String? = null
) {
    Column(
        modifier = modifier.padding(horizontal = 16.dp, vertical = 12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = TextMutedDark,
                fontSize = 11.sp
            )
            if (hint != null) {
                Text(
                    text = hint,
                    style = MaterialTheme.typography.labelSmall,
                    color = ElectricBlueSoft,
                    fontSize = 10.sp
                )
            }
        }
        Spacer(modifier = Modifier.height(3.dp))
        Text(
            text = value,
            style = MaterialTheme.typography.titleLarge.copy(
                fontWeight = FontWeight.SemiBold,
                fontSize = 20.sp,
                letterSpacing = (-0.4).sp
            ),
            color = accent
        )
    }
}

@Composable
private fun HealthRow(
    label: String,
    value: String,
    valueColor: Color = TextPrimaryDark
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = TextMutedDark,
            fontSize = 13.sp
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium.copy(
                fontWeight = FontWeight.Medium
            ),
            color = valueColor,
            fontSize = 13.sp
        )
    }
}

@Composable
private fun SessionQuickCard(
    session: MobileSessionItem,
    onClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = ObsidianCard,
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, ObsidianBorder, RoundedCornerShape(16.dp))
            .clip(RoundedCornerShape(16.dp))
            .clickable(onClick = onClick)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 18.dp, vertical = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = session.ip,
                        style = MaterialTheme.typography.bodyMedium.copy(
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.SemiBold
                        ),
                        color = TextPrimaryDark
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = session.country,
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMutedDark
                    )
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = if (session.commands.isNotEmpty()) "${session.commands.size} commands recorded" else "Credential probe",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMutedDark,
                    fontSize = 12.sp
                )
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                val riskColor = when {
                    session.risk_score >= 90 -> RoseCritical
                    session.risk_score >= 70 -> AmberWarning
                    else -> ElectricBlueSoft
                }
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(riskColor.copy(alpha = 0.14f))
                        .padding(horizontal = 10.dp, vertical = 5.dp)
                ) {
                    Text(
                        text = "${session.risk_score}",
                        style = MaterialTheme.typography.labelSmall.copy(
                            fontWeight = FontWeight.SemiBold,
                            fontFamily = FontFamily.Monospace
                        ),
                        color = riskColor
                    )
                }

                if (session.blocked) {
                    Spacer(modifier = Modifier.width(8.dp))
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .background(RoseCritical.copy(alpha = 0.18f))
                            .padding(horizontal = 8.dp, vertical = 5.dp)
                    ) {
                        Text(
                            text = "Blocked",
                            style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.SemiBold),
                            color = RoseCritical,
                            fontSize = 10.sp
                        )
                    }
                }
            }
        }
    }
}
