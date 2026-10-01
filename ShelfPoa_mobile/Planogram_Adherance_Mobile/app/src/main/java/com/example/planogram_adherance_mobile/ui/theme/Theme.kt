package com.example.planogram_adherance_mobile.ui.theme

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val PlanogramColorScheme = darkColorScheme(
    primary = AppCoral,
    background = AppDarkBg,
    surface = AppSurface,
    onPrimary = Color.Black, // Dark text on the Coral buttons
    onBackground = AppTextWhite,
    onSurface = AppTextWhite
)

@Composable
fun Planogram_Adherance_MobileTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = PlanogramColorScheme,
        typography = AppTypography,
        content = content
    )
}