package com.surpay.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Brand = Color(0xFF0B6E4F)
val BrandBright = Color(0xFF34C38F)

private val Light = lightColorScheme(
    primary = Brand,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE6F4EE),
    onPrimaryContainer = Color(0xFF06402E),
    secondary = Color(0xFF475467),
    background = Color(0xFFFFFFFF),
    surface = Color(0xFFFFFFFF),
    surfaceVariant = Color(0xFFF5F7FB),
    onSurfaceVariant = Color(0xFF5B6474),
    outline = Color(0xFFE3E8F0),
    error = Color(0xFFC0362C),
)

private val Dark = darkColorScheme(
    primary = BrandBright,
    onPrimary = Color(0xFF062016),
    primaryContainer = Color(0xFF123528),
    onPrimaryContainer = Color(0xFFBFF0DA),
    secondary = Color(0xFFB8C0CC),
    background = Color(0xFF0B1120),
    surface = Color(0xFF0B1120),
    surfaceVariant = Color(0xFF131C2E),
    onSurfaceVariant = Color(0xFF9AA4B5),
    outline = Color(0xFF23304A),
    error = Color(0xFFFF8A80),
)

@Composable
fun SurpayTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (darkTheme) Dark else Light, content = content)
}
