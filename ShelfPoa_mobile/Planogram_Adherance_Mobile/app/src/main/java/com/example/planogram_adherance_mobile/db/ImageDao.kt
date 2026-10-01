package com.example.planogram_adherance_mobile.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query

@Dao
interface ImageDao {
    @Insert
    suspend fun insertImage(image: ImageEntity)

    @Query("SELECT * FROM images WHERE imageId = :id LIMIT 1")
    suspend fun getImageById(id: Int): ImageEntity?
}
