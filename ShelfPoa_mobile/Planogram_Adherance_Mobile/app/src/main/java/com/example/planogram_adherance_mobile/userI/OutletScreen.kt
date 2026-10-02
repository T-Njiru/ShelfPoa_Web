package com.example.planogram_adherance_mobile.userI

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
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
import com.example.planogram_adherance_mobile.models.Outlet
import com.example.planogram_adherance_mobile.ui.theme.*
import com.google.firebase.database.FirebaseDatabase

@Composable
fun OutletsScreen(onOutletSelected: (Outlet) -> Unit, onBack: () -> Unit) {
    // State for data
    var allOutlets by remember { mutableStateOf(emptyList<Outlet>()) }
    var mtGroups by remember { mutableStateOf(listOf("All")) }

    // State for UI interaction
    var selectedGroup by remember { mutableStateOf("All") }
    var isLoading by remember { mutableStateOf(true) }

    val database = FirebaseDatabase.getInstance()

    // Load Data from Firebase
    LaunchedEffect(Unit) {
        // 1. Fetch Groups
        database.getReference("mt_groups").get()
            .addOnSuccessListener { snapshot ->
                val groupsFromDb = snapshot.children.mapNotNull {
                    it.child("group_name").getValue(String::class.java)
                }
                mtGroups = listOf("All") + groupsFromDb
                println("Firebase: Groups loaded successfully")
            }
            .addOnFailureListener { e ->
                println("Firebase Error (Groups): ${e.message}")
                isLoading = false // Stop the spinner even if it fails
            }

        // 2. Fetch Outlets
        database.getReference("outlets_universe").get()
            .addOnSuccessListener { snapshot ->
                val list = snapshot.children.mapNotNull {
                    it.getValue(Outlet::class.java)?.copy(id = it.key ?: "")
                }
                allOutlets = list
                isLoading = false
                println("Firebase: Outlets loaded successfully")
            }
            .addOnFailureListener { e ->
                println("Firebase Error (Outlets): ${e.message}")
                isLoading = false
            }
    }
    // Logic: Filter the list whenever selectedGroup or allOutlets changes
    val filteredOutlets = remember(selectedGroup, allOutlets) {
        if (selectedGroup == "All") allOutlets
        else allOutlets.filter { it.group_name == selectedGroup }
    }

    Column(modifier = Modifier.fillMaxSize().background(AppDarkBg).padding(24.dp)) {
        Text(
            text = "Select Outlet",
            color = AppTextWhite,
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold
        )

        Spacer(Modifier.height(16.dp))

        // --- Modern Trade Group Selector ---
        Text("Modern Trade Filter", color = AppTextWhite.copy(0.6f), fontSize = 14.sp)
        Spacer(Modifier.height(8.dp))

        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(mtGroups) { group ->
                val isSelected = selectedGroup == group
                Surface(
                    modifier = Modifier.clickable { selectedGroup = group },
                    color = if (isSelected) AppCoral else AppSurface,
                    shape = RoundedCornerShape(20.dp),
                    border = if (isSelected) null else BorderStroke(1.dp, AppTextWhite.copy(0.1f))
                ) {
                    Text(
                        text = group,
                        color = if (isSelected) Color.Black else AppTextWhite,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        fontSize = 14.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                    )
                }
            }
        }

        Spacer(Modifier.height(24.dp))

        // --- List Content ---
        if (isLoading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = AppCoral)
            }
        } else {
            if (filteredOutlets.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("No outlets found for $selectedGroup", color = AppTextWhite.copy(0.5f))
                }
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    items(filteredOutlets) { outlet ->
                        Surface(
                            modifier = Modifier.fillMaxWidth().clickable { onOutletSelected(outlet) },
                            color = AppSurface,
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text(
                                    text = outlet.outlet_name,
                                    color = AppTextWhite,
                                    fontWeight = FontWeight.Bold
                                )
                                Text(
                                    text = outlet.group_name.ifEmpty { "General Trade" },
                                    color = AppCoral.copy(0.8f),
                                    fontSize = 12.sp
                                )
                            }
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        TextButton(
            onClick = onBack,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Cancel", color = AppTextWhite.copy(0.7f))
        }
    }
}