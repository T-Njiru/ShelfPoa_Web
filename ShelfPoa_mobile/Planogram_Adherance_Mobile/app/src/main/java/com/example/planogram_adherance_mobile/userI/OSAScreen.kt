package com.example.planogram_adherance_mobile.userI

import android.graphics.Bitmap
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.planogram_adherance_mobile.data.OsaRepository
import com.example.planogram_adherance_mobile.ml.Detection
import com.example.planogram_adherance_mobile.ml.OSA
import com.example.planogram_adherance_mobile.models.OfflineSync
import com.example.planogram_adherance_mobile.models.Outlet
import com.example.planogram_adherance_mobile.ui.theme.*

private val InStockGreen = Color(0xFF4CAF50)
private val OutOfStockRed = Color(0xFFE5484D)

/**
 * Capture → detect happens upstream (CameraCapture / ShelfScreen); this screen is
 * review → confirm → submit. Signature unchanged, so existing navigation still compiles.
 */
@Composable
fun OSAScreen(
    debugBitmap: Bitmap?,
    skuCounts: Map<String, Int>,
    selectedOutlet: Outlet?,
    onBack: () -> Unit,
    onSubmitted: () -> Unit = onBack,
    shelfBitmap: Bitmap? = null,                  // original photo + raw detections: drawn by DetectionOverlay
    detections: List<Detection> = emptyList()     // (falls back to the old pre-drawn debugBitmap if null)
) {
    val context = LocalContext.current
    val scrollState = rememberScrollState()

    // One editable row per expected SKU, seeded from YOLO counts
    val statuses = remember(skuCounts) {
        mutableStateListOf(*OSA.buildStatuses(skuCounts).toTypedArray())
    }
    var submitted by remember { mutableStateOf(false) }

    val availableCount = statuses.count { it.available }
    val outOfStock = statuses.filterNot { it.available }
    val osaPct = OSA.osaPercent(statuses)

    // Edge photos: nothing at all detected (wall, very dark, not a shelf) vs a shelf with no Blueband
    val nothingDetected = skuCounts.isEmpty()
    val noBlueband = !nothingDetected && skuCounts.keys.none { it.startsWith("BB ") }
    var confirmEmpty by remember(skuCounts) { mutableStateOf(false) }
    // A photo with no detections must not silently become 13 stock-outs: the merchandiser either
    // marks what IS on the shelf, or confirms the shelf really is empty.
    val canSubmit = !nothingDetected || confirmEmpty || availableCount > 0

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg)
            .padding(24.dp)
            .verticalScroll(scrollState)
    ) {
        Text("On-Shelf Availability", color = AppTextWhite, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("Outlet: ${selectedOutlet?.outlet_name ?: "No outlet selected"}", color = AppCoral)

        Spacer(Modifier.height(20.dp))

        // Annotated capture: readable overlay when the raw photo is available, old debug image otherwise
        if (shelfBitmap != null) {
            DetectionOverlay(shelfBitmap, detections, height = 280.dp)
        } else Surface(
            modifier = Modifier.fillMaxWidth().height(280.dp),
            color = AppSurface,
            shape = RoundedCornerShape(12.dp)
        ) {
            Box(contentAlignment = Alignment.Center) {
                debugBitmap?.let {
                    Image(
                        bitmap = it.asImageBitmap(),
                        contentDescription = "Shelf capture with detections",
                        contentScale = ContentScale.Fit,
                        modifier = Modifier.fillMaxSize()
                    )
                } ?: Text("No capture", color = AppTextWhite.copy(0.5f))
            }
        }

        Spacer(Modifier.height(20.dp))

        // Summary
        Surface(modifier = Modifier.fillMaxWidth(), color = AppSurface, shape = RoundedCornerShape(12.dp)) {
            Row(
                modifier = Modifier.padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(Modifier.weight(1f)) {
                    Text("OSA", color = AppTextWhite.copy(0.6f), fontSize = 12.sp)
                    Text("${"%.0f".format(osaPct)}%", color = AppTextWhite, fontSize = 28.sp, fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("$availableCount / ${statuses.size} SKUs on shelf", color = AppTextWhite, fontSize = 13.sp)
                    Text(
                        "${outOfStock.size} out of stock",
                        color = if (outOfStock.isEmpty()) InStockGreen else OutOfStockRed,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        if (nothingDetected || noBlueband) {
            Surface(modifier = Modifier.fillMaxWidth(), color = OutOfStockRed.copy(alpha = 0.15f), shape = RoundedCornerShape(12.dp)) {
                Column(Modifier.padding(16.dp)) {
                    Text(
                        if (nothingDetected) "Nothing detected in this photo" else "No Blueband products detected",
                        color = OutOfStockRed, fontWeight = FontWeight.Bold, fontSize = 14.sp
                    )
                    Text(
                        if (nothingDetected)
                            "Make sure the photo shows the shelf and is well lit, then retake it. If the shelf really is empty, confirm below."
                        else
                            "Other products were found but no Blueband. If that's right, every Blueband SKU is out of stock.",
                        color = AppTextWhite.copy(0.85f), fontSize = 12.sp
                    )
                    if (nothingDetected) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = confirmEmpty, onCheckedChange = { confirmEmpty = it }, enabled = !submitted)
                            Text("The shelf really is empty - submit all as out of stock", color = AppTextWhite, fontSize = 12.sp)
                        }
                    }
                }
            }
            Spacer(Modifier.height(16.dp))
        }

        Text(
            "Review each SKU. Tap to correct the model if it's wrong.",
            color = AppTextWhite.copy(0.6f),
            fontSize = 12.sp
        )

        Spacer(Modifier.height(8.dp))

        // Review list
        Surface(modifier = Modifier.fillMaxWidth(), color = AppSurface, shape = RoundedCornerShape(12.dp)) {
            Column(Modifier.padding(vertical = 4.dp)) {
                statuses.forEachIndexed { index, s ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(s.sku, color = AppTextWhite, fontSize = 14.sp)
                            Text(
                                buildString {
                                    append(if (s.detected) "${s.facings} facing(s) detected" else "Not detected")
                                    if (s.overridden) append(" · corrected")
                                },
                                color = if (s.overridden) AppCoral else AppTextWhite.copy(0.5f),
                                fontSize = 11.sp
                            )
                        }
                        Switch(
                            checked = s.available,
                            onCheckedChange = { statuses[index] = s.copy(available = it) },
                            enabled = !submitted,
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = Color.White,
                                checkedTrackColor = InStockGreen,
                                uncheckedThumbColor = Color.White,
                                uncheckedTrackColor = OutOfStockRed
                            )
                        )
                    }
                    if (index < statuses.lastIndex) HorizontalDivider(color = AppTextWhite.copy(0.08f))
                }
            }
        }

        Spacer(Modifier.height(28.dp))

        AppButton(
            text = if (submitted) "Submitted" else "Submit OSA Report",
            onClick = {
                val outlet = selectedOutlet ?: return@AppButton
                submitted = true
                val app = context.applicationContext
                OsaRepository.submit(outlet, statuses.toList()) { reason ->
                    // The server refused it (e.g. account not set up as a merchandiser) -- say so
                    Toast.makeText(app, "OSA report was rejected: $reason", Toast.LENGTH_LONG).show()
                }
                // Queued locally; syncs automatically if offline
                Toast.makeText(
                    context,
                    if (OfflineSync.isOnline) "OSA report submitted"
                    else "No connection - OSA report saved on this phone and will upload automatically",
                    Toast.LENGTH_LONG
                ).show()
                onSubmitted()
            },
            containerColor = AppCoral,
            enabled = !submitted && canSubmit && selectedOutlet != null && selectedOutlet.id.isNotEmpty()
        )

        if (selectedOutlet == null) {
            Spacer(Modifier.height(8.dp))
            Text("Select an outlet before submitting.", color = OutOfStockRed, fontSize = 12.sp)
        }

        Spacer(Modifier.height(12.dp))
        Button(
            onClick = onBack,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = AppSurface)
        ) {
            Text("Cancel")
        }
    }
}