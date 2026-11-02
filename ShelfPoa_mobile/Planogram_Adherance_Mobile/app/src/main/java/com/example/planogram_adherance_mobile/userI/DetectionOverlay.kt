package com.example.planogram_adherance_mobile.userI

import android.graphics.Bitmap
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.planogram_adherance_mobile.ml.Detection
import com.example.planogram_adherance_mobile.ui.theme.*
import kotlin.math.min

private val BluebandBox = Color(0xFF2F9BFF)   // Blueband SKUs
private val OtherBox = Color(0xFFB0B0B8)      // OTHERS / competitor products

/**
 * Photo + YOLO detections, readable even with ~100 boxes:
 *  - the image is fitted (letterboxed) and the boxes are mapped onto the FITTED image, so they line up
 *  - thin boxes, colour-coded: blue = Blueband, grey = other brands
 *  - no labels by default; tap the photo to show short labels (Blueband only, e.g. "ORI 250g")
 *  - legend with counts underneath
 * Box coordinates may be normalised (0-1) or in image pixels; both are handled.
 */
@Composable
fun DetectionOverlay(
    bitmap: Bitmap?,
    detections: List<Detection>,
    modifier: Modifier = Modifier,
    title: String? = null,
    height: Dp = 260.dp
) {
    var showLabels by remember { mutableStateOf(false) }
    val measurer = rememberTextMeasurer()
    val bluebandCount = detections.count { it.className.startsWith("BB ") }
    val otherCount = detections.size - bluebandCount

    Column(modifier.fillMaxWidth()) {
        if (title != null) {
            Text(title, color = AppTextWhite.copy(0.7f), fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(6.dp))
        }
        Surface(
            modifier = Modifier.fillMaxWidth().height(height),
            color = AppSurface,
            shape = RoundedCornerShape(12.dp)
        ) {
            Box(
                Modifier.fillMaxSize().clipToBounds().clickable(enabled = bitmap != null) { showLabels = !showLabels },
                contentAlignment = Alignment.Center
            ) {
                if (bitmap == null) {
                    Text("No image", color = AppTextWhite.copy(0.5f))
                } else {
                    val image = remember(bitmap) { bitmap.asImageBitmap() }
                    val pixelCoords = remember(detections) {
                        detections.any { it.box.right > 1.5f || it.box.bottom > 1.5f }
                    }
                    Canvas(Modifier.fillMaxSize()) {
                        // fit the photo inside the panel, keeping its aspect ratio
                        val scale = min(size.width / bitmap.width, size.height / bitmap.height)
                        val dw = bitmap.width * scale
                        val dh = bitmap.height * scale
                        val ox = (size.width - dw) / 2f
                        val oy = (size.height - dh) / 2f
                        drawImage(
                            image = image,
                            dstOffset = IntOffset(ox.toInt(), oy.toInt()),
                            dstSize = IntSize(dw.toInt(), dh.toInt())
                        )
                        // map box coordinates onto the fitted photo (not the whole panel)
                        val sx = if (pixelCoords) scale else dw
                        val sy = if (pixelCoords) scale else dh
                        val stroke = Stroke(width = 1.5.dp.toPx())
                        val labelStyle = TextStyle(color = Color.White, fontSize = 8.sp, background = BluebandBox.copy(alpha = 0.85f))

                        // others first, Blueband on top
                        detections.sortedBy { it.className.startsWith("BB ") }.forEach { d ->
                            val isBb = d.className.startsWith("BB ")
                            val left = ox + d.box.left * sx
                            val top = oy + d.box.top * sy
                            drawRect(
                                color = if (isBb) BluebandBox else OtherBox.copy(alpha = 0.6f),
                                topLeft = Offset(left, top),
                                size = Size(d.box.width * sx, d.box.height * sy),
                                style = stroke
                            )
                            if (showLabels && isBb) {
                                drawText(
                                    textMeasurer = measurer,
                                    text = d.className.removePrefix("BB "),
                                    topLeft = Offset(left, top),
                                    style = labelStyle
                                )
                            }
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(6.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            LegendDot(BluebandBox); Text(" Blueband ($bluebandCount)", color = AppTextWhite, fontSize = 11.sp)
            Spacer(Modifier.width(12.dp))
            LegendDot(OtherBox); Text(" Other brands ($otherCount)", color = AppTextWhite, fontSize = 11.sp)
            Spacer(Modifier.weight(1f))
            if (bitmap != null) {
                Text(if (showLabels) "Tap photo to hide labels" else "Tap photo for labels",
                    color = AppTextWhite.copy(0.5f), fontSize = 11.sp)
            }
        }
    }
}

@Composable
private fun LegendDot(color: Color) {
    Box(Modifier.size(10.dp).background(color, RoundedCornerShape(2.dp)))
}