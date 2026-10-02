package com.example.planogram_adherance_mobile.userI

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.planogram_adherance_mobile.ui.theme.*

@Composable
fun MenuScreen(
    onNavigateToShelf: () -> Unit,
    onNavigateToSOS: () -> Unit,
    onNavigateToOSA: () -> Unit, // Added this parameter
    onNavigateToHelp: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            "Main Menu",
            color = AppTextWhite,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        Spacer(Modifier.height(64.dp))

        // Shelf Audit Button
        AppButton(
            text = "Shelf Audit",
            onClick = onNavigateToShelf,
            containerColor = AppCoral
        )

        Spacer(Modifier.height(16.dp))

        // Share of Shelf Button
        AppButton(
            text = "Share of Shelf",
            onClick = onNavigateToSOS,
            containerColor = AppCoral
        )

        Spacer(Modifier.height(16.dp))

        // OSA Debug Button - Matches the call in your MainActivity
        AppButton(
            text = "OSA Debug View",
            onClick = onNavigateToOSA,
            containerColor = AppCoral
        )

        Spacer(Modifier.height(16.dp))

        // Help Button
        AppButton(
            text = "Help",
            onClick = onNavigateToHelp,
            containerColor = AppSurface
        )
    }
}