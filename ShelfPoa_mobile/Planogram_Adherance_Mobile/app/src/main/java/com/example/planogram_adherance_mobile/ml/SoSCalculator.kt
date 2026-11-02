package com.example.planogram_adherance_mobile.ml

object SoSCalculator {

    /**
     * Single KPI pass mark (%), used by the screen and the saved status.
     * TODO: confirm the source of this target (e.g. Flora Food Group) for the report.
     */
    const val PASS_THRESHOLD = 20f

    /**
     * Share of Shelf by AREA (the reported KPI):
     * Blueband box area / total detected box area x 100.
     * Any class other than "OTHERS" counts as Blueband.
     */
    fun calculate(detections: List<Detection>): Float {
        if (detections.isEmpty()) return 0f

        var bluebandArea = 0f
        var totalArea = 0f

        detections.forEach { detection ->
            val area = detection.box.width * detection.box.height
            totalArea += area
            if (detection.className != "OTHERS") bluebandArea += area
        }

        if (totalArea == 0f) return 0f
        return ((bluebandArea / totalArea) * 100f).coerceIn(0f, 100f)
    }

    /**
     * Alternative: share by FACINGS (Blueband facings / all detected facings).
     * Not the reported KPI; kept for comparison only.
     */
    fun calculateByCount(detections: List<Detection>): Float {
        if (detections.isEmpty()) return 0f
        val bluebandCount = detections.count { it.className != "OTHERS" }
        return (bluebandCount.toFloat() / detections.size.toFloat()) * 100f
    }

    fun isPass(score: Float): Boolean = score >= PASS_THRESHOLD
}