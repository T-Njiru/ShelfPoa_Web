package com.example.planogram_adherance_mobile.models

import android.content.Context
import android.widget.Toast
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.DatabaseException
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener

/**
 * Offline-first report saving.
 *
 *  - init() turns on Firebase's disk persistence: every write is stored on the phone first and
 *    uploaded when there is a connection -- even if the app is closed and reopened in between.
 *  - submit() therefore never waits for the network: it queues the report, tells the merchandiser
 *    whether it was sent or saved offline, and returns straight away.
 *  - If the server REJECTS a report (e.g. database rules deny the write), a toast says so instead of
 *    the report silently disappearing.
 *
 * Call OfflineSync.init() first thing in MainActivity.onCreate, before any other FirebaseDatabase use.
 */
object OfflineSync {
    @Volatile
    var isOnline = false
        private set
    private var started = false

    fun init() {
        if (started) return            // activity recreation (e.g. rotation) must not call it twice
        started = true
        val db = FirebaseDatabase.getInstance()
        try {
            db.setPersistenceEnabled(true)
        } catch (_: DatabaseException) { /* already enabled */ }
        db.reference.child("outlets_universe").keepSynced(true)  // outlet picker still works offline
        db.getReference(".info/connected").addValueEventListener(object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                isOnline = snapshot.getValue(Boolean::class.java) == true
            }
            override fun onCancelled(error: DatabaseError) {}
        })
    }

    fun submit(context: Context, node: String, report: Any) {
        val app = context.applicationContext
        val wasOnline = isOnline
        FirebaseDatabase.getInstance().reference.child(node).push().setValue(report)
            .addOnSuccessListener {
                if (!wasOnline) Toast.makeText(app, "Saved report uploaded", Toast.LENGTH_SHORT).show()
            }
            .addOnFailureListener { e ->
                Toast.makeText(app, "Report was rejected: ${e.message}", Toast.LENGTH_LONG).show()
            }
        Toast.makeText(
            app,
            if (wasOnline) "Report submitted"
            else "No connection - report saved on this phone and will upload automatically",
            Toast.LENGTH_LONG
        ).show()
    }
}