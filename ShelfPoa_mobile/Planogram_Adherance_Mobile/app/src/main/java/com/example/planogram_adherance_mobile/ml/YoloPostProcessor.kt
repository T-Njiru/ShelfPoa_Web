package com.example.planogram_adherance_mobile.ml

import androidx.compose.ui.geometry.Rect
import kotlin.math.max
import kotlin.math.min

class YoloPostProcessor(
    private val labels: List<String>,
    private val confThreshold: Float = 0.4f,
    private val iouThreshold: Float = 0.5f
) {

    fun process(
        output: Array<FloatArray>,
        imageWidth: Int,
        imageHeight: Int
    ): List<Detection> {

        val detections = mutableListOf<Detection>()

        for (pred in output) {
            val objConf = pred[4]
            if (objConf < confThreshold) continue

            val classScores = pred.copyOfRange(5, pred.size)

            var maxScore = 0f
            var classIndex = 0

            for (i in classScores.indices) {
                if (classScores[i] > maxScore) {
                    maxScore = classScores[i]
                    classIndex = i
                }
            }

            val confidence = objConf * maxScore
            if (confidence < confThreshold) continue

            val cx = pred[0]
            val cy = pred[1]
            val w = pred[2]
            val h = pred[3]

            val scaleX = imageWidth / 640f
            val scaleY = imageHeight / 640f

            val left = max(0f, (cx - w / 2f) * scaleX)
            val top = max(0f, (cy - h / 2f) * scaleY)
            val right = min(imageWidth.toFloat(), (cx + w / 2f) * scaleX)
            val bottom = min(imageHeight.toFloat(), (cy + h / 2f) * scaleY)

            detections.add(
                Detection(
                    className = labels.getOrElse(classIndex) { "unknown" },
                    confidence = confidence,
                    box = Rect(left, top, right, bottom)
                )
            )
        }

        return nonMaxSuppression(detections)
    }

    private fun nonMaxSuppression(detections: List<Detection>): List<Detection> {
        val result = mutableListOf<Detection>()
        val sorted = detections.sortedByDescending { it.confidence }.toMutableList()

        while (sorted.isNotEmpty()) {
            val best = sorted.removeAt(0)
            result.add(best)

            val iterator = sorted.iterator()
            while (iterator.hasNext()) {
                val other = iterator.next()
                if (iou(best.box, other.box) > iouThreshold) {
                    iterator.remove()
                }
            }
        }

        return result
    }

    private fun iou(a: Rect, b: Rect): Float {
        val left = max(a.left, b.left)
        val top = max(a.top, b.top)
        val right = min(a.right, b.right)
        val bottom = min(a.bottom, b.bottom)

        val intersection = max(0f, right - left) * max(0f, bottom - top)
        val union = (a.width * a.height) + (b.width * b.height) - intersection

        return if (union <= 0f) 0f else intersection / union
    }
}
