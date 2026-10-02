package com.example.planogram_adherance_mobile.userI

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import com.example.planogram_adherance_mobile.ui.theme.AppDarkBg
import com.example.planogram_adherance_mobile.ui.theme.AppTextWhite

@Composable
fun HelpScreen(onBack: () -> Unit) {
    Box(
        modifier = Modifier.fillMaxSize().background(AppDarkBg),
        contentAlignment = Alignment.Center
    ) {
        Text("Help & Support Center", color = AppTextWhite)
    }
}
