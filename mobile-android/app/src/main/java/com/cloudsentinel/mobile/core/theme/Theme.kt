package com.cloudsentinel.mobile.core.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val DarkColors = darkColorScheme(
    primary = ElectricBlue,
    secondary = EmeraldLive,
    error = RoseCritical,
    background = ObsidianBg,
    surface = ObsidianCard,
    surfaceVariant = ObsidianPanel,
    onPrimary = TextPrimaryDark,
    onBackground = TextPrimaryDark,
    onSurface = TextPrimaryDark,
    onSurfaceVariant = TextMutedDark,
    outline = ObsidianBorder
)

private val LightColors = lightColorScheme(
    primary = ElectricBlue,
    secondary = EmeraldLive,
    error = RoseCritical,
    background = LightBg,
    surface = LightCard,
    surfaceVariant = LightPanel,
    onPrimary = LightCard,
    onBackground = TextPrimaryLight,
    onSurface = TextPrimaryLight,
    onSurfaceVariant = TextMutedLight,
    outline = LightBorder
)

@Composable
fun CloudSentinelTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = CloudSentinelTypography,
        content = content
    )
}
