package com.example.planogram_adherance_mobile.db
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "images")
data class ImageEntity(
    @PrimaryKey(autoGenerate = true) val imageId: Int = 0,
    val filepath: String,
    val type: String // "planogram" or "shelf"
)
