package com.example.planogram_adherance_mobile.data

import android.util.Log
import com.example.planogram_adherance_mobile.ml.OSA
import com.example.planogram_adherance_mobile.ml.SkuStatus
import com.example.planogram_adherance_mobile.models.CurrentUser
import com.example.planogram_adherance_mobile.models.Outlet
import com.google.firebase.database.FirebaseDatabase

/**
 * Writes OSA reports to Realtime Database.
 *
 * Record shape (backward compatible with /api/stockouts → normalize.osa_readings):
 *   skuCounts       – CONFIRMED facings per available SKU. The backend treats a SKU absent
 *                     from here as out of stock, so merchandiser overrides take effect
 *                     without any backend change.
 *   detectedCounts  – raw YOLO counts, kept for model-accuracy analysis (Chapter 5).
 *   availability    – explicit {sku: true/false} for every expected SKU. Always non-empty,
 *                     so an empty shelf still produces a full record (Firebase drops empty maps).
 *   overrides       – {sku: confirmedValue} only where the merchandiser disagreed with YOLO.
 */
object OsaRepository {

    private const val TAG = "OsaRepository"

    /**
     * Queues the report and returns its push key immediately.
     * With disk persistence enabled the write is stored locally and syncs when the device
     * is back online, so callers must NOT wait for completion (it won't fire while offline).
     */
    fun submit(
        outlet: Outlet,
        statuses: List<SkuStatus>,
        onRejected: (String) -> Unit = {}   // shown to the merchandiser, e.g. as a toast
    ): String? {
        val ref = FirebaseDatabase.getInstance().reference.child("osa_reports").push()

        val report = mapOf(
            "timestamp" to System.currentTimeMillis(),   // capture time, not sync time
            "outletId" to outlet.id,
            "outletName" to outlet.outlet_name,
            "groupName" to outlet.group_name,
            "uid" to CurrentUser.uid,
            "merchandiserId" to CurrentUser.merchandiserId,
            "auditId" to CurrentUser.auditIdFor(outlet.id),
            "source" to "mobile",
            "skuCounts" to statuses
                .filter { it.available }
                .associate { it.sku to maxOf(it.facings, 1) },  // manual "in stock" = at least 1 facing
            "detectedCounts" to statuses
                .filter { it.facings > 0 }
                .associate { it.sku to it.facings },
            "availability" to statuses.associate { it.sku to it.available },
            "overrides" to statuses
                .filter { it.overridden }
                .associate { it.sku to it.available },
            "osaPercent" to OSA.osaPercent(statuses)
        )

        ref.setValue(report).addOnFailureListener { e ->
            // Fires on rule rejection (e.g. user lacks the merchandiser role) once the server answers
            Log.e(TAG, "OSA report ${ref.key} rejected: ${e.message}")
            onRejected(e.message ?: "permission denied")
        }
        return ref.key
    }
}