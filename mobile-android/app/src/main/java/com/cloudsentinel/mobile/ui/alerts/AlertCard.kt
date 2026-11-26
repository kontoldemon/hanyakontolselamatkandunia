package com.cloudsentinel.mobile.ui.alerts

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Block
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.cloudsentinel.mobile.core.network.ThreatAlertItem
import com.cloudsentinel.mobile.core.theme.AmberWarning
import com.cloudsentinel.mobile.core.theme.ElectricBlueSoft
import com.cloudsentinel.mobile.core.theme.EmeraldLive
import com.cloudsentinel.mobile.core.theme.RoseCritical
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun AlertCard(
    alert: ThreatAlertItem,
    nowMs: Long,
    onBlockIp: (String) -> Unit,
    onClick: (() -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    val isBrandNew = alert.timestampMs > 0 && (nowMs - alert.timestampMs) in 0..3500
    val borderColor by animateColorAsState(
        targetValue = if (isBrandNew) EmeraldLive.copy(alpha = 0.65f) else MaterialTheme.colorScheme.outline,
        animationSpec = tween(durationMillis = 450),
        label = "alertCardBorder"
    )
    val containerColor by animateColorAsState(
        targetValue = if (isBrandNew) {
            EmeraldLive.copy(alpha = 0.08f)
        } else {
            MaterialTheme.colorScheme.surface
        },
        animationSpec = tween(durationMillis = 450),
        label = "alertCardBg"
    )

    val dotColor = when {
        alert.eventType.contains("AUTH", ignoreCase = true) || alert.riskScore >= 85 -> RoseCritical
        alert.eventType.contains("COMMAND", ignoreCase = true) -> AmberWarning
        else -> ElectricBlueSoft
    }

    val timeLabel = if (alert.timestampMs > 0) {
        SimpleDateFormat("HH:mm:ss", Locale.US).format(Date(alert.timestampMs))
    } else {
        "--:--:--"
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = containerColor),
        border = BorderStroke(1.dp, borderColor)
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            // Row 1: Dot + IP + Country | Risk + Time
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.weight(1f)
                ) {
                    Box(
                        modifier = Modifier
                            .size(7.dp)
                            .clip(CircleShape)
                            .background(dotColor)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = alert.ip,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = alert.country,
                        style = MaterialTheme.typography.bodyMedium.copy(fontSize = 11.sp),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (alert.blocked) {
                        Icon(
                            imageVector = Icons.Default.Shield,
                            contentDescription = "Blocked",
                            tint = RoseCritical,
                            modifier = Modifier.size(12.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "BLOCKED",
                            style = MaterialTheme.typography.labelSmall,
                            color = RoseCritical,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                    }
                    Text(
                        text = timeLabel,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Spacer(modifier = Modifier.height(6.dp))

            // Row 2: Metadata Strip
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "RISK ${alert.riskScore}/100",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (alert.riskScore >= 80) RoseCritical else AmberWarning,
                        fontWeight = FontWeight.Bold
                    )
                    if (alert.mitreId.isNotBlank()) {
                        Text(
                            text = "  |  ${alert.mitreId}",
                            style = MaterialTheme.typography.labelSmall,
                            color = ElectricBlueSoft
                        )
                    }
                }
                Text(
                    text = alert.eventType.replace("_", " "),
                    style = MaterialTheme.typography.labelSmall,
                    color = dotColor
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Row 3: Terminal Preview Box + Quick Action
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color.Black.copy(alpha = 0.35f))
                        .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(8.dp))
                        .padding(horizontal = 8.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = "$ ${alert.summary}",
                        style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.sp),
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                if (!alert.blocked) {
                    Spacer(modifier = Modifier.width(8.dp))
                    TextButton(
                        onClick = { onBlockIp(alert.ip) },
                        colors = ButtonDefaults.textButtonColors(contentColor = RoseCritical),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Block,
                            contentDescription = "Block IP",
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "Block",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        }
    }
}
