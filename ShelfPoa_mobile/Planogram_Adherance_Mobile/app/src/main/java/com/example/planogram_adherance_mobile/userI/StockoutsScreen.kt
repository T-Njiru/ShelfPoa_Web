package com.example.planogram_adherance_mobile.userI

import android.text.format.DateUtils
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.planogram_adherance_mobile.data.StockoutAlert
import com.example.planogram_adherance_mobile.data.StockoutRepository
import com.example.planogram_adherance_mobile.ui.theme.*

private val OutOfStockRed = Color(0xFFE5484D)

@Composable
fun StockoutsScreen(onBack: () -> Unit) {
    var alerts by remember { mutableStateOf<List<StockoutAlert>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var refreshKey by remember { mutableIntStateOf(0) }

    LaunchedEffect(refreshKey) {
        loading = true
        error = null
        StockoutRepository.load(
            onResult = { alerts = it; loading = false },
            onError = { error = it; loading = false }
        )
    }

    // Outlet with its out-of-stock SKUs, most recently reported outlet first
    val byOutlet = alerts.groupBy { it.outletId }.values
        .sortedByDescending { group -> group.maxOf { it.lastReportedAt } }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg)
            .padding(24.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Stock-out alerts", color = AppTextWhite, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(
                    if (loading) "Loading…" else "${alerts.size} SKUs out of stock across ${byOutlet.size} outlets",
                    color = AppTextWhite.copy(0.6f),
                    fontSize = 12.sp
                )
            }
            TextButton(onClick = { refreshKey++ }, enabled = !loading) {
                Text("Refresh", color = AppCoral)
            }
        }

        Spacer(Modifier.height(16.dp))

        when {
            loading -> Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = AppCoral)
            }
            error != null -> Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                Text(error!!, color = OutOfStockRed)
            }
            alerts.isEmpty() -> Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                Text("No current stock-outs", color = AppTextWhite.copy(0.6f))
            }
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(byOutlet, key = { it.first().outletId }) { group ->
                    OutletStockoutCard(group)
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        Button(
            onClick = onBack,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = AppSurface)
        ) { Text("Back") }
    }
}

@Composable
private fun OutletStockoutCard(group: List<StockoutAlert>) {
    val latest = group.maxOf { it.lastReportedAt }
    Surface(color = AppSurface, shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    group.first().outletName,
                    color = AppTextWhite,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f)
                )
                Text("${group.size} OOS", color = OutOfStockRed, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }
            Text(
                "Last audited ${DateUtils.getRelativeTimeSpanString(latest)}",
                color = AppTextWhite.copy(0.5f),
                fontSize = 11.sp
            )
            Spacer(Modifier.height(8.dp))
            group.sortedBy { it.sku }.forEach { alert ->
                Text("• ${alert.sku}", color = AppTextWhite.copy(0.9f), fontSize = 13.sp, modifier = Modifier.padding(vertical = 2.dp))
            }
        }
    }
}
