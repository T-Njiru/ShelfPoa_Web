package com.example.planogram_adherance_mobile.userI

import android.text.format.DateUtils
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.planogram_adherance_mobile.data.*
import com.example.planogram_adherance_mobile.models.CurrentUser
import com.example.planogram_adherance_mobile.ui.theme.*

private val OutOfStockRed = Color(0xFFE5484D)
private const val DAY_MS = 24 * 60 * 60 * 1000L

private enum class Period(val label: String, val days: Int?) {
    WEEK("7 days", 7), MONTH("30 days", 30), ALL("All time", null)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(onBack: () -> Unit) {
    val uid = CurrentUser.uid

    var period by remember { mutableStateOf(Period.MONTH) }
    var stats by remember { mutableStateOf<MerchStats?>(null) }
    var myStockouts by remember { mutableStateOf<List<StockoutAlert>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var showStockouts by remember { mutableStateOf(false) }

    LaunchedEffect(period) {
        loading = true
        error = null
        val since = period.days?.let { System.currentTimeMillis() - it * DAY_MS } ?: 0L
        DashboardRepository.load(
            uid = uid,
            sinceMs = since,
            onResult = { stats = it; loading = false },
            onError = { error = it; loading = false }
        )
    }

    // Open stock-outs this merchandiser reported (independent of the period filter)
    LaunchedEffect(uid) {
        StockoutRepository.load(
            onResult = { myStockouts = it },
            onError = { /* button just shows 0; the stock-out screen surfaces errors */ },
            reportedBy = uid
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg)
            .padding(24.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text("My performance", color = AppTextWhite, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(
            CurrentUser.displayName.ifEmpty { "Merchandiser" } +
                    CurrentUser.merchandiserId.takeIf { it.isNotEmpty() }?.let { " · $it" }.orEmpty(),
            color = AppCoral,
            fontSize = 13.sp
        )

        Spacer(Modifier.height(16.dp))

        // Period filter
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Period.entries.forEach { p ->
                FilterChip(
                    selected = period == p,
                    onClick = { period = p },
                    label = { Text(p.label, fontSize = 12.sp) },
                    colors = FilterChipDefaults.filterChipColors(
                        containerColor = AppSurface,
                        labelColor = AppTextWhite.copy(0.7f),
                        selectedContainerColor = AppCoral,
                        selectedLabelColor = AppDarkBg
                    )
                )
            }
        }

        Spacer(Modifier.height(16.dp))

        when {
            loading -> Box(Modifier.fillMaxWidth().height(200.dp), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = AppCoral)
            }
            error != null -> Text(error!!, color = OutOfStockRed)
            stats != null -> DashboardContent(stats!!)
        }

        Spacer(Modifier.height(20.dp))

        // Stock-outs popup trigger
        AppButton(
            text = "My reported stock-outs (${myStockouts.size})",
            onClick = { showStockouts = true },
            containerColor = if (myStockouts.isEmpty()) AppSurface else AppCoral
        )

        Spacer(Modifier.height(12.dp))
        Button(
            onClick = onBack,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = AppSurface)
        ) { Text("Back") }
    }

    if (showStockouts) {
        MyStockoutsDialog(myStockouts, onDismiss = { showStockouts = false })
    }
}

@Composable
private fun DashboardContent(s: MerchStats) {
    // KPI cards
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        KpiCard("OSA", s.osaAvg, s.osaCount, Modifier.weight(1f))
        KpiCard("SOS", s.sosAvg, s.sosCount, Modifier.weight(1f))
        KpiCard("Compliance", s.complianceAvg, s.complianceCount, Modifier.weight(1f))
    }

    Spacer(Modifier.height(10.dp))

    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        StatCard("Outlet visits", s.visits.toString(), Modifier.weight(1f))
        StatCard("Outlets covered", s.outlets.toString(), Modifier.weight(1f))
    }

    Spacer(Modifier.height(20.dp))

    Text("Recent activity", color = AppTextWhite, fontWeight = FontWeight.SemiBold)
    Spacer(Modifier.height(8.dp))

    Surface(color = AppSurface, shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
        if (s.recent.isEmpty()) {
            Text("No captures in this period", color = AppTextWhite.copy(0.5f), modifier = Modifier.padding(16.dp))
        } else {
            Column(Modifier.padding(vertical = 4.dp)) {
                s.recent.forEachIndexed { i, c ->
                    Row(
                        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(c.outletName, color = AppTextWhite, fontSize = 14.sp)
                            Text(
                                "${c.type.label} · ${DateUtils.getRelativeTimeSpanString(c.timestamp)}",
                                color = AppTextWhite.copy(0.5f),
                                fontSize = 11.sp
                            )
                        }
                        Text(
                            c.score?.let { "${"%.0f".format(it)}%" } ?: "—",
                            color = AppCoral,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    if (i < s.recent.lastIndex) HorizontalDivider(color = AppTextWhite.copy(0.08f))
                }
            }
        }
    }
}

@Composable
private fun KpiCard(label: String, value: Double?, count: Int, modifier: Modifier) {
    Surface(color = AppSurface, shape = RoundedCornerShape(12.dp), modifier = modifier) {
        Column(Modifier.padding(12.dp)) {
            Text(label, color = AppTextWhite.copy(0.6f), fontSize = 11.sp)
            Text(
                value?.let { "${"%.0f".format(it)}%" } ?: "—",
                color = AppTextWhite,
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold
            )
            Text("$count captures", color = AppTextWhite.copy(0.5f), fontSize = 10.sp)
        }
    }
}

@Composable
private fun StatCard(label: String, value: String, modifier: Modifier) {
    Surface(color = AppSurface, shape = RoundedCornerShape(12.dp), modifier = modifier) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(label, color = AppTextWhite.copy(0.6f), fontSize = 12.sp, modifier = Modifier.weight(1f))
            Text(value, color = AppTextWhite, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun MyStockoutsDialog(alerts: List<StockoutAlert>, onDismiss: () -> Unit) {
    val byOutlet = alerts.groupBy { it.outletId }.values
        .sortedByDescending { g -> g.maxOf { it.lastReportedAt } }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = AppSurface,
        title = { Text("Open stock-outs you reported", color = AppTextWhite, fontSize = 18.sp) },
        text = {
            if (alerts.isEmpty()) {
                Text("None. Every SKU you last flagged has since been restocked or re-audited.", color = AppTextWhite.copy(0.7f))
            } else {
                Column(
                    Modifier
                        .heightIn(max = 400.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    byOutlet.forEach { group ->
                        Text(group.first().outletName, color = AppTextWhite, fontWeight = FontWeight.SemiBold)
                        Text(
                            "Reported ${DateUtils.getRelativeTimeSpanString(group.maxOf { it.lastReportedAt })}",
                            color = AppTextWhite.copy(0.5f),
                            fontSize = 11.sp
                        )
                        group.sortedBy { it.sku }.forEach {
                            Text("• ${it.sku}", color = OutOfStockRed, fontSize = 13.sp, modifier = Modifier.padding(vertical = 1.dp))
                        }
                        Spacer(Modifier.height(12.dp))
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Close", color = AppCoral) }
        }
    )
}
