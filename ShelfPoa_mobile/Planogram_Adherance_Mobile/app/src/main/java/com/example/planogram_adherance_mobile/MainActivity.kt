package com.example.planogram_adherance_mobile

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.example.planogram_adherance_mobile.ml.*
import com.example.planogram_adherance_mobile.userI.*
import com.example.planogram_adherance_mobile.ui.theme.*
import com.example.planogram_adherance_mobile.models.CurrentUser
import com.example.planogram_adherance_mobile.models.OfflineSync
import com.example.planogram_adherance_mobile.models.Outlet // IMPORTANT: Check this path
import com.google.firebase.Firebase
import com.google.firebase.auth.auth
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Offline support: must run before anything else touches the database.
        // Enables disk persistence (reports queue on the phone and sync on reconnect), keeps the
        // outlet list cached, and tracks online/offline so submit screens can say which happened.
        OfflineSync.init()

        val requestPermissionLauncher = registerForActivityResult(
            ActivityResultContracts.RequestPermission()
        ) { _ -> }
        requestPermissionLauncher.launch(android.Manifest.permission.CAMERA)

        setContent {
            Planogram_Adherance_MobileTheme {
                AppNav(this)
            }
        }
    }
}

@Composable
fun AppNav(context: Context) {
    val navController = rememberNavController()
    val scope = rememberCoroutineScope()
    val yoloRunner = remember { OnnxYoloRunner(context) }

    // --- OUTLET STATE ---
    var selectedOutlet by remember { mutableStateOf<Outlet?>(null) }
    var pendingRoute by remember { mutableStateOf("") }

    // --- SHARED STATES ---
    var planogramBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var shelfBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var planogramDetections by remember { mutableStateOf<List<Detection>>(emptyList()) }
    var shelfDetections by remember { mutableStateOf<List<Detection>>(emptyList()) }
    var adherenceScore by remember { mutableFloatStateOf(0f) }
    var sosBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var sosScore by remember { mutableStateOf<Float?>(null) }   // null = not calculated yet (0% is a real result)
    var sosDetectedCount by remember { mutableIntStateOf(0) }
    var osaDebugBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var osaSkuCounts by remember { mutableStateOf<Map<String, Int>>(emptyMap()) }
    var osaBitmap by remember { mutableStateOf<Bitmap?>(null) }            // raw photo for the overlay
    var osaDetections by remember { mutableStateOf<List<Detection>>(emptyList()) }

    // --- ERROR HANDLING ---
    // Every model run goes through here: warns about very dark photos, runs YOLO off the main thread,
    // and turns any failure (unreadable image, model error) into a message instead of a crash.
    fun analyse(bitmap: Bitmap, onFail: () -> Unit = {}, onDetections: (List<Detection>) -> Unit) {
        if (runCatching { ImageCheck.isTooDark(bitmap) }.getOrDefault(false)) {
            Toast.makeText(context, "This photo is very dark - results may be unreliable. Retake it with more light if you can.", Toast.LENGTH_LONG).show()
        }
        scope.launch(Dispatchers.Default) {
            val result = runCatching { yoloRunner.infer(ImagePreprocessor.preprocess(bitmap)) }
            withContext(Dispatchers.Main) {
                result
                    .onSuccess(onDetections)
                    .onFailure { e ->
                        Log.e("AppNav", "Model run failed", e)
                        Toast.makeText(context, "Couldn't analyse this photo. Try another one.", Toast.LENGTH_LONG).show()
                        onFail()
                    }
            }
        }
    }

    // OSA: detections -> annotated image + counts -> review screen
    fun showOsa(bitmap: Bitmap, detections: List<Detection>) {
        osaBitmap = bitmap
        osaDetections = detections
        osaDebugBitmap = null   // boxes are now drawn live by DetectionOverlay, not baked into the photo
        osaSkuCounts = OSA.calculateCounts(detections)
        navController.navigate("osa_view")
    }

    fun unreadable() = Toast.makeText(context, "Couldn't open that image. Choose a JPG or PNG photo.", Toast.LENGTH_LONG).show()

    // --- LAUNCHERS (Fixed Types) ---
    val pickPlanogram = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { decodeBitmap(context, it)?.let { b -> planogramBitmap = b } ?: unreadable() }
    }
    val pickShelf = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { decodeBitmap(context, it)?.let { b -> shelfBitmap = b } ?: unreadable() }
    }
    val pickSos = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { decodeBitmap(context, it)?.let { b -> sosBitmap = b; sosScore = null } ?: unreadable() }
    }
    val pickOsa = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { uriPath ->
            val bitmap = decodeBitmap(context, uriPath) ?: return@let unreadable()
            analyse(bitmap) { detections -> showOsa(bitmap, detections) }
        }
    }

    NavHost(navController = navController, startDestination = "splash") {

        composable("splash") {
            SplashScreen(onTimeout = {
                // Already signed in (Firebase keeps the session between launches) → skip login.
                if (Firebase.auth.currentUser != null) {
                    // NEW: restore merchandiser_id for the saved session before entering the app
                    CurrentUser.load {
                        navController.navigate("menu") { popUpTo("splash") { inclusive = true } }
                    }
                } else {
                    navController.navigate("login") { popUpTo("splash") { inclusive = true } }
                }
            })
        }

        composable("login") {
            LoginScreen(
                onLoginSuccess = {
                    // Load uid + merchandiser_id BEFORE entering the app, otherwise every report
                    // from this session is stamped with an empty uid until the app restarts.
                    CurrentUser.load {
                        navController.navigate("menu") { popUpTo("login") { inclusive = true } }
                    }
                },
                // Accounts are admin-provisioned from the web dashboard; self sign-up is disabled.
                // TODO: remove the "Sign up" link from LoginScreen, then this parameter.
                onNavigateToSignup = {}
            )
        }

        composable("menu") {
            MenuScreen(
                userEmail = Firebase.auth.currentUser?.email,
                onNavigateToShelf = {
                    pendingRoute = "planogram"
                    navController.navigate("outlets")
                },
                onNavigateToSOS = {
                    pendingRoute = "sos"
                    navController.navigate("outlets")
                },
                onNavigateToOSA = {
                    pendingRoute = "osa_entry"
                    navController.navigate("outlets")
                },
                onNavigateToDashboard = { navController.navigate("dashboard") },
                onNavigateToRecommendations = { navController.navigate("recommendations") },
                onNavigateToStockouts = { navController.navigate("stockouts") },
                onNavigateToHelp = { navController.navigate("help") },
                onSignOut = {
                    Firebase.auth.signOut()
                    CurrentUser.clear()  // NEW
                    selectedOutlet = null
                    navController.navigate("login") { popUpTo("menu") { inclusive = true } }
                }
            )
        }

        // TODO: replace these placeholders with the real Dashboard, Recommendations
        // and Stock-out screens as each module is built.
        composable("dashboard") {
            DashboardScreen(onBack = { navController.popBackStack() })
        }
        composable("recommendations") {
            RecommendationsScreen(onBack = { navController.popBackStack() })
        }
        composable("stockouts") {
            StockoutsScreen(onBack = { navController.popBackStack() })
        }

        composable("outlets") {
            OutletsScreen(
                onOutletSelected = { outlet ->
                    selectedOutlet = outlet
                    navController.navigate(pendingRoute)
                },
                onBack = { navController.popBackStack() }
            )
        }

        composable("planogram") {
            var isCameraMode by remember { mutableStateOf(false) }
            if (isCameraMode) {
                CameraCapture { bitmap -> planogramBitmap = bitmap; isCameraMode = false }
            } else {
                PlanogramScreen(
                    bitmap = planogramBitmap,
                    onCapture = { isCameraMode = true },
                    onGallery = { pickPlanogram.launch("image/*") },
                    onNext = {
                        planogramBitmap?.let { bitmap ->
                            analyse(bitmap) { detections ->
                                if (detections.isEmpty()) {
                                    Toast.makeText(context, "No products found in the planogram photo. Choose a clearer image of the planogram.", Toast.LENGTH_LONG).show()
                                } else {
                                    planogramDetections = detections
                                    navController.navigate("shelf")
                                }
                            }
                        }
                    }
                )
            }
        }

        composable("shelf") {
            var isCameraMode by remember { mutableStateOf(false) }
            if (isCameraMode) {
                CameraCapture { bitmap -> shelfBitmap = bitmap; isCameraMode = false }
            } else {
                ShelfScreen(
                    bitmap = shelfBitmap,
                    onCapture = { isCameraMode = true },
                    onGallery = { pickShelf.launch("image/*") },
                    onCompare = {
                        shelfBitmap?.let { bitmap ->
                            analyse(bitmap) { detections ->
                                if (detections.isEmpty()) {
                                    Toast.makeText(context, "No products found on the shelf photo. Make sure it shows the shelf and is well lit.", Toast.LENGTH_LONG).show()
                                }
                                // still scored: an empty shelf against the planogram is a genuine 0% result
                                val score = runCatching { AdherenceCalculator.compute(planogramDetections, detections) }.getOrDefault(0f)
                                shelfDetections = detections
                                adherenceScore = if (score.isNaN()) 0f else score
                                navController.navigate("result")
                            }
                        }
                    }
                )
            }
        }

        composable("result") {
            ResultScreen(
                adherence = adherenceScore,
                planogramDetections = planogramDetections,
                shelfDetections = shelfDetections,
                planogramBitmap = planogramBitmap,
                shelfBitmap = shelfBitmap,
                selectedOutlet = selectedOutlet,
                onBackToDashboard = {
                    selectedOutlet = null
                    navController.navigate("menu") { popUpTo("menu") { inclusive = true } }
                }
            )
        }

        composable("sos") {
            ShareOfShelfScreen(
                bitmap = sosBitmap,
                score = sosScore,
                detectedCount = sosDetectedCount,
                selectedOutlet = selectedOutlet,
                onCapture = { captured ->
                    sosBitmap = captured
                    sosScore = null
                },
                onGallery = { pickSos.launch("image/*") },
                onRetake = {
                    // Recalculate: clear the result and pick another photo (demo: gallery, not camera)
                    sosScore = null
                    sosBitmap = null
                    pickSos.launch("image/*")
                },
                onCalculate = {
                    sosBitmap?.let { bitmap ->
                        analyse(bitmap) { detections ->
                            sosDetectedCount = detections.size
                            val res = SoSCalculator.calculate(detections)
                            sosScore = if (res.isNaN()) 0f else res   // 0% is shown as a FAIL, not hidden
                        }
                    }
                },
                onBack = {
                    selectedOutlet = null
                    navController.popBackStack()
                }
            )
        }

        composable("osa_entry") {
            var isCameraMode by remember { mutableStateOf(false) }
            if (isCameraMode) {
                CameraCapture { bitmap ->
                    analyse(bitmap, onFail = { isCameraMode = false }) { detections ->
                        isCameraMode = false
                        showOsa(bitmap, detections)
                    }
                }
            } else {
                Column(
                    modifier = Modifier.fillMaxSize().background(AppDarkBg).padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Text(
                        "Outlet: ${selectedOutlet?.outlet_name ?: "Select Outlet"}",
                        color = AppCoral,
                        style = MaterialTheme.typography.labelLarge
                    )
                    Spacer(Modifier.height(16.dp))
                    Text("OSA Analysis", color = AppTextWhite, style = MaterialTheme.typography.headlineMedium)
                    Spacer(Modifier.height(32.dp))
                    AppButton(text = "Capture Live", onClick = { isCameraMode = true })
                    Spacer(Modifier.height(16.dp))
                    AppButton(text = "Select Gallery", onClick = { pickOsa.launch("image/*") })
                    Spacer(Modifier.height(16.dp))
                    TextButton(onClick = { navController.popBackStack() }) {
                        Text("Cancel", color = AppTextWhite.copy(0.7f))
                    }
                }
            }
        }

        composable("osa_view") {
            OSAScreen(
                debugBitmap = osaDebugBitmap,
                skuCounts = osaSkuCounts,
                selectedOutlet = selectedOutlet,
                shelfBitmap = osaBitmap,
                detections = osaDetections,
                onBack = { navController.popBackStack() },   // Cancel → back to capture
                onSubmitted = {                               // Submit → menu, visit done
                    selectedOutlet = null
                    osaDebugBitmap = null
                    osaBitmap = null
                    osaDetections = emptyList()
                    osaSkuCounts = emptyMap()
                    navController.navigate("menu") { popUpTo("menu") { inclusive = true } }
                }
            )
        }

        composable("help") { HelpScreen(onBack = { navController.popBackStack() }) }
    }
}

// Temporary stand-in for screens that haven't been built yet.
@Composable
fun ComingSoonScreen(title: String, onBack: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().background(AppDarkBg).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(title, color = AppTextWhite, style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text("This screen is coming soon.", color = AppTextWhite.copy(0.7f))
        Spacer(Modifier.height(24.dp))
        TextButton(onClick = onBack) { Text("Back", color = AppCoral) }
    }
}

// Ensure this is OUTSIDE the AppNav function
// null (instead of a crash) when the file can't be read or isn't an image Android can decode
fun decodeBitmap(context: Context, uri: Uri): Bitmap? = try {
    context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) }
} catch (e: Exception) {
    Log.e("decodeBitmap", "Couldn't decode $uri", e)
    null
}