package com.cloudsentinel.mobile.core.theme

import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

internal data class SentinelPalette(
    val background: Color,
    val panel: Color,
    val card: Color,
    val elevated: Color,
    val border: Color,
    val textPrimary: Color,
    val textMuted: Color,
    val accentSoft: Color
)

internal val DarkPalette = SentinelPalette(
    background = Color(0xFF090A0E),
    panel = Color(0xFF0D0F15),
    card = Color(0xFF13161F),
    elevated = Color(0xFF1A1E2A),
    border = Color(0x14FFFFFF),
    textPrimary = Color(0xFFF8FAFC),
    textMuted = Color(0xFF8B95A8),
    accentSoft = Color(0xFF60A5FA)
)

internal val LightPalette = SentinelPalette(
    background = Color(0xFFF8FAFC),
    panel = Color(0xFFF1F5F9),
    card = Color(0xFFFFFFFF),
    elevated = Color(0xFFFFFFFF),
    border = Color(0xFFE2E8F0),
    textPrimary = Color(0xFF0F172A),
    textMuted = Color(0xFF475569),
    accentSoft = Color(0xFF2563EB)
)

internal val LocalSentinelPalette = staticCompositionLocalOf { DarkPalette }

// Accents are shared by both themes.
val ElectricBlue = Color(0xFF3B82F6)
val EmeraldLive = Color(0xFF10B981)
val RoseCritical = Color(0xFFF43F5E)
val AmberWarning = Color(0xFFF59E0B)

// Legacy names stay so existing screens flip with the palette without a rewrite.
val ObsidianBg: Color
    @Composable @ReadOnlyComposable get() = LocalSentinelPalette.current.background
val ObsidianPanel: Color
    @Composable @ReadOnlyComposable get() = LocalSentinelPalette.current.panel
val ObsidianCard: Color
    @Composable @ReadOnlyComposable get() = LocalSentinelPalette.current.card
val ObsidianSurfaceElevated: Color
    @Composable @ReadOnlyComposable get() = LocalSentinelPalette.current.elevated
val ObsidianBorder: Color
    @Composable @ReadOnlyComposable get() = LocalSentinelPalette.current.border
val TextPrimaryDark: Color
    @Composable @ReadOnlyComposable get() = LocalSentinelPalette.current.textPrimary
val TextMutedDark: Color
    @Composable @ReadOnlyComposable get() = LocalSentinelPalette.current.textMuted
val ElectricBlueSoft: Color
    @Composable @ReadOnlyComposable get() = LocalSentinelPalette.current.accentSoft
