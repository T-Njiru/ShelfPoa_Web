package com.example.planogram_adherance_mobile.userI

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.planogram_adherance_mobile.ui.theme.*

@Composable
fun ShelfScreen(
    bitmap: Bitmap?,
    onCapture: () -> Unit,
    onGallery: () -> Unit,
    onCompare: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(Modifier.height(40.dp))
        Text(
            "Take Photo of shelf",
            color = AppTextWhite,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold
        )

        Spacer(Modifier.height(32.dp))

        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .height(300.dp),
            color = AppSurface,
            shape = RoundedCornerShape(12.dp)
        ) {
            Box(contentAlignment = Alignment.Center) {
                bitmap?.let {
                    Image(
                        bitmap = it.asImageBitmap(),
                        contentDescription = null,
                        modifier = Modifier.fillMaxSize()
                    )
                }
            }
        }

        Spacer(Modifier.height(48.dp))

        AppButton(text = "Take Live photo", onClick = onCapture)
        Spacer(Modifier.height(16.dp))
        AppButton(text = "Choose from Gallery", onClick = onGallery)

        Spacer(Modifier.weight(1f))

        AppButton(
            text = "Analyze & Compare",
            onClick = onCompare,
            containerColor = AppCoral,
            enabled = bitmap != null
        )
        Spacer(Modifier.height(16.dp))
    }
}