package com.example.planogram_adherance_mobile.userI

import android.graphics.Bitmap
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.ViewModel
import com.example.planogram_adherance_mobile.ml.Detection

class PlanogramViewModel : ViewModel() {
    var planogramBitmap = mutableStateOf<Bitmap?>(null)
    var shelfBitmap = mutableStateOf<Bitmap?>(null)
    var detections = mutableStateOf<List<Detection>>(emptyList())
    var adherence = mutableStateOf(0f)
}
