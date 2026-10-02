package com.example.planogram_adherance_mobile.ml

import androidx.compose.ui.geometry.Rect
import kotlin.math.abs
import kotlin.math.sqrt

object AdherenceCalculator {

    fun compute(
        planogram: List<Detection>,
        shelf: List<Detection>,
        distanceThreshold: Float = 0.2f // Max 20% screen distance deviation
    ): Float {
        if (planogram.isEmpty()) return 0f

        var totalScore = 0f
        val usedShelfIndices = mutableSetOf<Int>()

        // Sort both by position (top-to-bottom, left-to-right) to check "Order"
        val sortedP = planogram.sortedWith(compareBy({ it.box.top }, { it.box.left }))
        val sortedS = shelf.sortedWith(compareBy({ it.box.top }, { it.box.left }))

        for (i in sortedP.indices) {
            val p = sortedP[i]

            // Find the best physical match in the shelf detections
            var bestMatchIdx = -1
            var bestMatchScore = 0f

            for (j in sortedS.indices) {
                if (j in usedShelfIndices) continue
                val s = sortedS[j]

                if (p.className == s.className) {
                    // 1. Proximity Score (0.0 to 1.0)
                    val dist = calculateDistance(p.box, s.box)
                    val proximityScore = (1f - (dist / distanceThreshold)).coerceIn(0f, 1f)

                    // 2. Order/Neighbor Score
                    // Check if the previous item in the shelf matches the previous in planogram
                    var orderScore = 1.0f
                    if (i > 0 && j > 0) {
                        if (sortedP[i-1].className != sortedS[j-1].className) {
                            orderScore = 0.7f // Penalty for wrong neighbor
                        }
                    }

                    val combinedScore = (proximityScore * 0.6f) + (orderScore * 0.4f)

                    if (combinedScore > bestMatchScore) {
                        bestMatchScore = combinedScore
                        bestMatchIdx = j
                    }
                }
            }

            if (bestMatchIdx != -1) {
                totalScore += bestMatchScore
                usedShelfIndices.add(bestMatchIdx)
            }
        }

        // Final score accounts for Count (Priority 1)
        // If shelf has more or fewer items than planogram, it naturally dilutes the average
        return (totalScore / planogram.size) * 100f
    }

    private fun calculateDistance(rectA: Rect, rectB: Rect): Float {
        val centerAX = (rectA.left + rectA.right) / 2f
        val centerAY = (rectA.top + rectA.bottom) / 2f
        val centerBX = (rectB.left + rectB.right) / 2f
        val centerBY = (rectB.top + rectB.bottom) / 2f

        return sqrt(
            (centerAX - centerBX).pow(2) + (centerAY - centerBY).pow(2)
        )
    }

    // Extension for square
    private fun Float.pow(n: Int): Float = Math.pow(this.toDouble(), n.toDouble()).toFloat()
}