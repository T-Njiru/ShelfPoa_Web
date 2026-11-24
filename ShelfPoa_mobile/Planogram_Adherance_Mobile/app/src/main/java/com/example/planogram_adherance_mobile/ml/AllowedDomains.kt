package com.example.planogram_adherance_mobile.models

/**
 * "Continue with Google" is for Flora Food Group accounts, plus any account an admin has already
 * set up (AuthViewModel checks users/{uid} first; this list only decides which message a
 * not-yet-activated Google account sees). Keep the same as VITE_ALLOWED_EMAIL_DOMAINS (web) and
 * ALLOWED_EMAIL_DOMAINS (backend).
 */
object AllowedDomains {
    val DOMAINS = listOf("upfield.com", "florafoodgroup.com")

    fun isAllowed(email: String?): Boolean {
        val domain = email?.substringAfterLast('@', "")?.lowercase().orEmpty()
        return domain.isNotEmpty() && domain in DOMAINS
    }

    /** "@upfield.com or @florafoodgroup.com", for messages. */
    fun describe(): String = DOMAINS.joinToString(" or ") { "@$it" }
}