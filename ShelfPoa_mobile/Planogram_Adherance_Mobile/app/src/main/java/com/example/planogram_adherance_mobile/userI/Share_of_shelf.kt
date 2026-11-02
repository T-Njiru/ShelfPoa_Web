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
import com.example.planogram_adherance_mobile.models.CurrentUser
import com.example.planogram_adherance_mobile.models.Outlet
import com.example.planogram_adherance_mobile.ml.SoSCalculator
import androidx.compose.ui.platform.LocalContext
import com.example.planogram_adherance_mobile.models.OfflineSync

data class SosResult(
    val timestamp: Long = System.currentTimeMillis(),
    val coverageScore: Float = 0f,   // field name kept so existing Firebase records still match
    val status: String = "",
    val outletId: String = "",
    val outletName: String = "",
    val uid: String = "",
    val merchandiserId: String = "",
    val auditId: String = ""
)

@Composable
fun ShareOfShelfScreen(
    bitmap: Bitmap?,
    score: Float?,            // null = not calculated yet; 0f is a real (failing) result
    detectedCount: Int = 0,   // how many objects the model found in the photo (0 = wall / too dark / not a shelf)
    selectedOutlet: Outlet?,
    onCapture: (Bitmap) -> Unit,
    onGallery: () -> Unit,
    onCalculate: () -> Unit,
    onRetake: () -> Unit,   // clear the result and choose another photo from the gallery
    onBack: () -> Unit
) {
    val context = LocalContext.current
    var isUploading by remember { mutableStateOf(false) }
    var isCameraMode by remember { mutableStateOf(false) }

    if (isCameraMode) {
        CameraCapture { capturedBitmap ->
            onCapture(capturedBitmap)
            isCameraMode = false
        }
        return
    }

    val threshold = SoSCalculator.PASS_THRESHOLD
    val thresholdText = "${threshold.toInt()}%"

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

        val nothingDetected = score != null && detectedCount == 0
        if (score != null) {
            val isPass = SoSCalculator.isPass(score)
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(text = "${"%.1f".format(score)}% Share of Shelf", fontSize = 36.sp, fontWeight = FontWeight.Black, color = if (isPass) Color.Green else AppCoral)
                Text(text = if (isPass) "PASS (At or above $thresholdText)" else "FAIL (Below $thresholdText)", color = AppTextWhite, fontWeight = FontWeight.Bold)
                when {
                    nothingDetected -> Text(
                        "No products were found in this photo. Make sure it shows the shelf and is well lit, then choose another photo.",
                        color = AppCoral, fontSize = 13.sp, modifier = Modifier.padding(top = 8.dp)
                    )
                    score == 0f -> Text(
                        "No Blueband products were detected on this shelf.",
                        color = AppTextWhite.copy(0.8f), fontSize = 13.sp, modifier = Modifier.padding(top = 8.dp)
                    )
                }
            }
        }

        Spacer(Modifier.weight(1f))

        if (score == null) {
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
                    val outletId = selectedOutlet?.id ?: "unknown"
                    val result = SosResult(
                        coverageScore = score ?: 0f,
                        status = if (SoSCalculator.isPass(score ?: 0f)) "Pass" else "Fail",
                        outletId = outletId,
                        outletName = selectedOutlet?.outlet_name ?: "unknown",
                        uid = CurrentUser.uid,
                        merchandiserId = CurrentUser.merchandiserId,
                        auditId = CurrentUser.auditIdFor(outletId)
                    )
                    // Queued on the phone; uploads now or when the connection returns (no waiting offline)
                    OfflineSync.submit(context, "sos_audits", result)
                    onBack()
                },
                containerColor = AppCoral,
                enabled = !isUploading && !nothingDetected   // a wall / unusable photo isn't a 0% audit
            )
            Spacer(Modifier.height(16.dp))
            // Recalculate = pick another photo from the gallery (demo); the caller resets the score
            AppButton(text = "Recalculate", onClick = onRetake, containerColor = AppSurface, enabled = !isUploading)
            Spacer(Modifier.height(16.dp))
            // Retake with the camera: the caller's onCapture resets the score when the new photo arrives.
            // ("Choose Another from Gallery" removed: Recalculate now does exactly that.)
            AppButton(text = "Retake Photo", onClick = { isCameraMode = true }, containerColor = AppSurface, enabled = !isUploading)
        }

        Spacer(Modifier.height(16.dp))
        TextButton(onClick = onBack, enabled = !isUploading) {
            Text("Back to Menu", color = AppTextWhite.copy(0.7f))
        }
    }
}