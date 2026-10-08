package com.surpay.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val Brand = Color(0xFF0B6E4F)
val BrandBright = Color(0xFF34C38F)
val BrandDeep = Color(0xFF064E3B)
val Gold = Color(0xFFE6A700)

private val Light = lightColorScheme(
    primary = Brand,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE6F4EE),
    onPrimaryContainer = Color(0xFF06402E),
    secondary = Color(0xFF475467),
    secondaryContainer = Color(0xFFEFF2F7),
    tertiary = Color(0xFF8A5A00),
    tertiaryContainer = Color(0xFFFFF1D6),
    onTertiaryContainer = Color(0xFF6B4A00),
    background = Color(0xFFF7F9FC),
    surface = Color(0xFFF7F9FC),
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color.White,
    surfaceContainer = Color(0xFFF1F4F9),
    surfaceVariant = Color(0xFFEFF2F7),
    onSurfaceVariant = Color(0xFF5B6474),
    outline = Color(0xFFDCE2EC),
    outlineVariant = Color(0xFFE8ECF3),
    error = Color(0xFFC0362C),
)

private val Dark = darkColorScheme(
    primary = BrandBright,
    onPrimary = Color(0xFF062016),
    primaryContainer = Color(0xFF123528),
    onPrimaryContainer = Color(0xFFBFF0DA),
    secondary = Color(0xFFB8C0CC),
    secondaryContainer = Color(0xFF1A2438),
    tertiary = Color(0xFFF2C26B),
    tertiaryContainer = Color(0xFF3A2C0B),
    onTertiaryContainer = Color(0xFFFFE2A8),
    background = Color(0xFF0B1120),
    surface = Color(0xFF0B1120),
    surfaceContainerLowest = Color(0xFF0E1527),
    surfaceContainerLow = Color(0xFF111A2D),
    surfaceContainer = Color(0xFF131C2E),
    surfaceVariant = Color(0xFF162036),
    onSurfaceVariant = Color(0xFF9AA4B5),
    outline = Color(0xFF23304A),
    outlineVariant = Color(0xFF1C2740),
    error = Color(0xFFFF8A80),
)

private val base = Typography()
private val AppTypography = Typography(
    displaySmall = base.displaySmall.copy(fontWeight = FontWeight.ExtraBold, letterSpacing = (-0.5).sp),
    headlineLarge = base.headlineLarge.copy(fontWeight = FontWeight.ExtraBold, letterSpacing = (-0.5).sp),
    headlineMedium = base.headlineMedium.copy(fontWeight = FontWeight.Bold, letterSpacing = (-0.25).sp),
    headlineSmall = base.headlineSmall.copy(fontWeight = FontWeight.Bold),
    titleLarge = base.titleLarge.copy(fontWeight = FontWeight.Bold),
    titleMedium = base.titleMedium.copy(fontWeight = FontWeight.SemiBold),
    labelLarge = base.labelLarge.copy(fontWeight = FontWeight.SemiBold),
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(22.dp),
    extraLarge = RoundedCornerShape(28.dp),
)

/** The green hero gradient used on headline cards. */
val HeroGradient = Brush.linearGradient(listOf(Color(0xFF0E8A63), BrandDeep))

@Composable
fun SurpayTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) Dark else Light,
        typography = AppTypography,
        shapes = AppShapes,
        content = content,
    )
}
