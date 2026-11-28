package com.cloudsentinel.mobile.ui.sessions

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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.cloudsentinel.mobile.R
import com.cloudsentinel.mobile.core.network.MobileSessionItem
import com.cloudsentinel.mobile.core.theme.AmberWarning
import com.cloudsentinel.mobile.core.theme.ElectricBlue
import com.cloudsentinel.mobile.core.theme.ElectricBlueSoft
import com.cloudsentinel.mobile.core.theme.ObsidianBg
import com.cloudsentinel.mobile.core.theme.ObsidianBorder
import com.cloudsentinel.mobile.core.theme.ObsidianCard
import com.cloudsentinel.mobile.core.theme.RoseCritical
import com.cloudsentinel.mobile.core.theme.TextMutedDark
import com.cloudsentinel.mobile.core.theme.TextPrimaryDark

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionsScreen(
    sessions: List<MobileSessionItem>,
    isRefreshing: Boolean,
    isSensorReachable: Boolean?,
    onRefresh: () -> Unit,
    onSelectSession: (MobileSessionItem) -> Unit
) {
    var query by rememberSaveable { mutableStateOf("") }
    var filterName by rememberSaveable { mutableStateOf(SessionFilter.ALL.name) }
    val filter = SessionFilter.valueOf(filterName)
    val filtered = sessions.filter { session ->
        val matchesQuery = query.isBlank() ||
            session.ip.contains(query, ignoreCase = true) ||
            session.country.contains(query, ignoreCase = true) ||
            session.city.contains(query, ignoreCase = true) ||
            session.isp.contains(query, ignoreCase = true) ||
            session.commands.any { it.contains(query, ignoreCase = true) }
        val matchesFilter = when (filter) {
            SessionFilter.ALL -> true
            SessionFilter.HIGH_RISK -> session.risk_score >= 70
            SessionFilter.BLOCKED -> session.blocked
        }
        matchesQuery && matchesFilter
    }

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
                            text = "Sessions",
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
                .padding(horizontal = 20.dp)
        ) {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
                placeholder = {
                    Text(
                        text = "Search IP, country, city or command",
                        color = TextMutedDark,
                        fontSize = 13.sp
                    )
                },
                leadingIcon = {
                    Icon(
                        imageVector = Icons.Default.Search,
                        contentDescription = null,
                        tint = TextMutedDark
                    )
                },
                trailingIcon = {
                    if (query.isNotBlank()) {
                        IconButton(onClick = { query = "" }) {
                            Icon(
                                imageVector = Icons.Default.Close,
                                contentDescription = "Clear search",
                                tint = TextMutedDark
                            )
                        }
                    }
                },
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = ElectricBlue,
                    unfocusedBorderColor = ObsidianBorder,
                    focusedContainerColor = ObsidianCard,
                    unfocusedContainerColor = ObsidianCard,
                    cursorColor = ElectricBlue,
                    focusedTextColor = TextPrimaryDark,
                    unfocusedTextColor = TextPrimaryDark
                )
            )

            Spacer(modifier = Modifier.height(8.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SessionFilter.entries.forEach { option ->
                    val selected = filter == option
                    FilterChip(
                        selected = selected,
                        onClick = { filterName = option.name },
                        label = {
                            Text(text = option.label, fontSize = 12.sp)
                        },
                        colors = FilterChipDefaults.filterChipColors(
                            containerColor = ObsidianCard,
                            labelColor = TextMutedDark,
                            selectedContainerColor = ElectricBlue.copy(alpha = 0.14f),
                            selectedLabelColor = ElectricBlueSoft
                        )
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            PullToRefreshBox(
                isRefreshing = isRefreshing,
                onRefresh = onRefresh,
                modifier = Modifier.fillMaxSize()
            ) {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    contentPadding = PaddingValues(bottom = 24.dp)
                ) {
                    item {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = if (filtered.size == sessions.size) {
                                    "${sessions.size} recent attacker${if (sessions.size == 1) "" else "s"}"
                                } else {
                                    "${filtered.size} of ${sessions.size} attacker${if (sessions.size == 1) "" else "s"}"
                                },
                                style = MaterialTheme.typography.titleSmall.copy(
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 14.sp
                                ),
                                color = TextMutedDark
                            )
                            if (filtered.isNotEmpty()) {
                                Text(
                                    text = "Tap to inspect",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = ElectricBlueSoft
                                )
                            }
                        }
                    }

                    if (isSensorReachable == false) {
                        item {
                            Surface(
                                shape = RoundedCornerShape(14.dp),
                                color = AmberWarning.copy(alpha = 0.12f),
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text(
                                    text = "Sensor unreachable. Pull down to retry.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = AmberWarning,
                                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)
                                )
                            }
                        }
                    }

                    if (filtered.isEmpty()) {
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
                                    Icon(
                                        imageVector = Icons.Default.Terminal,
                                        contentDescription = null,
                                        tint = TextMutedDark,
                                        modifier = Modifier.height(26.dp)
                                    )
                                    Spacer(modifier = Modifier.height(8.dp))
                                    Text(
                                        text = if (sessions.isEmpty()) {
                                            "No recent threat sessions"
                                        } else {
                                            "No sessions match this filter"
                                        },
                                        style = MaterialTheme.typography.bodyMedium.copy(
                                            fontWeight = FontWeight.Medium
                                        ),
                                        color = TextPrimaryDark,
                                        textAlign = TextAlign.Center
                                    )
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        text = if (sessions.isEmpty()) {
                                            "Captured SSH and honeypot sessions will appear here in real time."
                                        } else {
                                            "Try another search or filter."
                                        },
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextMutedDark,
                                        textAlign = TextAlign.Center,
                                        lineHeight = 18.sp
                                    )
                                }
                            }
                        }
                    } else {
                        items(filtered.size) { idx ->
                            val session = filtered[idx]
                            SessionCard(
                                session = session,
                                onClick = { onSelectSession(session) }
                            )
                        }
                    }
                }
            }
        }
    }
}

private enum class SessionFilter(val label: String) {
    ALL("All"),
    HIGH_RISK("High risk"),
    BLOCKED("Blocked")
}

@Composable
private fun SessionCard(
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
                    text = buildString {
                        val commandCount = session.commands.size
                        append(
                            if (commandCount > 0) {
                                "$commandCount command${if (commandCount == 1) "" else "s"} recorded"
                            } else {
                                "Credential probe"
                            }
                        )
                        if (session.session_count > 1 || session.session_count_capped) {
                            val count = "${session.session_count}${if (session.session_count_capped) "+" else ""}"
                            append(" · $count sessions")
                        }
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMutedDark,
                    fontSize = 12.sp
                )
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                val riskScore = session.risk_score.coerceIn(0, 100)
                val riskColor = when {
                    riskScore >= 90 -> RoseCritical
                    riskScore >= 70 -> AmberWarning
                    else -> ElectricBlueSoft
                }
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(riskColor.copy(alpha = 0.14f))
                        .padding(horizontal = 10.dp, vertical = 5.dp)
                ) {
                    Text(
                        text = "$riskScore",
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
