package com.example.planogram_adherance_mobile.models

import android.content.Context
import androidx.credentials.ClearCredentialStateRequest
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.firebase.FirebaseNetworkException
import com.google.firebase.Firebase
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.FirebaseAuthInvalidCredentialsException
import com.google.firebase.auth.FirebaseAuthInvalidUserException
import com.google.firebase.auth.GoogleAuthProvider
import com.google.firebase.auth.auth
import com.google.firebase.database.database
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withTimeoutOrNull

/**
 * UI state for LoginScreen.
 */
sealed class AuthUiState {
    object Idle : AuthUiState()
    object Loading : AuthUiState()
    object Success : AuthUiState()
    data class Error(val message: String) : AuthUiState()
}

/**
 * Backs LoginScreen. Two ways in, both straight against Firebase Auth:
 *  - email + password (accounts created by an admin; there is no self sign-up), and
 *  - "Continue with Google": Flora Food Group addresses (AllowedDomains), or any account an admin
 *    has already set up (e.g. an existing account's own Gmail).
 *
 * Either way the account must be ACTIVATED before the app opens: users/{uid} needs a role of
 * merchandiser (or admin/manager) and active != false. An admin activates a new Google account
 * after its first sign-in with:  python link_merchandiser.py --email <address> --yes
 * The Realtime Database rules enforce the same thing on every read and write.
 */
class AuthViewModel : ViewModel() {

    private val auth: FirebaseAuth = Firebase.auth

    private val _uiState = MutableStateFlow<AuthUiState>(AuthUiState.Idle)
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    val currentUser get() = auth.currentUser

    fun login(email: String, password: String) {
        if (email.isBlank() || password.isBlank()) {
            _uiState.value = AuthUiState.Error("Enter your email and password.")
            return
        }
        _uiState.value = AuthUiState.Loading
        viewModelScope.launch {
            try {
                auth.signInWithEmailAndPassword(email.trim(), password).await()
                finishSignIn()
            } catch (e: Exception) {
                _uiState.value = AuthUiState.Error(friendly(e))
            }
        }
    }

    /** Google account picker (Credential Manager) -> Firebase. [context] must be the Activity. */
    fun loginWithGoogle(context: Context) {
        val webClientId = webClientId(context)
        if (webClientId == null) {
            _uiState.value = AuthUiState.Error(
                "Google sign-in isn't set up in this build. Enable Google in Firebase Authentication, " +
                        "add the app's SHA-1, then replace app/google-services.json."
            )
            return
        }
        _uiState.value = AuthUiState.Loading
        viewModelScope.launch {
            try {
                val request = GetCredentialRequest.Builder()
                    .addCredentialOption(GetSignInWithGoogleOption.Builder(webClientId).build())
                    .build()
                val credential = CredentialManager.create(context).getCredential(context, request).credential
                if (credential !is CustomCredential ||
                    credential.type != GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
                ) {
                    _uiState.value = AuthUiState.Error("Couldn't sign in with Google. Try again.")
                    return@launch
                }
                val idToken = GoogleIdTokenCredential.createFrom(credential.data).idToken
                auth.signInWithCredential(GoogleAuthProvider.getCredential(idToken, null)).await()
                finishSignIn(context, viaGoogle = true)
            } catch (e: GetCredentialCancellationException) {
                _uiState.value = AuthUiState.Idle            // user closed the account picker
            } catch (e: NoCredentialException) {
                _uiState.value = AuthUiState.Error(
                    "No Google account on this phone. Add your work account in Settings > Accounts, then try again."
                )
            } catch (e: GetCredentialException) {
                _uiState.value = AuthUiState.Error("Couldn't open Google sign-in. Try again.")
            } catch (e: Exception) {
                _uiState.value = AuthUiState.Error(friendly(e))
            }
        }
    }

    /** Lets the user in only if users/{uid} has an app role and is active; otherwise signs out. */
    private suspend fun finishSignIn(context: Context? = null, viaGoogle: Boolean = false) {
        val user = auth.currentUser ?: run {
            _uiState.value = AuthUiState.Error("Sign-in failed. Try again."); return
        }
        val snap = runCatching {
            withTimeoutOrNull(8_000) { Firebase.database.reference.child("users").child(user.uid).get().await() }
        }.getOrNull()
        if (snap == null) {
            auth.signOut()
            _uiState.value = AuthUiState.Error("Couldn't check your account. Connect to the internet and try again.")
            return
        }
        val role = snap.child("role").getValue(String::class.java)
        val active = snap.child("active").getValue(Boolean::class.java) != false
        if (role == null || role !in APP_ROLES || !active) {
            if (context != null) signOut(context) else auth.signOut()
            val ffg = user.isEmailVerified && AllowedDomains.isAllowed(user.email)
            _uiState.value = AuthUiState.Error(
                when {
                    !active -> "This account has been deactivated. Contact your ShelfPoa admin."
                    viaGoogle && !ffg ->
                        "Google sign-in is for Flora Food Group accounts (${AllowedDomains.describe()}) " +
                                "and accounts your admin has already set up."
                    else -> "${user.email ?: "This account"} isn't activated for ShelfPoa yet. Ask your admin to activate it."
                }
            )
            return
        }
        _uiState.value = AuthUiState.Success
    }

    fun resetState() {
        _uiState.value = AuthUiState.Idle
    }

    companion object {
        private val APP_ROLES = setOf("merchandiser", "admin", "manager")

        /** Signs out of Firebase and forgets the chosen Google account, so the picker shows next time. */
        suspend fun signOut(context: Context) {
            Firebase.auth.signOut()
            runCatching { CredentialManager.create(context).clearCredentialState(ClearCredentialStateRequest()) }
        }

        /** OAuth web client id generated from google-services.json (null until Google sign-in is enabled). */
        private fun webClientId(context: Context): String? {
            val id = context.resources.getIdentifier("default_web_client_id", "string", context.packageName)
            return if (id == 0) null else context.getString(id).takeIf { it.isNotBlank() }
        }

        private fun friendly(e: Exception): String = when (e) {
            is FirebaseAuthInvalidUserException,
            is FirebaseAuthInvalidCredentialsException -> "Wrong email or password."
            is FirebaseNetworkException -> "No connection. Connect to the internet to sign in."
            else -> "Sign-in failed. Try again."
        }
    }
}