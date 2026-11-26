package com.cloudsentinel.mobile.ui.pairing

import android.Manifest
import android.content.res.Configuration
import androidx.compose.ui.platform.LocalConfiguration
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.cloudsentinel.mobile.BuildConfig
import com.cloudsentinel.mobile.R
import com.cloudsentinel.mobile.core.network.ApiClient
import com.cloudsentinel.mobile.core.network.QrPairingPayload
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

@Composable
fun PairingScreen(
    isPairing: Boolean,
    errorMessage: String?,
    onPairSubmit: (serverUrl: String, pairingCode: String, pairingToken: String) -> Unit,
    onDemoBypass: () -> Unit = {}
) {
    var selectedTab by remember { mutableIntStateOf(0) }
    var serverUrl by remember { mutableStateOf("http://127.0.0.1:8080") }
    var pairingCode by remember { mutableStateOf("") }
    var pairingToken by remember { mutableStateOf("") }
    var isCameraActive by remember { mutableStateOf(false) }
    val haptic = LocalHapticFeedback.current
    val focusManager = LocalFocusManager.current
    val keyboardController = LocalSoftwareKeyboardController.current
    val isLandscape = LocalConfiguration.current.orientation == Configuration.ORIENTATION_LANDSCAPE

    fun dismissInputFocus() {
        focusManager.clearFocus()
        keyboardController?.hide()
    }

    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) isCameraActive = true
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(ObsidianBg)
            .statusBarsPadding()
            .navigationBarsPadding()
            .pointerInput(Unit) {
                detectTapGestures(onTap = { dismissInputFocus() })
            }
            .let { if (isLandscape) it.verticalScroll(rememberScrollState()) else it }
            .padding(horizontal = 24.dp, vertical = if (isLandscape) 14.dp else 20.dp),
        verticalArrangement = if (isLandscape) Arrangement.spacedBy(16.dp) else Arrangement.SpaceBetween
    ) {
        // TOP: Minimalist Brand Header + Segmented Switcher
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                Image(
                    painter = painterResource(id = R.drawable.ic_shield_logo),
                    contentDescription = "CloudSentinel",
                    modifier = Modifier.size(30.dp)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        text = buildAnnotatedString {
                            append("Cloud")
                            withStyle(SpanStyle(color = ElectricBlueSoft)) {
                                append("Sentinel")
                            }
                        },
                        style = MaterialTheme.typography.titleLarge.copy(
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 20.sp,
                            letterSpacing = (-0.3).sp
                        ),
                        color = TextPrimaryDark
                    )
                    Text(
                        text = "Mobile Command",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMutedDark,
                        fontSize = 12.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(28.dp))

            // Clean Minimalist Segmented Control
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(14.dp))
                    .background(ObsidianCard)
                    .border(1.dp, ObsidianBorder, RoundedCornerShape(14.dp))
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                SegmentTab(
                    label = "Scan QR",
                    icon = Icons.Default.QrCodeScanner,
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    modifier = Modifier.weight(1f)
                )
                SegmentTab(
                    label = "Manual",
                    icon = Icons.Default.Edit,
                    selected = selectedTab == 1,
                    onClick = {
                        isCameraActive = false
                        selectedTab = 1
                    },
                    modifier = Modifier.weight(1f)
                )
            }
        }

        // CENTER: Spacious QR Viewfinder or Manual Entry
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .let { if (isLandscape) it else it.weight(1f).padding(vertical = 24.dp) },
            contentAlignment = Alignment.Center
        ) {
            AnimatedContent(
                targetState = selectedTab,
                transitionSpec = { fadeIn() togetherWith fadeOut() },
                label = "PairingModeContent"
            ) { tab ->
                if (tab == 0) {
                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        if (isCameraActive) {
                            // Single clean camera frame with ONE close button in top-right
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(if (isLandscape) 300.dp else 340.dp)
                                    .clip(RoundedCornerShape(24.dp))
                                    .border(1.dp, ObsidianBorder, RoundedCornerShape(24.dp))
                            ) {
                                QrCodeScanner(
                                    onQrScanned = { raw ->
                                        runCatching {
                                            val parsed = ApiClient.json.decodeFromString<QrPairingPayload>(raw)
                                            serverUrl = parsed.serverUrl
                                            pairingCode = parsed.pairingCode
                                            pairingToken = parsed.pairingToken
                                            isCameraActive = false
                                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                            onPairSubmit(parsed.serverUrl, parsed.pairingCode, parsed.pairingToken)
                                        }
                                    }
                                )

                                IconButton(
                                    onClick = { isCameraActive = false },
                                    modifier = Modifier
                                        .align(Alignment.TopEnd)
                                        .padding(14.dp)
                                        .size(38.dp)
                                        .clip(CircleShape)
                                        .background(Color.Black.copy(alpha = 0.65f))
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Close,
                                        contentDescription = "Close scanner",
                                        tint = Color.White,
                                        modifier = Modifier.size(20.dp)
                                    )
                                }
                            }
                        } else {
                            // Calm, premium minimalist QR launcher surface
                            Surface(
                                shape = RoundedCornerShape(24.dp),
                                color = ObsidianCard,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(270.dp)
                                    .border(1.dp, ObsidianBorder, RoundedCornerShape(24.dp))
                                    .clip(RoundedCornerShape(24.dp))
                                    .clickable {
                                        cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                                    }
                            ) {
                                Column(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .padding(24.dp),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    verticalArrangement = Arrangement.Center
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .size(64.dp)
                                            .clip(CircleShape)
                                            .background(ElectricBlue.copy(alpha = 0.14f)),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.CameraAlt,
                                            contentDescription = "Open QR Scanner",
                                            tint = ElectricBlueSoft,
                                            modifier = Modifier.size(28.dp)
                                        )
                                    }
                                    Spacer(modifier = Modifier.height(18.dp))
                                    Text(
                                        text = "Tap to scan QR code",
                                        style = MaterialTheme.typography.titleMedium.copy(
                                            fontWeight = FontWeight.SemiBold,
                                            fontSize = 16.sp
                                        ),
                                        color = TextPrimaryDark
                                    )
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text(
                                        text = "Open Web Settings > Mobile Alerts to display your pairing code",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextMutedDark,
                                        textAlign = TextAlign.Center,
                                        lineHeight = 18.sp,
                                        modifier = Modifier.padding(horizontal = 12.dp)
                                    )
                                }
                            }
                        }

                        if (isPairing) {
                            Spacer(modifier = Modifier.height(20.dp))
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.Center
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(16.dp),
                                    strokeWidth = 2.dp,
                                    color = EmeraldLive
                                )
                                Spacer(modifier = Modifier.width(10.dp))
                                Text(
                                    text = "Connecting to sensor...",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = EmeraldLive
                                )
                            }
                        }
                    }
                } else {
                    // Clean Manual Setup Surface
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .verticalScroll(rememberScrollState()),
                        shape = RoundedCornerShape(20.dp),
                        color = ObsidianCard
                    ) {
                        Column(
                            modifier = Modifier
                                .border(1.dp, ObsidianBorder, RoundedCornerShape(20.dp))
                                .padding(20.dp)
                        ) {
                            Text(
                                text = "Manual Pairing",
                                style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold),
                                color = TextPrimaryDark
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "Enter the credentials from your web dashboard.",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMutedDark
                            )

                            Spacer(modifier = Modifier.height(18.dp))

                            OutlinedTextField(
                                value = serverUrl,
                                onValueChange = { serverUrl = it },
                                label = { Text("Sensor API URL", fontSize = 12.sp) },
                                singleLine = true,
                                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
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

                            Spacer(modifier = Modifier.height(12.dp))

                            OutlinedTextField(
                                value = pairingCode,
                                onValueChange = { if (it.length <= 6) pairingCode = it.filter(Char::isDigit) },
                                label = { Text("6-Digit Code", fontSize = 12.sp) },
                                singleLine = true,
                                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp),
                                textStyle = MaterialTheme.typography.bodyLarge.copy(
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.SemiBold,
                                    color = TextPrimaryDark,
                                    letterSpacing = 2.sp
                                ),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedContainerColor = ObsidianBg,
                                    unfocusedContainerColor = ObsidianBg,
                                    focusedBorderColor = ElectricBlueSoft,
                                    unfocusedBorderColor = ObsidianBorder
                                )
                            )

                            Spacer(modifier = Modifier.height(12.dp))

                            OutlinedTextField(
                                value = pairingToken,
                                onValueChange = { pairingToken = it.trim() },
                                label = { Text("Pairing Token", fontSize = 12.sp) },
                                singleLine = true,
                                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                                keyboardActions = KeyboardActions(
                                    onDone = {
                                        dismissInputFocus()
                                        if (!isPairing && serverUrl.isNotBlank() && pairingCode.length == 6) {
                                            onPairSubmit(serverUrl, pairingCode, pairingToken)
                                        }
                                    }
                                ),
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

                            Spacer(modifier = Modifier.height(20.dp))

                            Button(
                                onClick = {
                                    dismissInputFocus()
                                    onPairSubmit(serverUrl, pairingCode, pairingToken)
                                },
                                enabled = !isPairing && serverUrl.isNotBlank() && pairingCode.length == 6,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(48.dp),
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = ElectricBlue)
                            ) {
                                if (isPairing) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(18.dp),
                                        strokeWidth = 2.dp,
                                        color = Color.White
                                    )
                                } else {
                                    Text(
                                        text = "Connect",
                                        fontWeight = FontWeight.SemiBold,
                                        fontSize = 14.sp
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        // BOTTOM: Error feedback + subtle dev preview entry + minimal footer
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            if (!errorMessage.isNullOrBlank()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(RoseCritical.copy(alpha = 0.12f))
                        .padding(12.dp)
                ) {
                    Text(
                        text = errorMessage,
                        style = MaterialTheme.typography.bodySmall,
                        color = RoseCritical,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))
            }

            if (BuildConfig.DEBUG) {
                TextButton(
                    onClick = onDemoBypass,
                    modifier = Modifier.height(44.dp)
                ) {
                    Text(
                        text = "Continue in Dev Preview",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Medium,
                        color = ElectricBlueSoft
                    )
                }
            }

            Spacer(modifier = Modifier.height(6.dp))

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Lock,
                    contentDescription = null,
                    tint = TextMutedDark.copy(alpha = 0.7f),
                    modifier = Modifier.size(12.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = "Secured link with your CloudSentinel cluster",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextMutedDark.copy(alpha = 0.75f),
                    fontSize = 11.sp
                )
            }
        }
    }
}

@Composable
private fun SegmentTab(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .height(42.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(if (selected) ObsidianSurfaceElevated else Color.Transparent)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = if (selected) TextPrimaryDark else TextMutedDark,
                modifier = Modifier.size(16.dp)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = label,
                fontSize = 13.sp,
                fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                color = if (selected) TextPrimaryDark else TextMutedDark
            )
        }
    }
}
