package com.example.planogram_adherance_mobile.userI

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.planogram_adherance_mobile.ui.theme.*

private data class HelpTopic(val title: String, val steps: List<String>)

private val TOPICS = listOf(
    HelpTopic(
        "Getting started",
        listOf(
            "Log in with the work email and password your Flora Foods admin gave you.",
            "Every check starts by choosing the outlet you are standing in. Pick it from the list before you take any photo.",
            "Checks done at the same outlet within 2 hours count as one store visit on the dashboard, so do the OSA, Share of Shelf and planogram checks in one go."
        )
    ),
    HelpTopic(
        "Planogram check",
        listOf(
            "Menu -> Planogram -> choose the outlet.",
            "Take or choose a photo of the PLANOGRAM (the approved shelf layout), then tap Save & continue.",
            "Take or choose a photo of the ACTUAL shelf, then tap Compare.",
            "The adherence score shows how closely the shelf matches the plan. 70% or more is a Pass.",
            "Tap Submit Result & Exit to send it."
        )
    ),
    HelpTopic(
        "Share of Shelf (SOS)",
        listOf(
            "Menu -> Share of Shelf -> choose the outlet.",
            "Take a live photo or choose one from the gallery. Capture the whole spreads section, not just the Blueband facings.",
            "Tap Calculate Share. The score is Blueband's share of the shelf area. 20% or more is a Pass.",
            "Not happy with the photo? Tap Recalculate to choose a different one.",
            "Tap Submit & Exit to send it."
        )
    ),
    HelpTopic(
        "On-Shelf Availability (OSA)",
        listOf(
            "Menu -> OSA -> choose the outlet.",
            "Capture the shelf live or select a photo from the gallery.",
            "The debug view shows each product the camera found, with a count per SKU. A Blueband SKU that is missing from the list is treated as out of stock.",
            "Check the boxes look right, then tap Submit OSA Report. Out-of-stock SKUs appear on the Stock-out alerts page straight away."
        )
    ),
    HelpTopic(
        "Taking good photos",
        listOf(
            "Stand square to the shelf, about 1-2 metres back, so the full bay fits in one photo.",
            "Avoid glare from lights and glass doors; step slightly to the side if needed.",
            "Hold the phone steady and make sure the price tags and packs are sharp.",
            "One bay per photo. Don't stitch or crop."
        )
    ),
    HelpTopic(
        "Working offline",
        listOf(
            "No signal in the store? Submit as normal. You will see \"report saved on this phone\".",
            "Saved reports upload automatically when you are back online, even if you close the app in between.",
            "You'll see \"Saved report uploaded\" once it has gone through. Don't log out before then, or reports still waiting to upload may be lost."
        )
    ),
    HelpTopic(
        "Troubleshooting",
        listOf(
            "\"Report was rejected\": your account isn't allowed to submit yet. Ask your admin to check your account is set up as a merchandiser.",
            "Your visits don't show on the dashboard: your account may not be linked to a merchandiser profile yet. Ask your admin.",
            "The outlet you're in isn't listed: ask your admin to add it to the outlet list.",
            "The app is slow to analyse a photo: the model runs on the phone, so give it a few seconds. Close other apps if it keeps happening."
        )
    ),
)

@Composable
fun HelpScreen(onBack: () -> Unit) {
    var open by remember { mutableStateOf(0) }  // index of the expanded topic, -1 = none

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AppDarkBg)
            .verticalScroll(rememberScrollState())
            .padding(24.dp)
    ) {
        Spacer(Modifier.height(24.dp))
        Text("Help", color = AppTextWhite, fontSize = 26.sp, fontWeight = FontWeight.Bold)
        Text("How to use Shelf Poa in the store", color = AppTextWhite.copy(alpha = 0.7f), fontSize = 14.sp)
        Spacer(Modifier.height(20.dp))

        TOPICS.forEachIndexed { i, topic ->
            Surface(
                color = AppSurface,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 12.dp)
                    .clickable { open = if (open == i) -1 else i }
            ) {
                Column(Modifier.padding(16.dp)) {
                    Row {
                        Text(topic.title, color = AppTextWhite, fontWeight = FontWeight.Bold, fontSize = 16.sp,
                            modifier = Modifier.weight(1f))
                        Text(if (open == i) "-" else "+", color = AppCoral, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    }
                    if (open == i) {
                        Spacer(Modifier.height(10.dp))
                        topic.steps.forEachIndexed { n, step ->
                            Row(Modifier.padding(vertical = 4.dp)) {
                                Text("${n + 1}.", color = AppCoral, fontWeight = FontWeight.Bold, fontSize = 14.sp,
                                    modifier = Modifier.width(24.dp))
                                Text(step, color = AppTextWhite.copy(alpha = 0.9f), fontSize = 14.sp, lineHeight = 20.sp)
                            }
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(8.dp))
        AppButton(text = "Back to Menu", onClick = onBack, containerColor = AppCoral)
        Spacer(Modifier.height(16.dp))
    }
}