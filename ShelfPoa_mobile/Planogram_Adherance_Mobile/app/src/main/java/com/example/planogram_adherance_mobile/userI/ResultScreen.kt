package com.example.planogram_adherance_mobile.userI

import android.graphics.Bitmap
import android.graphics.Paint
import android.graphics.Typeface
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.planogram_adherance_mobile.ml.Detection
import com.example.planogram_adherance_mobile.ui.theme.*
import com.example.planogram_adherance_mobile.models.Outlet
import com.google.firebase.database.FirebaseDatabase
import androidx.compose.foundation.Image

data class AuditResult(
    val timestamp: Long = System.currentTimeMillis(),
    val adherenceScore: Float = 0f,
    val totalPlanogramItems: Int = 0,
    val totalDetectedItems: Int = 0,
    val status: String = "",
    val outletId: String = "",
    val outletName: String = ""
)

@Composable
fun ResultScreen(
    adherence: Float,
    planogramDetections: List<Detection>,
    shelfDetections: List<Detection>,
    planogramBitmap: Bitmap?,
    shelfBitmap: Bitmap?,
    selectedOutlet: Outlet?, // NEW
    onBackToDashboard: () -> Unit
) {
    val database = FirebaseDatabase.getInstance().reference
    var isUploading by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(Modifier.height(40.dp))
        Text(
            "Outlet: ${selectedOutlet?.outlet_name ?: "N/A"}",
            color = AppCoral,
            style = MaterialTheme.typography.bodyMedium
        )
        Text(
            "Adherence Score: ${adherence.toInt()}%",
            color = AppTextWhite,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold
        )

        Spacer(Modifier.height(24.dp))

        ResultContainer(planogramBitmap, planogramDetections, Color.Blue)
        Spacer(Modifier.height(16.dp))
        ResultContainer(shelfBitmap, shelfDetections, Color.Green)

        Spacer(Modifier.weight(1f))

        AppButton(
            text = if (isUploading) "Uploading..." else "Submit Result & Exit",
            onClick = {
                isUploading = true
                val audit = AuditResult(
                    adherenceScore = adherence,
                    totalPlanogramItems = planogramDetections.size,
                    totalDetectedItems = shelfDetections.size,
                    status = if (adherence > 70f) "Pass" else "Fail",
                    outletId = selectedOutlet?.id ?: "unknown",
                    outletName = selectedOutlet?.outlet_name ?: "unknown"
                )
                database.child("audits").push().setValue(audit).addOnCompleteListener {
                    isUploading = false
                    onBackToDashboard()
                }
            },
            containerColor = AppCoral,
            enabled = !isUploading
        )
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
fun ResultContainer(bitmap: Bitmap?, detections: List<Detection>, boxColor: Color) {
    val textPaint = Paint().apply {
        color = android.graphics.Color.WHITE
        textSize = 24f
        typeface = Typeface.DEFAULT_BOLD
    }

    Surface(
        modifier = Modifier.fillMaxWidth().height(200.dp),
        color = AppSurface,
        shape = RoundedCornerShape(12.dp)
    ) {
        Box {
            bitmap?.let {
                Image(
                    bitmap = it.asImageBitmap(),
                    contentDescription = null,
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Fit
                )
            }
            Canvas(Modifier.fillMaxSize()) {
                detections.forEach { det ->
                    val left = det.box.left * size.width
                    val top = det.box.top * size.height
                    drawRect(
                        color = boxColor,
                        topLeft = Offset(left, top),
                        size = Size(det.box.width * size.width, det.box.height * size.height),
                        style = Stroke(width = 3f)
                    )
                    drawContext.canvas.nativeCanvas.drawText(det.className, left, top - 5f, textPaint)
                }
            }
        }
    }
}