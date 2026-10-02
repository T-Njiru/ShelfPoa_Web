package com.example.planogram_adherance_mobile.userI

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.planogram_adherance_mobile.R
import com.example.planogram_adherance_mobile.ui.theme.AppCoral
import com.example.planogram_adherance_mobile.ui.theme.AppDarkBg
import com.example.planogram_adherance_mobile.ui.theme.AppTextWhite
import kotlinx.coroutines.delay

@Composable
fun SplashScreen(onTimeout: () -> Unit) {
    // Logic to wait and then navigate
    LaunchedEffect(Unit) {
        delay(2500) // 2.5 seconds
        onTimeout()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Your custom logo.png5
        Image(
            painter = painterResource(id = R.drawable.logo), // Use lowercase 'logo'
            contentDescription = "Shelf Poa Logo",
            modifier = Modifier.size(180.dp) // Adjust size as needed
        )

        Spacer(Modifier.height(24.dp))

        Text(
            "Shelf Poa",
            color = AppCoral,
            fontSize = 32.sp,
            fontWeight = FontWeight.Bold
        )

        Text(
            "For all your shelving needs",
            color = AppTextWhite.copy(alpha = 0.7f),
            fontSize = 16.sp,
            fontWeight = FontWeight.Normal
        )
    }
}