package com.example.planogram_adherance_mobile.userI

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.planogram_adherance_mobile.ui.theme.*
import com.example.planogram_adherance_mobile.models.Outlet
import com.google.firebase.database.FirebaseDatabase

data class SosResult(
    val timestamp: Long = System.currentTimeMillis(),
    val coverageScore: Float = 0f,
    val status: String = "",
    val outletId: String = "",
    val outletName: String = ""
)

@Composable
fun ShareOfShelfScreen(
    bitmap: Bitmap?,
    score: Float,
    selectedOutlet: Outlet?, // NEW
    onCapture: (Bitmap) -> Unit,
    onGallery: () -> Unit,
    onCalculate: () -> Unit,
    onBack: () -> Unit
) {
    val database = FirebaseDatabase.getInstance().reference
    var isUploading by remember { mutableStateOf(false) }
    var isCameraMode by remember { mutableStateOf(false) }

    if (isCameraMode) {
        CameraCapture { capturedBitmap ->
            onCapture(capturedBitmap)
            isCameraMode = false
        }
        return
    }

    Column(
        modifier = Modifier.fillMaxSize().background(AppDarkBg).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(Modifier.height(40.dp))
        Text("Share of Shelf", color = AppTextWhite, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("Store: ${selectedOutlet?.outlet_name ?: "Unknown"}", color = AppCoral, fontSize = 14.sp)

        Spacer(Modifier.height(24.dp))

        Surface(
            modifier = Modifier.fillMaxWidth().height(250.dp),
            color = AppSurface,
            shape = RoundedCornerShape(12.dp)
        ) {
            Box(contentAlignment = Alignment.Center) {
                bitmap?.let {
                    Image(bitmap = it.asImageBitmap(), contentDescription = null, modifier = Modifier.fillMaxSize())
                } ?: Text("No image captured", color = AppTextWhite.copy(0.5f))
            }
        }

        Spacer(Modifier.height(32.dp))

        if (score > 0f) {
            val isPass = score >= 20f
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(text = "${"%.1f".format(score)}% Coverage", fontSize = 36.sp, fontWeight = FontWeight.Black, color = if (isPass) Color.Green else AppCoral)
                Text(text = if (isPass) "PASS (Above 20%)" else "FAIL (Below 20%)", color = AppTextWhite, fontWeight = FontWeight.Bold)
            }
        }

        Spacer(Modifier.weight(1f))

        if (score <= 0f) {
            AppButton(text = "Take Live Photo", onClick = { isCameraMode = true })
            Spacer(Modifier.height(16.dp))
            AppButton(text = "Choose from Gallery", onClick = onGallery)
            Spacer(Modifier.height(16.dp))
            AppButton(text = "Calculate Share", onClick = onCalculate, containerColor = AppCoral, enabled = bitmap != null)
        } else {
            AppButton(
                text = if (isUploading) "Saving..." else "Submit & Exit",
                onClick = {
                    isUploading = true
                    val result = SosResult(
                        coverageScore = score,
                        status = if (score >= 20f) "Pass" else "Fail",
                        outletId = selectedOutlet?.id ?: "unknown",
                        outletName = selectedOutlet?.outlet_name ?: "unknown"
                    )
                    database.child("sos_audits").push().setValue(result).addOnCompleteListener {
                        isUploading = false
                        onBack()
                    }
                },
                containerColor = AppCoral,
                enabled = !isUploading
            )
            Spacer(Modifier.height(16.dp))
            AppButton(text = "Recalculate", onClick = onCalculate, containerColor = AppSurface, enabled = !isUploading)
        }

        Spacer(Modifier.height(16.dp))
        TextButton(onClick = onBack, enabled = !isUploading) {
            Text("Back to Menu", color = AppTextWhite.copy(0.7f))
        }
    }
}