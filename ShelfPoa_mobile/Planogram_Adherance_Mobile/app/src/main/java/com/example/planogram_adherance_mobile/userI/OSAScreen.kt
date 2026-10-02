package com.example.planogram_adherance_mobile.userI

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.planogram_adherance_mobile.ui.theme.*
import com.example.planogram_adherance_mobile.models.Outlet
import com.google.firebase.database.FirebaseDatabase

data class OsaResult(
    val timestamp: Long = System.currentTimeMillis(),
    val skuCounts: Map<String, Int> = emptyMap(),
    val outletId: String = "",
    val outletName: String = ""
)

@Composable
fun OSAScreen(
    debugBitmap: Bitmap?,
    skuCounts: Map<String, Int>,
    selectedOutlet: Outlet?, // NEW
    onBack: () -> Unit
) {
    val scrollState = rememberScrollState()
    val database = FirebaseDatabase.getInstance().reference
    var isUploading by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier.fillMaxSize().background(AppDarkBg).padding(24.dp).verticalScroll(scrollState),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text("OSA Debug View", color = AppTextWhite, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("Outlet: ${selectedOutlet?.outlet_name ?: "N/A"}", color = AppCoral)

        Spacer(Modifier.height(20.dp))

        Surface(
            modifier = Modifier.fillMaxWidth().height(350.dp),
            color = AppSurface,
            shape = RoundedCornerShape(12.dp)
        ) {
            Box(contentAlignment = Alignment.Center) {
                debugBitmap?.let {
                    Image(bitmap = it.asImageBitmap(), contentDescription = "Debug", modifier = Modifier.fillMaxSize())
                } ?: Text("No Detection Data", color = AppTextWhite.copy(0.5f))
            }
        }

        Spacer(Modifier.height(24.dp))

        Surface(modifier = Modifier.fillMaxWidth(), color = AppSurface, shape = RoundedCornerShape(12.dp)) {
            Column(modifier = Modifier.padding(16.dp)) {
                if (skuCounts.isEmpty()) Text("No items found", color = AppTextWhite.copy(0.5f))
                skuCounts.forEach { (sku, count) ->
                    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(sku, color = AppTextWhite)
                        Text(count.toString(), color = AppCoral, fontWeight = FontWeight.ExtraBold)
                    }
                }
            }
        }

        Spacer(Modifier.height(32.dp))

        AppButton(
            text = if (isUploading) "Submitting..." else "Submit OSA Report",
            onClick = {
                isUploading = true
                val report = OsaResult(
                    skuCounts = skuCounts,
                    outletId = selectedOutlet?.id ?: "unknown",
                    outletName = selectedOutlet?.outlet_name ?: "N/A"
                )
                database.child("osa_reports").push().setValue(report).addOnSuccessListener {
                    isUploading = false
                    onBack()
                }
            },
            containerColor = AppCoral,
            enabled = !isUploading
        )

        Spacer(Modifier.height(12.dp))
        Button(onClick = onBack, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = AppSurface)) {
            Text("Cancel")
        }
    }
}