package com.example.planogram_adherance_mobile.models

import android.os.Parcelable
import kotlinx.parcelize.Parcelize

@Parcelize
data class Outlet(
    val id: String = "",
    val outlet_name: String = "",
    val group_name: String = "",
    val planogram_base64: String? = null
) : Parcelable {
    // This empty constructor is required for Firebase to work
    constructor() : this("", "", "", null)
}