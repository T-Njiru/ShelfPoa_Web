package com.example.planogram_adherance_mobile.userI

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.planogram_adherance_mobile.models.AllowedDomains
import com.example.planogram_adherance_mobile.models.AuthUiState
import com.example.planogram_adherance_mobile.models.AuthViewModel
import com.example.planogram_adherance_mobile.models.CurrentUser
import com.example.planogram_adherance_mobile.ui.theme.AppCoral
import com.example.planogram_adherance_mobile.ui.theme.AppDarkBg
import com.example.planogram_adherance_mobile.ui.theme.AppTextWhite

// Auth-screen tokens not covered by the app theme.
internal val AuthFieldBg = Color(0xFF38373F)
internal val AuthMutedText = Color(0xFFA8A6AE)
internal val AuthErrorText = Color(0xFFE0605A)

/**
 * Sign-in screen: email + password (admin-created accounts) or "Continue with Google"
 * (Flora Food Group accounts, or accounts an admin has already set up). There is no self sign-up. Navigation is handled by the
 * caller (AppNav), matching the callback style used by SplashScreen.
 */
@Composable
fun LoginScreen(
    onLoginSuccess: () -> Unit,
    authViewModel: AuthViewModel = viewModel()
) {
    val context = LocalContext.current   // the Activity: Credential Manager needs it to show the picker
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }

    val uiState by authViewModel.uiState.collectAsState()

    LaunchedEffect(uiState) {
        if (uiState is AuthUiState.Success) {
            authViewModel.resetState()
            CurrentUser.load { onLoginSuccess() }  // NEW: fetch merchandiser_id before entering the app
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg)
            .padding(horizontal = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("Shelf Poa", color = AppCoral, fontSize = 28.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(4.dp))
        Text("Log in to your account", color = AppTextWhite, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(32.dp))

        OutlinedTextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("Work email") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            colors = authFieldColors(),
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(Modifier.height(14.dp))

        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            singleLine = true,
            visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            trailingIcon = {
                TextButton(onClick = { passwordVisible = !passwordVisible }) {
                    Text(if (passwordVisible) "Hide" else "Show", color = AuthMutedText, fontSize = 12.sp)
                }
            },
            colors = authFieldColors(),
            modifier = Modifier.fillMaxWidth()
        )

        if (uiState is AuthUiState.Error) {
            Spacer(Modifier.height(10.dp))
            Text((uiState as AuthUiState.Error).message, color = AuthErrorText, fontSize = 12.5.sp)
        }

        Spacer(Modifier.height(24.dp))

        Button(
            onClick = { authViewModel.login(email, password) },
            enabled = uiState !is AuthUiState.Loading,
            colors = ButtonDefaults.buttonColors(containerColor = AppCoral),
            shape = RoundedCornerShape(10.dp),
            modifier = Modifier.fillMaxWidth().height(48.dp)
        ) {
            if (uiState is AuthUiState.Loading) {
                CircularProgressIndicator(color = Color.Black, strokeWidth = 2.dp, modifier = Modifier.size(18.dp))
            } else {
                Text("Log in", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 15.sp)
            }
        }

        Spacer(Modifier.height(18.dp))
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            HorizontalDivider(Modifier.weight(1f), color = AuthFieldBg)
            Text("  or  ", color = AuthMutedText, fontSize = 12.sp)
            HorizontalDivider(Modifier.weight(1f), color = AuthFieldBg)
        }
        Spacer(Modifier.height(18.dp))

        OutlinedButton(
            onClick = { authViewModel.loginWithGoogle(context) },
            enabled = uiState !is AuthUiState.Loading,
            colors = ButtonDefaults.outlinedButtonColors(containerColor = Color.White, contentColor = Color.Black),
            shape = RoundedCornerShape(10.dp),
            modifier = Modifier.fillMaxWidth().height(48.dp)
        ) {
            Text("Continue with Google", fontWeight = FontWeight.Bold, fontSize = 15.sp)
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "For Flora Food Group Google accounts (${AllowedDomains.describe()}) and accounts your admin has set up.",
            color = AuthMutedText, fontSize = 11.5.sp
        )

        Spacer(Modifier.height(20.dp))
        Text(
            "No account? Ask your Flora Food Group admin to create or activate one.",
            color = AuthMutedText, fontSize = 12.sp
        )
    }
}

@Composable
internal fun authFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedContainerColor = AuthFieldBg,
    unfocusedContainerColor = AuthFieldBg,
    focusedBorderColor = AppCoral,
    unfocusedBorderColor = AuthFieldBg,
    focusedLabelColor = AppCoral,
    unfocusedLabelColor = AuthMutedText,
    focusedTextColor = AppTextWhite,
    unfocusedTextColor = AppTextWhite,
    cursorColor = AppCoral
)