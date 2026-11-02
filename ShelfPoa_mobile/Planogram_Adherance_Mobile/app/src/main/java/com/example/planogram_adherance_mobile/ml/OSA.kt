package com.example.planogram_adherance_mobile.ml

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint

/** One row of the OSA review list: what YOLO saw vs. what the merchandiser confirmed. */
data class SkuStatus(
    val sku: String,
    val facings: Int,          // raw YOLO count for this SKU
    val available: Boolean     // merchandiser-confirmed; defaults to facings > 0
) {
    val detected: Boolean get() = facings > 0
    /** True when the merchandiser disagreed with the model. */
    val overridden: Boolean get() = available != detected
}

object OSA {

    /**
     * Legacy annotation classes that do not correspond to products in the current
     * Blueband range. The model can still output them, so they are excluded from
     * the OSA SKU counts (they still count as Blueband in Share of Shelf).
     */
    private val LEGACY_CLASSES = setOf("BB CHOCO 1Kg", "BB VANILLA 250g")

    /**
     * SKUs every outlet is expected to range. Order = display order in the review list.
     * TODO: replace with a per-outlet assortment (e.g. outlets_universe/{id}/expected_skus)
     *       once that data exists; until then every outlet is audited against the full range.
     */
    val EXPECTED_SKUS: List<String> = listOf(
        "BB ORI 100g", "BB ORI 250g", "BB ORI 500g", "BB ORI 1Kg",
        "BB S4B 100g", "BB S4B 250g", "BB S4B 500g", "BB S4B 1Kg",
        "BB CHOCO 100g", "BB CHOCO 250g", "BB CHOCO 500g",
        "BB VANILLA 500g", "BB VANILLA 1Kg"
    )

    /** Counts SKUs by detection class, excluding legacy classes. */
    fun calculateCounts(detections: List<Detection>): Map<String, Int> {
        return detections
            .filter { it.className !in LEGACY_CLASSES }
            .groupBy { it.className }
            .mapValues { it.value.size }
    }

    /** Expands raw counts into one status per expected SKU (missing SKU = 0 facings = out of stock). */
    fun buildStatuses(skuCounts: Map<String, Int>): List<SkuStatus> =
        EXPECTED_SKUS.map { sku ->
            val facings = skuCounts[sku] ?: 0
            SkuStatus(sku = sku, facings = facings, available = facings > 0)
        }

    /** Share of expected SKUs confirmed on shelf, 0–100. */
    fun osaPercent(statuses: List<SkuStatus>): Double =
        if (statuses.isEmpty()) 0.0
        else statuses.count { it.available } * 100.0 / statuses.size

    /**
     * Returns a new Bitmap with bounding boxes drawn.
     * OnnxYoloRunner returns boxes normalised to 0–1, so they are scaled back to the
     * bitmap's pixel size here (otherwise every box collapses into the top-left corner).
     * Assumes ImagePreprocessor stretches to 640×640; if it letterboxes, subtract the padding first.
     */
    fun drawDebugBoxes(
        originalBitmap: Bitmap,
        detections: List<Detection>
    ): Bitmap {
        val debugBitmap = originalBitmap.copy(Bitmap.Config.ARGB_8888, true)
        val canvas = Canvas(debugBitmap)
        val w = debugBitmap.width.toFloat()
        val h = debugBitmap.height.toFloat()

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
            val l = det.box.left * w
            val t = det.box.top * h
            val r = det.box.right * w
            val b = det.box.bottom * h
            canvas.drawRect(l, t, r, b, boxPaint)
            canvas.drawText(det.className, l, (t - 10f).coerceAtLeast(textPaint.textSize), textPaint)
        }
        return debugBitmap
    }
}