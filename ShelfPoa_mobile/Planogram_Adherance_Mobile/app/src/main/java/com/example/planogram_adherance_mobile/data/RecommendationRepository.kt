package com.example.planogram_adherance_mobile.data

import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ServerValue
import com.google.firebase.database.ValueEventListener

/**
 * recommendations/{merchandiserUid}/{recId}
 *
 * Written by admins/managers from the web dashboard. Keyed by the target's uid, so the
 * database rules (auth.uid === $uid) guarantee a merchandiser can only ever read their own.
 * The merchandiser may only change: status, seenAt, completedAt, merchandiserNote.
 */
data class Recommendation(
    val id: String,
    val title: String,
    val message: String,
    val type: String,          // sos | copromo | restock (matches the web RecommendationMaker)
    val priority: String,      // high | medium | low
    val due: String,           // "Next visit" | "Within 24 hours" | "This week"
    val outletId: String,
    val outletName: String,
    val sku: String,
    val basis: String,         // why: the model output it came from, e.g. "FP-Growth — BB VANILLA 500g → Flour, lift 2.4x"
    val source: String,        // ml | manual
    val createdAt: Long,
    val createdByName: String,
    val status: String,        // new | seen | done | dismissed
    val completedAt: Long?,
    val note: String
) {
    val isOpen: Boolean get() = status == "new" || status == "seen"
}

object RecommendationRepository {

    private const val LIMIT = 100

    private fun node(uid: String) =
        FirebaseDatabase.getInstance().reference.child("recommendations").child(uid)

    /** Live updates (new recommendations appear without a refresh). Returns a function that stops listening. */
    fun listen(
        uid: String,
        onChange: (List<Recommendation>) -> Unit,
        onError: (String) -> Unit
    ): () -> Unit {
        if (uid.isEmpty()) {
            onError("Not signed in"); return {}
        }
        val query = node(uid).orderByChild("createdAt").limitToLast(LIMIT)
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                onChange(snapshot.children.mapNotNull(::parse).sortedByDescending { it.createdAt })
            }
            override fun onCancelled(error: DatabaseError) {
                onError(error.message)
            }
        }
        query.addValueEventListener(listener)
        return { query.removeEventListener(listener) }
    }

    fun markSeen(uid: String, recId: String) {
        node(uid).child(recId).updateChildren(
            mapOf("status" to "seen", "seenAt" to ServerValue.TIMESTAMP)
        )
    }

    /** status = "done" or "dismissed". Queued offline like OSA reports. */
    fun close(uid: String, recId: String, status: String, note: String) {
        node(uid).child(recId).updateChildren(
            mapOf(
                "status" to status,
                "completedAt" to ServerValue.TIMESTAMP,
                "merchandiserNote" to note.trim()
            )
        )
    }

    private fun parse(s: DataSnapshot): Recommendation? {
        val id = s.key ?: return null
        fun str(k: String) = s.child(k).getValue(String::class.java) ?: ""
        return Recommendation(
            id = id,
            title = str("title").ifEmpty { "Recommendation" },
            message = str("message"),
            type = str("type"),
            priority = str("priority").ifEmpty { "medium" },
            due = str("due"),
            outletId = str("outletId"),
            outletName = str("outletName"),
            sku = str("sku"),
            basis = str("basis"),
            source = str("source").ifEmpty { "manual" },
            createdAt = s.child("createdAt").getValue(Long::class.java) ?: 0L,
            createdByName = str("createdByName"),
            status = str("status").ifEmpty { "new" },
            completedAt = s.child("completedAt").getValue(Long::class.java),
            note = str("merchandiserNote")
        )
    }
}
