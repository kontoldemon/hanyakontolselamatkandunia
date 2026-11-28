package com.cloudsentinel.mobile.core.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider

private val DarkColors = darkColorScheme(
    primary = ElectricBlue,
    secondary = EmeraldLive,
    error = RoseCritical,
    background = DarkPalette.background,
    surface = DarkPalette.card,
    surfaceVariant = DarkPalette.panel,
    onPrimary = DarkPalette.textPrimary,
    onBackground = DarkPalette.textPrimary,
    onSurface = DarkPalette.textPrimary,
    onSurfaceVariant = DarkPalette.textMuted,
    outline = DarkPalette.border
)

private val LightColors = lightColorScheme(
    primary = ElectricBlue,
    secondary = EmeraldLive,
    error = RoseCritical,
    background = LightPalette.background,
    surface = LightPalette.card,
    surfaceVariant = LightPalette.panel,
    onPrimary = LightPalette.textPrimary,
    onBackground = LightPalette.textPrimary,
    onSurface = LightPalette.textPrimary,
    onSurfaceVariant = LightPalette.textMuted,
    outline = LightPalette.border
)

@Composable
fun CloudSentinelTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val palette = if (darkTheme) DarkPalette else LightPalette
    CompositionLocalProvider(LocalSentinelPalette provides palette) {
        MaterialTheme(
            colorScheme = if (darkTheme) DarkColors else LightColors,
            typography = CloudSentinelTypography,
            content = content
        )
    }
}

enum class ThemeMode(val label: String) {
    LIGHT("Light"),
    DARK("Dark"),
    SYSTEM("System")
}
