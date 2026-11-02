package com.example.planogram_adherance_mobile.data

import com.example.planogram_adherance_mobile.ml.OSA
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.FirebaseDatabase

/** One current stock-out: the latest OSA reading for (outlet, SKU) says unavailable. */
data class StockoutAlert(
    val outletId: String,
    val outletName: String,
    val sku: String,
    val lastReportedAt: Long,
    val reportedBy: String      // uid of whoever submitted the latest reading
)

/**
 * Reads osa_reports straight from Realtime Database (same rule as /api/stockouts):
 * an alert is current only if the LATEST reading for that outlet+SKU is "unavailable",
 * so repeat audits don't duplicate it and restocked SKUs drop off.
 */
object StockoutRepository {

    /** Recent records to scan. Raise if outlets go unaudited for long stretches. */
    private const val WINDOW = 500

    /**
     * @param reportedBy if set, keep only alerts whose latest reading came from this uid
     *                   ("stock-outs I reported that are still open").
     */
    fun load(
        onResult: (List<StockoutAlert>) -> Unit,
        onError: (String) -> Unit,
        reportedBy: String? = null
    ) {
        FirebaseDatabase.getInstance().reference
            .child("osa_reports")
            .orderByKey()
            .limitToLast(WINDOW)
            .get()
            .addOnSuccessListener { snap ->
                val all = compute(snap)
                onResult(if (reportedBy == null) all else all.filter { it.reportedBy == reportedBy })
            }
            .addOnFailureListener { onError(it.message ?: "Couldn't load stock-outs") }
    }

    private data class Reading(val outletName: String, val timestamp: Long, val available: Boolean, val uid: String)

    private fun compute(snap: DataSnapshot): List<StockoutAlert> {
        val latest = HashMap<Pair<String, String>, Reading>()

        for (rec in snap.children) {
            val outletId = rec.child("outletId").getValue(String::class.java) ?: continue
            val outletName = rec.child("outletName").getValue(String::class.java) ?: outletId
            val ts = rec.child("timestamp").getValue(Long::class.java) ?: continue
            val uid = rec.child("uid").getValue(String::class.java) ?: ""

            val availability: Map<String, Boolean> = when {
                // Current app: explicit per-SKU availability
                rec.hasChild("availability") ->
                    rec.child("availability").children.associate {
                        it.key!! to (it.getValue(Boolean::class.java) ?: false)
                    }
                // Older app: SKU missing from skuCounts = out of stock
                rec.hasChild("skuCounts") -> {
                    val counts = rec.child("skuCounts").children.associate {
                        it.key!! to (it.getValue(Long::class.java) ?: 0L)
                    }
                    OSA.EXPECTED_SKUS.associateWith { (counts[it] ?: 0L) > 0 }
                }
                // No SKU data (pre-fix empty-shelf records, seeded rows) — skip
                else -> continue
            }

            for ((sku, available) in availability) {
                if (sku !in OSA.EXPECTED_SKUS) continue
                val key = outletId to sku
                val current = latest[key]
                if (current == null || ts > current.timestamp) {
                    latest[key] = Reading(outletName, ts, available, uid)
                }
            }
        }

        return latest
            .filterValues { !it.available }
            .map { (key, r) -> StockoutAlert(key.first, r.outletName, key.second, r.timestamp, r.uid) }
            .sortedByDescending { it.lastReportedAt }
    }
}
