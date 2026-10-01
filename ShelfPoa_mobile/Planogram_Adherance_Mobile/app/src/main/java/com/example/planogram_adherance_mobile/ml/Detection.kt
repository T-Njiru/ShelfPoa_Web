package com.example.planogram_adherance_mobile.ml

import androidx.compose.ui.geometry.Rect

data class Detection(
    val className: String,
    val confidence: Float,
    val box: Rect
)
