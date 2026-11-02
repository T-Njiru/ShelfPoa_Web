package com.example.planogram_adherance_mobile.models

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.Firebase
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.auth
import com.google.firebase.database.database
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

/**
 * UI state shared by LoginScreen and SignupScreen.
 */
sealed class AuthUiState {
    object Idle : AuthUiState()
    object Loading : AuthUiState()
    object Success : AuthUiState()
    data class Error(val message: String) : AuthUiState()
}

/**
 * Backs LoginScreen and SignupScreen. Talks directly to Firebase Auth (account
 * creation/login is implemented straight against Firebase per the project's
 * architecture) and writes a profile record to Realtime Database on signup.
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
                _uiState.value = AuthUiState.Success
            } catch (e: Exception) {
                _uiState.value = AuthUiState.Error(
                    e.localizedMessage ?: "Login failed. Check your details and try again."
                )
            }
        }
    }

    fun signup(fullName: String, email: String, password: String, confirmPassword: String) {
        if (fullName.isBlank() || email.isBlank() || password.isBlank()) {
            _uiState.value = AuthUiState.Error("Fill in all fields.")
            return
        }
        if (password != confirmPassword) {
            _uiState.value = AuthUiState.Error("Passwords don't match.")
            return
        }
        if (password.length < 6) {
            _uiState.value = AuthUiState.Error("Password must be at least 6 characters.")
            return
        }
        _uiState.value = AuthUiState.Loading
        viewModelScope.launch {
            try {
                val result = auth.createUserWithEmailAndPassword(email.trim(), password).await()
                val uid = result.user?.uid
                if (uid != null) {
                    // TODO: confirm the real Realtime Database node name for merchandiser
                    // profiles before shipping. "merchandisers" is a placeholder guess —
                    // it isn't one of the confirmed top-level nodes (audits, mt_groups,
                    // osa_reports, outlets_universe, sos_audits), so check the Firebase
                    // console / firebase.py before relying on it elsewhere.
                    val profile = mapOf(
                        "fullName" to fullName.trim(),
                        "email" to email.trim(),
                        "createdAt" to System.currentTimeMillis()
                    )
                    Firebase.database.reference
                        .child("merchandisers")
                        .child(uid)
                        .setValue(profile)
                        .await()
                }
                _uiState.value = AuthUiState.Success
            } catch (e: Exception) {
                _uiState.value = AuthUiState.Error(
                    e.localizedMessage ?: "Sign up failed. Try again."
                )
            }
        }
    }

    fun resetState() {
        _uiState.value = AuthUiState.Idle
    }

    fun signOut() {
        auth.signOut()
    }
}