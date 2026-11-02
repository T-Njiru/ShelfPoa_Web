package com.example.planogram_adherance_mobile.models

import android.os.Handler
import android.os.Looper
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener

/**
 * Who is signed in, and which store visit is in progress.
 * Every report the app writes stamps uid + merchandiserId + auditId from here, so the
 * website can credit it to a merchandiser and group OSA + SOS + planogram into one visit.
 *
 *  - call CurrentUser.load { ... } after login AND wherever the app resumes an existing
 *    session (e.g. SplashScreen when FirebaseAuth.currentUser != null)
 *  - call CurrentUser.clear() on logout
 */
object CurrentUser {
    var uid: String = ""
        private set
    var merchandiserId: String = ""
        private set
    var displayName: String = ""
        private set

    private var visitOutletId = ""
    private var visitId = ""
    private var visitStartedAt = 0L
    private const val VISIT_WINDOW_MS = 2 * 60 * 60 * 1000L  // captures at one outlet within 2 h = one visit

    /** Reads users/{uid}. Works offline from the phone's cache (persistence is on); onDone always
     *  runs -- at the latest after 4 s -- so login/splash never hangs without signal. */
    fun load(onDone: () -> Unit) {
        val user = FirebaseAuth.getInstance().currentUser
        if (user == null) {
            onDone(); return
        }
        uid = user.uid
        var finished = false
        val finish = {
            if (!finished) { finished = true; onDone() }
        }
        val ref = FirebaseDatabase.getInstance().reference.child("users").child(uid)
        ref.keepSynced(true)  // keep this user's record cached for offline launches
        ref.addListenerForSingleValueEvent(object : ValueEventListener {
            override fun onDataChange(snap: DataSnapshot) {
                merchandiserId = snap.child("merchandiser_id").getValue(String::class.java) ?: ""
                displayName = snap.child("display_name").getValue(String::class.java) ?: ""
                finish()
            }
            override fun onCancelled(error: DatabaseError) = finish()
        })
        Handler(Looper.getMainLooper()).postDelayed({ finish() }, 4000)
    }

    /** Same id for every capture at one outlet within 2 hours; a new outlet starts a new visit. */
    fun auditIdFor(outletId: String): String {
        val now = System.currentTimeMillis()
        if (visitId.isEmpty() || outletId != visitOutletId || now - visitStartedAt > VISIT_WINDOW_MS) {
            visitOutletId = outletId
            visitStartedAt = now
            visitId = "${merchandiserId.ifEmpty { uid }}-$outletId-$now"
        }
        return visitId
    }

    fun clear() {
        uid = ""; merchandiserId = ""; displayName = ""
        visitOutletId = ""; visitId = ""; visitStartedAt = 0L
    }
}