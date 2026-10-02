package com.example.planogram_adherance_mobile

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
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
import com.example.planogram_adherance_mobile.models.Outlet // IMPORTANT: Check this path
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
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
    var sosScore by remember { mutableFloatStateOf(0f) }
    var osaDebugBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var osaSkuCounts by remember { mutableStateOf<Map<String, Int>>(emptyMap()) }

    // --- LAUNCHERS (Fixed Types) ---
    val pickPlanogram = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { planogramBitmap = decodeBitmap(context, it) }
    }
    val pickShelf = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { shelfBitmap = decodeBitmap(context, it) }
    }
    val pickSos = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { sosBitmap = decodeBitmap(context, it) }
    }
    val pickOsa = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { uriPath ->
            val bitmap = decodeBitmap(context, uriPath)
            scope.launch(Dispatchers.Default) {
                val input = ImagePreprocessor.preprocess(bitmap)
                val detections = yoloRunner.infer(input)
                val debugImg = OSA.drawDebugBoxes(bitmap, detections)
                val counts = OSA.calculateCounts(detections)
                withContext(Dispatchers.Main) {
                    osaDebugBitmap = debugImg
                    osaSkuCounts = counts
                    navController.navigate("osa_view")
                }
            }
        }
    }

    NavHost(navController = navController, startDestination = "splash") {

        composable("splash") {
            SplashScreen(onTimeout = {
                navController.navigate("menu") { popUpTo("splash") { inclusive = true } }
            })
        }

        composable("menu") {
            MenuScreen(
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
                onNavigateToHelp = { navController.navigate("help") }
            )
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
                            scope.launch(Dispatchers.Default) {
                                val input = ImagePreprocessor.preprocess(bitmap)
                                val detections = yoloRunner.infer(input)
                                withContext(Dispatchers.Main) {
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
                            scope.launch(Dispatchers.Default) {
                                val input = ImagePreprocessor.preprocess(bitmap)
                                val detections = yoloRunner.infer(input)
                                val score = AdherenceCalculator.compute(planogramDetections, detections)
                                withContext(Dispatchers.Main) {
                                    shelfDetections = detections
                                    adherenceScore = score
                                    navController.navigate("result")
                                }
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
                selectedOutlet = selectedOutlet,
                onCapture = { captured ->
                    sosBitmap = captured
                    sosScore = 0f
                },
                onGallery = { pickSos.launch("image/*") },
                onCalculate = {
                    sosBitmap?.let { bitmap ->
                        scope.launch(Dispatchers.Default) {
                            val input = ImagePreprocessor.preprocess(bitmap)
                            val detections = yoloRunner.infer(input)
                            val res = SoSCalculator.calculate(detections)
                            withContext(Dispatchers.Main) { sosScore = res }
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
                    scope.launch(Dispatchers.Default) {
                        val input = ImagePreprocessor.preprocess(bitmap)
                        val detections = yoloRunner.infer(input)
                        val debugImg = OSA.drawDebugBoxes(bitmap, detections)
                        val counts = OSA.calculateCounts(detections)
                        withContext(Dispatchers.Main) {
                            osaDebugBitmap = debugImg
                            osaSkuCounts = counts
                            isCameraMode = false
                            navController.navigate("osa_view")
                        }
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
                selectedOutlet = selectedOutlet, // FIXED: Added this parameter
                onBack = { navController.popBackStack() }
            )
        }

        composable("help") { HelpScreen(onBack = { navController.popBackStack() }) }
    }
}

// Ensure this is OUTSIDE the AppNav function
fun decodeBitmap(context: Context, uri: Uri): Bitmap {
    return context.contentResolver.openInputStream(uri).use {
        BitmapFactory.decodeStream(it)
    }!!
}