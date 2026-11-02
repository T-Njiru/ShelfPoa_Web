package com.example.planogram_adherance_mobile.ml

import android.graphics.Bitmap
import android.graphics.Color

/** Cheap photo-quality checks run before the model, so bad photos get a clear message. */
object ImageCheck {

    /** Average brightness 0-255, sampled on a small copy of the image (fast even for 12 MP photos). */
    fun meanBrightness(bitmap: Bitmap): Double {
        val small = Bitmap.createScaledBitmap(bitmap, 64, 64, true)
        var sum = 0.0
        for (y in 0 until small.height) for (x in 0 until small.width) {
            val p = small.getPixel(x, y)
            sum += 0.299 * Color.red(p) + 0.587 * Color.green(p) + 0.114 * Color.blue(p)  // perceived luminance
        }
        val pixels = small.width * small.height
        if (small !== bitmap) small.recycle()
        return sum / pixels
    }

    /** Too dark for reliable detection (threshold chosen for indoor shelf photos; tune if needed). */
    fun isTooDark(bitmap: Bitmap, threshold: Double = 40.0) = meanBrightness(bitmap) < threshold
}

