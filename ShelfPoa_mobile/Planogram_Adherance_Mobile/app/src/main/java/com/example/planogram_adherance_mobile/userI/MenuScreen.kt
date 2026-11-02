package com.example.planogram_adherance_mobile.userI

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.HelpOutline
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.ChevronRight
import androidx.compose.material.icons.outlined.Dashboard
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.Lightbulb
import androidx.compose.material.icons.outlined.PieChart
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.planogram_adherance_mobile.R
import com.example.planogram_adherance_mobile.ui.theme.*

private val MenuMuted = Color(0xFFA8A6AE)
private val MenuDanger = Color(0xFFE0605A)

@Composable
fun MenuScreen(
    userEmail: String?,
    onNavigateToShelf: () -> Unit,
    onNavigateToSOS: () -> Unit,
    onNavigateToOSA: () -> Unit,
    onNavigateToDashboard: () -> Unit,
    onNavigateToRecommendations: () -> Unit,
    onNavigateToStockouts: () -> Unit,
    onNavigateToHelp: () -> Unit,
    onSignOut: () -> Unit
) {
    var showSignOutDialog by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 20.dp)
    ) {
        // Header: logo top-left, as in the wireframes
        Row(verticalAlignment = Alignment.CenterVertically) {
            Image(
                painter = painterResource(id = R.drawable.logo),
                contentDescription = "Shelf Poa logo",
                modifier = Modifier.size(36.dp)
            )
            Spacer(Modifier.width(10.dp))
            Text("Shelf Poa", color = AppCoral, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }

        Spacer(Modifier.height(20.dp))
        Text("Main menu", color = AppTextWhite, fontSize = 22.sp, fontWeight = FontWeight.Bold)
        if (userEmail != null) {
            Text("Signed in as $userEmail", color = MenuMuted, fontSize = 12.sp)
        }

        SectionLabel("Field audit")
        MenuRow(Icons.Outlined.CameraAlt, "Shelf audit", "Compare a shelf against its planogram", onNavigateToShelf)
        MenuRow(Icons.Outlined.PieChart, "Share of shelf", "Measure Blueband's share of facings", onNavigateToSOS)
        MenuRow(Icons.Outlined.Inventory2, "On-shelf availability", "Count SKUs on a shelf photo", onNavigateToOSA)

        SectionLabel("Insights")
        MenuRow(Icons.Outlined.Dashboard, "Dashboard", "SOS, OSA, compliance and MTD sales", onNavigateToDashboard)
        MenuRow(Icons.Outlined.Lightbulb, "Recommendations", "Co-promotions and SKU suggestions", onNavigateToRecommendations)
        MenuRow(Icons.Outlined.WarningAmber, "Stock-out alerts", "Outlets reporting empty shelves", onNavigateToStockouts)

        SectionLabel("Account")
        MenuRow(Icons.AutoMirrored.Outlined.HelpOutline, "Help", "How to use Shelf Poa", onNavigateToHelp)
        MenuRow(
            icon = Icons.AutoMirrored.Outlined.Logout,
            title = "Sign out",
            subtitle = null,
            onClick = { showSignOutDialog = true },
            tint = MenuDanger
        )
    }

    if (showSignOutDialog) {
        AlertDialog(
            onDismissRequest = { showSignOutDialog = false },
            title = { Text("Sign out?") },
            text = { Text("You'll need to log in again to run audits.") },
            confirmButton = {
                TextButton(onClick = {
                    showSignOutDialog = false
                    onSignOut()
                }) { Text("Sign out", color = MenuDanger, fontWeight = FontWeight.Bold) }
            },
            dismissButton = {
                TextButton(onClick = { showSignOutDialog = false }) { Text("Cancel", color = MenuMuted) }
            },
            containerColor = AppSurface,
            titleContentColor = AppTextWhite,
            textContentColor = MenuMuted
        )
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(
        text = text.uppercase(),
        color = MenuMuted,
        fontSize = 11.sp,
        fontWeight = FontWeight.Bold,
        letterSpacing = 0.6.sp,
        modifier = Modifier.padding(top = 22.dp, bottom = 8.dp)
    )
}

@Composable
private fun MenuRow(
    icon: ImageVector,
    title: String,
    subtitle: String?,
    onClick: () -> Unit,
    tint: Color = AppCoral
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 10.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(AppSurface)
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(tint.copy(alpha = 0.15f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(20.dp))
        }
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(title, color = if (tint == MenuDanger) tint else AppTextWhite, fontSize = 14.sp, fontWeight = FontWeight.Bold)
            if (subtitle != null) {
                Text(subtitle, color = MenuMuted, fontSize = 11.5.sp)
            }
        }
        Icon(Icons.Outlined.ChevronRight, contentDescription = null, tint = MenuMuted)
    }
}