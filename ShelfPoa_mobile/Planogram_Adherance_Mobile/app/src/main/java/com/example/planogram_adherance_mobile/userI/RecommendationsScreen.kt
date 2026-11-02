package com.example.planogram_adherance_mobile.userI

import android.text.format.DateUtils
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.planogram_adherance_mobile.data.Recommendation
import com.example.planogram_adherance_mobile.data.RecommendationRepository
import com.example.planogram_adherance_mobile.models.CurrentUser
import com.example.planogram_adherance_mobile.ui.theme.*

private val HighRed = Color(0xFFE5484D)
private val MediumAmber = Color(0xFFF5A524)
private val LowGrey = Color(0xFF8B8A93)
private val DoneGreen = Color(0xFF4CAF50)

private fun priorityColor(p: String) = when (p) {
    "high" -> HighRed
    "low" -> LowGrey
    else -> MediumAmber
}

private fun priorityRank(p: String) = when (p) {
    "high" -> 0
    "medium" -> 1
    else -> 2
}

// Must match TYPES in the web RecommendationMaker.jsx
private val TYPE_LABELS = mapOf(
    "sos" to "Shelf space",
    "copromo" to "Co-promotion",
    "restock" to "Restock"
)

@Composable
fun RecommendationsScreen(onBack: () -> Unit) {
    val uid = CurrentUser.uid

    var items by remember { mutableStateOf<List<Recommendation>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var tab by remember { mutableIntStateOf(0) }            // 0 = To do, 1 = History
    var closing by remember { mutableStateOf<Pair<Recommendation, String>?>(null) } // rec + "done"/"dismissed"

    // ids that were unread when they first arrived, so the "new" dot survives markSeen
    val unread = remember { mutableStateListOf<String>() }

    DisposableEffect(uid) {
        val stop = RecommendationRepository.listen(
            uid = uid,
            onChange = { list ->
                list.filter { it.status == "new" }.forEach { rec ->
                    if (rec.id !in unread) unread.add(rec.id)
                    RecommendationRepository.markSeen(uid, rec.id)
                }
                items = list
                loading = false
            },
            onError = { error = it; loading = false }
        )
        onDispose { stop() }
    }

    val open = items.filter { it.isOpen }
        .sortedWith(compareBy<Recommendation> { priorityRank(it.priority) }.thenByDescending { it.createdAt })
    val history = items.filterNot { it.isOpen }
        .sortedByDescending { it.completedAt ?: it.createdAt }
    val shown = if (tab == 0) open else history

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg)
            .padding(24.dp)
    ) {
        Text("Recommendations", color = AppTextWhite, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("Actions assigned to you by your manager", color = AppTextWhite.copy(0.6f), fontSize = 12.sp)

        Spacer(Modifier.height(16.dp))

        TabRow(
            selectedTabIndex = tab,
            containerColor = AppSurface,
            contentColor = AppCoral
        ) {
            Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("To do (${open.size})") })
            Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("History (${history.size})") })
        }

        Spacer(Modifier.height(12.dp))

        when {
            loading -> Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = AppCoral)
            }
            error != null -> Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                Text(error!!, color = HighRed)
            }
            shown.isEmpty() -> Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                Text(
                    if (tab == 0) "Nothing to do right now" else "No completed recommendations yet",
                    color = AppTextWhite.copy(0.6f)
                )
            }
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(shown, key = { it.id }) { rec ->
                    RecommendationCard(
                        rec = rec,
                        isUnread = rec.id in unread && rec.isOpen,
                        onDone = { closing = rec to "done" },
                        onDismiss = { closing = rec to "dismissed" }
                    )
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

    closing?.let { (rec, status) ->
        CloseDialog(
            rec = rec,
            status = status,
            onConfirm = { note ->
                RecommendationRepository.close(uid, rec.id, status, note)
                unread.remove(rec.id)
                closing = null
            },
            onCancel = { closing = null }
        )
    }
}

@Composable
private fun RecommendationCard(
    rec: Recommendation,
    isUnread: Boolean,
    onDone: () -> Unit,
    onDismiss: () -> Unit
) {
    Surface(color = AppSurface, shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            // Priority · type · new dot
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(8.dp).background(priorityColor(rec.priority), CircleShape))
                Spacer(Modifier.width(6.dp))
                Text(
                    "${rec.priority.replaceFirstChar { it.uppercase() }} · ${TYPE_LABELS[rec.type] ?: "Action"}",
                    color = priorityColor(rec.priority),
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f)
                )
                if (isUnread) {
                    Text("NEW", color = AppCoral, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                }
            }

            Spacer(Modifier.height(6.dp))
            Text(rec.title, color = AppTextWhite, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)

            val where = listOf(rec.outletName, rec.sku).filter { it.isNotEmpty() }.joinToString(" · ")
            if (where.isNotEmpty()) {
                Text(where, color = AppCoral, fontSize = 12.sp)
            }
            if (rec.due.isNotEmpty() && rec.isOpen) {
                Text("Due: ${rec.due}", color = AppTextWhite.copy(0.7f), fontSize = 12.sp)
            }

            if (rec.message.isNotEmpty()) {
                Spacer(Modifier.height(6.dp))
                Text(rec.message, color = AppTextWhite.copy(0.85f), fontSize = 13.sp)
            }

            if (rec.basis.isNotEmpty()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    "Why: ${rec.basis}",
                    color = AppTextWhite.copy(0.5f),
                    fontSize = 11.sp
                )
            }

            Spacer(Modifier.height(8.dp))
            Text(
                buildString {
                    append(if (rec.createdByName.isNotEmpty()) "From ${rec.createdByName}" else "Assigned")
                    if (rec.source == "ml") append(" · model suggestion")
                    if (rec.createdAt > 0) append(" · ${DateUtils.getRelativeTimeSpanString(rec.createdAt)}")
                },
                color = AppTextWhite.copy(0.4f),
                fontSize = 10.sp
            )

            if (rec.isOpen) {
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = onDone,
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.buttonColors(containerColor = AppCoral)
                    ) { Text("Mark done", color = AppDarkBg, fontWeight = FontWeight.SemiBold) }
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f)
                    ) { Text("Can't do", color = AppTextWhite.copy(0.8f)) }
                }
            } else {
                Spacer(Modifier.height(8.dp))
                Text(
                    buildString {
                        append(if (rec.status == "done") "Done" else "Couldn't action")
                        rec.completedAt?.let { append(" · ${DateUtils.getRelativeTimeSpanString(it)}") }
                    },
                    color = if (rec.status == "done") DoneGreen else LowGrey,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold
                )
                if (rec.note.isNotEmpty()) {
                    Text("“${rec.note}”", color = AppTextWhite.copy(0.6f), fontSize = 12.sp)
                }
            }
        }
    }
}

@Composable
private fun CloseDialog(
    rec: Recommendation,
    status: String,
    onConfirm: (String) -> Unit,
    onCancel: () -> Unit
) {
    var note by remember { mutableStateOf("") }
    val isDone = status == "done"

    AlertDialog(
        onDismissRequest = onCancel,
        containerColor = AppSurface,
        title = {
            Text(if (isDone) "Mark as done?" else "Can't action this?", color = AppTextWhite, fontSize = 18.sp)
        },
        text = {
            Column {
                Text(rec.title, color = AppTextWhite.copy(0.8f), fontSize = 13.sp)
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it.take(300) },
                    label = { Text(if (isDone) "Note (optional)" else "Reason") },
                    minLines = 2,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(note) },
                enabled = isDone || note.isNotBlank()   // a reason is required when declining
            ) { Text("Confirm", color = AppCoral) }
        },
        dismissButton = {
            TextButton(onClick = onCancel) { Text("Cancel", color = AppTextWhite.copy(0.7f)) }
        }
    )
}
