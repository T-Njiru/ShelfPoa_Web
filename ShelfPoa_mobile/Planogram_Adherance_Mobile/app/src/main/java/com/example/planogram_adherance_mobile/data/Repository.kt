package com.example.planogram_adherance_mobile.data

import android.graphics.Bitmap
import androidx.room.*
import kotlinx.coroutines.flow.Flow

// 1️⃣ Room Entity for saved planograms or shelf captures
@Entity(tableName = "planogram_table")
data class PlanogramEntity(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val name: String,
    val bitmap: ByteArray, // store image as byte array
    val adherence: Float
)

// 2️⃣ DAO
@Dao
interface PlanogramDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(planogram: PlanogramEntity)

    @Query("SELECT * FROM planogram_table ORDER BY id DESC")
    fun getAllPlanograms(): Flow<List<PlanogramEntity>>

    @Delete
    suspend fun delete(planogram: PlanogramEntity)
}

// 3️⃣ Repository class
class PlanogramRepository(private val dao: PlanogramDao) {

    // Expose all planograms as Flow
    val allPlanograms: Flow<List<PlanogramEntity>> = dao.getAllPlanograms()

    // Insert a new planogram
    suspend fun insertPlanogram(planogram: PlanogramEntity) {
        dao.insert(planogram)
    }

    // Delete a planogram
    suspend fun deletePlanogram(planogram: PlanogramEntity) {
        dao.delete(planogram)
    }
}
