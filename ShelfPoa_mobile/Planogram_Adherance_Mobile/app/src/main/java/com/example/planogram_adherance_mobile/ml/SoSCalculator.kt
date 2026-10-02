package com.example.planogram_adherance_mobile.ml

object SoSCalculator {

    /**
     * Calculates Share of Shelf based on Area.
     * Your Brand Area / (Your Brand Area + Competitor Area)
     */
    fun calculate(detections: List<Detection>): Float {
        if (detections.isEmpty()) return 0f

        var yourBrandArea = 0f
        var totalCategoryArea = 0f

        detections.forEach { detection ->
            val area = detection.box.width * detection.box.height

            // Accumulate Total Category (everything the model saw)
            totalCategoryArea += area

            // Accumulate Your Brand (anything not labeled OTHERS)
            if (detection.className != "OTHERS") {
                yourBrandArea += area
            }
        }

        if (totalCategoryArea == 0f) return 0f

        val sosPercentage = (yourBrandArea / totalCategoryArea) * 100f
        return sosPercentage.coerceIn(0f, 100f)
    }

    /**
     * Alternative: Calculate by SKU count (Facings)
     * Useful if boxes are overlapping or sizes are inconsistent.
     */
    fun calculateByCount(detections: List<Detection>): Float {
        if (detections.isEmpty()) return 0f

        val totalCount = detections.size
        val yourBrandCount = detections.count { it.className != "OTHERS" }

        return (yourBrandCount.toFloat() / totalCount.toFloat()) * 100f
    }

    // Set your KPI target here (e.g., 40% Share of Shelf is a Pass)
    fun isPass(score: Float): Boolean = score >= 40f
}