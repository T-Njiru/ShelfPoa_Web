package com.example.planogram_adherance_mobile.ml

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color

object ImagePreprocessor {

    private const val INPUT_SIZE = 640

    fun preprocess(bitmap: Bitmap): FloatArray {

        val resized = letterbox(bitmap)

        val input = FloatArray(1 * 3 * INPUT_SIZE * INPUT_SIZE)

        val channelSize = INPUT_SIZE * INPUT_SIZE

        var index = 0

        for (y in 0 until INPUT_SIZE) {
            for (x in 0 until INPUT_SIZE) {

                val pixel = resized.getPixel(x, y)

                val r = ((pixel shr 16) and 0xFF) / 255f
                val g = ((pixel shr 8) and 0xFF) / 255f
                val b = (pixel and 0xFF) / 255f

                input[index] = r
                input[index + channelSize] = g
                input[index + channelSize * 2] = b

                index++
            }
        }

        return input
    }

    private fun letterbox(bitmap: Bitmap): Bitmap {

        val width = bitmap.width
        val height = bitmap.height

        val scale = minOf(
            INPUT_SIZE.toFloat() / width,
            INPUT_SIZE.toFloat() / height
        )

        val newW = (width * scale).toInt()
        val newH = (height * scale).toInt()

        val resized = Bitmap.createScaledBitmap(
            bitmap,
            newW,
            newH,
            true
        )

        val output = Bitmap.createBitmap(
            INPUT_SIZE,
            INPUT_SIZE,
            Bitmap.Config.ARGB_8888
        )

        val canvas = Canvas(output)

        // IMPORTANT: YOLO default padding color
        canvas.drawColor(Color.rgb(114, 114, 114))

        val padX = (INPUT_SIZE - newW) / 2f
        val padY = (INPUT_SIZE - newH) / 2f

        canvas.drawBitmap(resized, padX, padY, null)

        return output
    }
}