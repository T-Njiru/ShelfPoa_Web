package com.example.planogram_adherance_mobile.data

import com.example.planogram_adherance_mobile.ml.OSA
import com.google.android.gms.tasks.Tasks
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.FirebaseDatabase

enum class CaptureType(val label: String) { OSA("OSA"), SOS("Share of Shelf"), COMPLIANCE("Planogram") }

/** One capture the merchandiser submitted. score is 0–100, or null if the record has none. */
data class Capture(
    val type: CaptureType,
    val outletId: String,
    val outletName: String,
    val score: Double?,
    val timestamp: Long,
    val auditId: String
)

data class MerchStats(
    val osaAvg: Double?,
    val sosAvg: Double?,
    val complianceAvg: Double?,
    val osaCount: Int,
    val sosCount: Int,
    val complianceCount: Int,
    val visits: Int,         // distinct auditIds (one outlet visit = one id, see CurrentUser.auditIdFor)
    val outlets: Int,        // distinct outlets audited
    val recent: List<Capture>
)

/**
 * The signed-in merchandiser's own captures, read directly from Realtime Database.
 * Filters each node by uid server-side (needs ".indexOn": ["uid"] in the rules,
 * otherwise Firebase downloads the whole node and logs a warning).
 */
object DashboardRepository {

    fun load(
        uid: String,
        sinceMs: Long,
        onResult: (MerchStats) -> Unit,
        onError: (String) -> Unit
    ) {
        if (uid.isEmpty()) {
            onError("Not signed in"); return
        }
        val db = FirebaseDatabase.getInstance().reference
        fun mine(node: String) = db.child(node).orderByChild("uid").equalTo(uid).get()

        Tasks.whenAllSuccess<DataSnapshot>(mine("osa_reports"), mine("sos_audits"), mine("audits"))
            .addOnSuccessListener { (osa, sos, audits) -> onResult(build(osa, sos, audits, sinceMs)) }
            .addOnFailureListener { onError(it.message ?: "Couldn't load your performance") }
    }

    private fun build(osa: DataSnapshot, sos: DataSnapshot, audits: DataSnapshot, sinceMs: Long): MerchStats {
        val captures = buildList {
            osa.children.forEach { r -> capture(r, CaptureType.OSA, osaScore(r))?.let(::add) }
            sos.children.forEach { r -> capture(r, CaptureType.SOS, pct(num(r, "coverageScore")))?.let(::add) }
            audits.children.forEach { r -> capture(r, CaptureType.COMPLIANCE, pct(num(r, "adherenceScore")))?.let(::add) }
        }.filter { it.timestamp >= sinceMs }
            .sortedByDescending { it.timestamp }

        fun avg(type: CaptureType) =
            captures.filter { it.type == type }.mapNotNull { it.score }.takeIf { it.isNotEmpty() }?.average()

        return MerchStats(
            osaAvg = avg(CaptureType.OSA),
            sosAvg = avg(CaptureType.SOS),
            complianceAvg = avg(CaptureType.COMPLIANCE),
            osaCount = captures.count { it.type == CaptureType.OSA },
            sosCount = captures.count { it.type == CaptureType.SOS },
            complianceCount = captures.count { it.type == CaptureType.COMPLIANCE },
            visits = captures.map { it.auditId }.distinct().size,
            outlets = captures.map { it.outletId }.filter { it.isNotEmpty() }.distinct().size,
            recent = captures.take(10)
        )
    }

    private fun capture(r: DataSnapshot, type: CaptureType, score: Double?): Capture? {
        val ts = r.child("timestamp").getValue(Long::class.java) ?: return null
        val outletId = r.child("outletId").getValue(String::class.java) ?: ""
        return Capture(
            type = type,
            outletId = outletId,
            outletName = r.child("outletName").getValue(String::class.java) ?: outletId,
            score = score,
            timestamp = ts,
            auditId = r.child("auditId").getValue(String::class.java) ?: r.key.orEmpty()
        )
    }

    /** OSA %: stored osaPercent (current app), else derived from availability / skuCounts. */
    private fun osaScore(r: DataSnapshot): Double? {
        num(r, "osaPercent")?.let { return it }
        val skus = OSA.EXPECTED_SKUS
        val onShelf = when {
            r.hasChild("availability") ->
                skus.count { r.child("availability").child(it).getValue(Boolean::class.java) == true }
            r.hasChild("skuCounts") ->
                skus.count { (r.child("skuCounts").child(it).getValue(Long::class.java) ?: 0L) > 0 }
            else -> return null
        }
        return onShelf * 100.0 / skus.size
    }

    private fun num(r: DataSnapshot, key: String): Double? = (r.child(key).value as? Number)?.toDouble()

    /**
     * Scores may be stored as a fraction (0–1) or a percentage (0–100) depending on the screen
     * that wrote them. TODO: confirm SoSCalculator / AdherenceCalculator output range and drop this.
     */
    private fun pct(v: Double?): Double? = v?.let { if (it <= 1.0) it * 100 else it }
}
