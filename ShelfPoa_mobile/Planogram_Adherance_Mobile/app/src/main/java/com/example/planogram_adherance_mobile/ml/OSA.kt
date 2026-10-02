package com.example.planogram_adherance_mobile.ml

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint

object OSA {

    /**
     * Logic: Counts SKUs based on the Detection class.
     */
    fun calculateCounts(detections: List<Detection>): Map<String, Int> {
        return detections.groupBy { it.className }
            .mapValues { it.value.size }
    }

    /**
     * Logic: Returns a new Bitmap with bounding boxes drawn.
     */
    fun drawDebugBoxes(
        originalBitmap: Bitmap,
        detections: List<Detection>
    ): Bitmap {
        val debugBitmap = originalBitmap.copy(Bitmap.Config.ARGB_8888, true)
        val canvas = Canvas(debugBitmap)

        val boxPaint = Paint().apply {
            color = Color.RED
            style = Paint.Style.STROKE
            strokeWidth = 5f
        }

        val textPaint = Paint().apply {
            color = Color.YELLOW
            textSize = 35f
            isAntiAlias = true
        }

        for (det in detections) {
            val rect = det.box
            canvas.drawRect(rect.left, rect.top, rect.right, rect.bottom, boxPaint)
            canvas.drawText(det.className, rect.left, rect.top - 10f, textPaint)
        }
        return debugBitmap
    }
}