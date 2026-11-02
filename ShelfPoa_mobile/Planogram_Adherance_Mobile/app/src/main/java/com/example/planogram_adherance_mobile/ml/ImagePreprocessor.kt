package com.example.planogram_adherance_mobile.ml

import android.graphics.Bitmap
import android.os.SystemClock
import android.util.Log

object ImagePreprocessor {

    private const val INPUT_SIZE = 640
    private const val TAG = "ShelfPoaTiming"

    /**
     * Converts a bitmap into the 1x3x640x640 float tensor YOLOv8 expects.
     *
     * The image is STRETCHED to 640x640 (no letterbox padding) to match the
     * Roboflow "Resize to 640x640 (Stretch)" preprocessing the model was trained on.
     * Detection boxes (divided by 640 in OnnxYoloRunner) are therefore normalised
     * to the full original image: multiply x by image width and y by image height
     * to get pixel coordinates.
     */
    fun preprocess(bitmap: Bitmap): FloatArray {
        val t0 = SystemClock.elapsedRealtime()

        val resized = Bitmap.createScaledBitmap(bitmap, INPUT_SIZE, INPUT_SIZE, true)

        // Read all pixels in one call (much faster than getPixel() per pixel)
        val pixels = IntArray(INPUT_SIZE * INPUT_SIZE)
        resized.getPixels(pixels, 0, INPUT_SIZE, 0, 0, INPUT_SIZE, INPUT_SIZE)

        val channelSize = INPUT_SIZE * INPUT_SIZE
        val input = FloatArray(3 * channelSize)

        // CHW layout, RGB, scaled to 0..1 (same ordering as before)
        for (i in pixels.indices) {
            val p = pixels[i]
            input[i] = ((p shr 16) and 0xFF) / 255f                    // R
            input[i + channelSize] = ((p shr 8) and 0xFF) / 255f      // G
            input[i + channelSize * 2] = (p and 0xFF) / 255f          // B
        }

        // createScaledBitmap returns the same object if the input is already 640x640
        if (resized !== bitmap) resized.recycle()

        Log.d(TAG, "preprocess=${SystemClock.elapsedRealtime() - t0}")
        return input
    }
}