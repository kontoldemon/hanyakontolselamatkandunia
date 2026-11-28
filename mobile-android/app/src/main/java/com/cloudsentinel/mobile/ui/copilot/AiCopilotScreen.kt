package com.cloudsentinel.mobile.ui.copilot

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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.cloudsentinel.mobile.R
import com.cloudsentinel.mobile.core.theme.ElectricBlue
import com.cloudsentinel.mobile.core.theme.ElectricBlueSoft
import com.cloudsentinel.mobile.core.theme.ObsidianBg
import com.cloudsentinel.mobile.core.theme.ObsidianBorder
import com.cloudsentinel.mobile.core.theme.ObsidianCard
import com.cloudsentinel.mobile.core.theme.ObsidianSurfaceElevated
import com.cloudsentinel.mobile.core.theme.RoseCritical
import com.cloudsentinel.mobile.core.theme.TextMutedDark
import com.cloudsentinel.mobile.core.theme.TextPrimaryDark
import com.cloudsentinel.mobile.data.repository.CopilotMessage
import com.cloudsentinel.mobile.data.repository.CopilotSender

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AiCopilotScreen(
    messages: List<CopilotMessage>,
    isSending: Boolean,
    onSendMessage: (String) -> Unit,
    onStopMessage: () -> Unit
) {
    var inputText by rememberSaveable { mutableStateOf("") }
    val listState = rememberLazyListState()
    val focusManager = LocalFocusManager.current
    val keyboardController = LocalSoftwareKeyboardController.current
    val haptic = LocalHapticFeedback.current

    fun dismissInputFocus() {
        focusManager.clearFocus()
        keyboardController?.hide()
    }

    fun sendMessage(raw: String) {
        val toSend = raw.trim()
        if (toSend.isNotBlank() && !isSending) {
            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
            inputText = ""
            dismissInputFocus()
            onSendMessage(toSend)
        }
    }

    fun submitMessage() {
        sendMessage(inputText)
    }

    val quickPrompts = listOf(
        "Killswitch status",
        "Explain T1059.004",
        "Cluster MTTB",
        "Top attack origins"
    )

    LaunchedEffect(messages.size, isSending) {
        if (messages.isNotEmpty() || isSending) {
            listState.animateScrollToItem(if (isSending) messages.size else messages.lastIndex)
        }
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
                            text = "Copilot",
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
                .pointerInput(Unit) {
                    detectTapGestures(onTap = { dismissInputFocus() })
                }
        ) {
            // Subtle Quick Prompts
            LazyRow(
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(quickPrompts) { prompt ->
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(10.dp))
                            .background(ObsidianCard)
                            .border(1.dp, ObsidianBorder, RoundedCornerShape(10.dp))
                            .clickable {
                                sendMessage(prompt)
                            }
                            .padding(horizontal = 12.dp, vertical = 8.dp)
                    ) {
                        Text(
                            text = prompt,
                            style = MaterialTheme.typography.labelMedium,
                            color = TextMutedDark,
                            fontSize = 12.sp
                        )
                    }
                }
            }

            // Message Stream (tap anywhere on chat to unfocus input & hide keyboard)
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .pointerInput(Unit) {
                        detectTapGestures(onTap = { dismissInputFocus() })
                    },
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                items(messages) { msg ->
                    ChatBubble(message = msg)
                }
                if (isSending) {
                    item { ThinkingBubble() }
                }
            }

            HorizontalDivider(color = ObsidianBorder, thickness = 1.dp)

            // Clean Composer Bar (exact height parity between input and send button)
            var isInputFocused by remember { mutableStateOf(false) }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(ObsidianBg)
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.Bottom
            ) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 48.dp)
                        .clip(RoundedCornerShape(24.dp))
                        .background(ObsidianCard)
                        .border(
                            width = 1.dp,
                            color = if (isInputFocused) ElectricBlueSoft else ObsidianBorder,
                            shape = RoundedCornerShape(24.dp)
                        )
                        .padding(horizontal = 18.dp, vertical = 13.dp),
                    contentAlignment = Alignment.CenterStart
                ) {
                    if (inputText.isEmpty()) {
                        Text(
                            text = "Ask about threats, IPs, or rules...",
                            fontSize = 14.sp,
                            color = TextMutedDark
                        )
                    }
                    BasicTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        modifier = Modifier
                            .fillMaxWidth()
                            .onFocusChanged { isInputFocused = it.isFocused },
                        textStyle = TextStyle(
                            color = TextPrimaryDark,
                            fontSize = 14.sp,
                            lineHeight = 20.sp
                        ),
                        cursorBrush = SolidColor(ElectricBlueSoft),
                        maxLines = 3,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(onSend = { submitMessage() })
                    )
                }

                Spacer(modifier = Modifier.width(10.dp))

                IconButton(
                    onClick = {
                        if (isSending) onStopMessage() else submitMessage()
                    },
                    modifier = Modifier
                        .size(48.dp)
                        .clip(CircleShape)
                        .background(
                            when {
                                isSending -> RoseCritical
                                inputText.isNotBlank() -> ElectricBlue
                                else -> ObsidianSurfaceElevated
                            }
                        )
                ) {
                    if (isSending) {
                        Icon(
                            imageVector = Icons.Default.Stop,
                            contentDescription = "Stop response",
                            tint = Color.White,
                            modifier = Modifier.size(20.dp)
                        )
                    } else {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.Send,
                            contentDescription = "Send",
                            tint = if (inputText.isNotBlank()) Color.White else TextMutedDark,
                            modifier = Modifier.size(19.dp)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ChatBubble(message: CopilotMessage) {
    val isUser = message.sender == CopilotSender.USER
    val bubbleShape = RoundedCornerShape(
        topStart = 18.dp,
        topEnd = 18.dp,
        bottomStart = if (isUser) 18.dp else 4.dp,
        bottomEnd = if (isUser) 4.dp else 18.dp
    )

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Box(
            modifier = Modifier
                .widthIn(min = 44.dp, max = 285.dp)
                .clip(bubbleShape)
                .background(if (isUser) ElectricBlue else ObsidianCard)
                .border(
                    width = if (isUser) 0.dp else 1.dp,
                    color = if (isUser) Color.Transparent else ObsidianBorder,
                    shape = bubbleShape
                )
                .padding(horizontal = 15.dp, vertical = 11.dp)
        ) {
            Text(
                text = remember(message.text) { markdownText(message.text) },
                style = if (isUser) {
                    MaterialTheme.typography.bodyMedium.copy(
                        color = Color.White,
                        lineHeight = 20.sp
                    )
                } else {
                    MaterialTheme.typography.bodyMedium.copy(
                        color = TextPrimaryDark,
                        lineHeight = 21.sp
                    )
                }
            )
        }
    }
}

@Composable
private fun ThinkingBubble() {
    val bubbleShape = RoundedCornerShape(
        topStart = 18.dp,
        topEnd = 18.dp,
        bottomStart = 4.dp,
        bottomEnd = 18.dp
    )
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.Start
    ) {
        Box(
            modifier = Modifier
                .widthIn(min = 44.dp, max = 285.dp)
                .clip(bubbleShape)
                .background(ObsidianCard)
                .border(1.dp, ObsidianBorder, bubbleShape)
                .padding(horizontal = 15.dp, vertical = 12.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(
                    modifier = Modifier.size(14.dp),
                    strokeWidth = 2.dp,
                    color = ElectricBlueSoft
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "CloudSentinel is thinking…",
                    color = TextMutedDark,
                    fontSize = 13.sp
                )
            }
        }
    }
}

private fun markdownText(text: String): AnnotatedString {
    val cleaned = text.replace(Regex("(?m)^#{1,6}\\s+"), "")
    val builder = AnnotatedString.Builder()
    var index = 0
    while (index < cleaned.length) {
        when {
            cleaned.startsWith("**", index) -> {
                val end = cleaned.indexOf("**", index + 2)
                if (end > index + 2) {
                    builder.withStyle(SpanStyle(fontWeight = FontWeight.Bold)) {
                        append(cleaned.substring(index + 2, end))
                    }
                    index = end + 2
                } else {
                    builder.append("**")
                    index += 2
                }
            }
            cleaned[index] == '`' -> {
                val end = cleaned.indexOf('`', index + 1)
                if (end > index + 1) {
                    builder.withStyle(SpanStyle(fontFamily = FontFamily.Monospace)) {
                        append(cleaned.substring(index + 1, end))
                    }
                    index = end + 1
                } else {
                    builder.append('`')
                    index++
                }
            }
            else -> {
                builder.append(cleaned[index])
                index++
            }
        }
    }
    return builder.toAnnotatedString()
}
