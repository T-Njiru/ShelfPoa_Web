package com.example.planogram_adherance_mobile.ml

import android.content.Context
import ai.onnxruntime.*
import androidx.compose.ui.geometry.Rect
import java.nio.FloatBuffer

class OnnxYoloRunner(context: Context) {

    private val ortEnv = OrtEnvironment.getEnvironment()
    private val session: OrtSession

    // Note: With internal NMS, these act as secondary filters
    private val CONF_THRESHOLD = 0.35f

    private val labels = listOf(
        "BB CHOCO 100g", "BB CHOCO 1Kg", "BB CHOCO 250g", "BB CHOCO 500g",
        "BB ORI 100g", "BB ORI 1Kg", "BB ORI 250g", "BB ORI 500g",
        "BB S4B 100g", "BB S4B 1Kg", "BB S4B 250g", "BB S4B 500g",
        "BB VANILLA 1Kg", "BB VANILLA 250g", "BB VANILLA 500g", "OTHERS"
    )

    init {
        val modelBytes = context.assets.open("best_model.onnx").use { it.readBytes() }
        session = ortEnv.createSession(modelBytes)
    }

    fun infer(input: FloatArray): List<Detection> {
        val shape = longArrayOf(1, 3, 640, 640)
        val tensor = OnnxTensor.createTensor(ortEnv, FloatBuffer.wrap(input), shape)

        val results = session.run(mapOf(session.inputNames.first() to tensor))

        results.use {
            // Based on your Logcat, we only have 'output0'
            val output = it[0].value as Array<Array<FloatArray>>
            val raw = output[0] // This is shape [num_detections, 6]

            val detections = mutableListOf<Detection>()

            // In this format, each row is ONE detection: [x1, y1, x2, y2, score, class]
            for (i in raw.indices) {
                val row = raw[i]
                val score = row[4]
                val classId = row[5].toInt()

                if (score > CONF_THRESHOLD) {
                    detections.add(
                        Detection(
                            className = labels.getOrElse(classId) { "Unknown" },
                            confidence = score,
                            box = Rect(
                                left = row[0] / 640f,
                                top = row[1] / 640f,
                                right = row[2] / 640f,
                                bottom = row[3] / 640f
                            )
                        )
                    )
                }
            }

            // No manual NMS needed! The model already filtered it.
            return detections
        }
    }
}