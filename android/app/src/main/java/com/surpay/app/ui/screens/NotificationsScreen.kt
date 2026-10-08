package com.surpay.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Chat
import androidx.compose.material.icons.outlined.Celebration
import androidx.compose.material.icons.outlined.FamilyRestroom
import androidx.compose.material.icons.outlined.Gavel
import androidx.compose.material.icons.outlined.NotificationsNone
import androidx.compose.material.icons.outlined.Timeline
import androidx.compose.material.icons.outlined.VerifiedUser
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.surpay.app.data.AppNotification
import com.surpay.app.ui.theme.Gold
import com.surpay.app.ui.prettyDate

@Composable
fun NotificationsScreen(
    items: List<AppNotification>?,
    onLoad: () -> Unit,
    onMarkRead: () -> Unit,
    onOpen: (AppNotification) -> Unit,
    modifier: Modifier = Modifier,
) {
    LaunchedEffect(Unit) { onLoad() }
    LaunchedEffect(items?.count { !it.read }) { if (items?.any { !it.read } == true) onMarkRead() }
    when {
        items == null -> Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        items.isEmpty() -> Column(modifier.fillMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center) {
            IconCircle(Icons.Outlined.NotificationsNone, size = 64.dp)
            Text("No updates yet", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 12.dp))
            Text("We’ll let you know here, and on your phone, when anything changes.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        else -> LazyColumn(modifier.fillMaxSize().testTag("notifications"), contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(items, key = { it.id }) { n ->
                SectionCard(onClick = { onOpen(n) }, modifier = Modifier.testTag("notification${n.id}")) {
                    Row {
                        val (icon, bg) = when (n.kind) {
                            "money_released" -> Icons.Outlined.Celebration to Gold.copy(alpha = 0.18f)
                            "message" -> Icons.AutoMirrored.Outlined.Chat to MaterialTheme.colorScheme.primaryContainer
                            "case_offer" -> Icons.Outlined.Gavel to MaterialTheme.colorScheme.primaryContainer
                            "identity" -> Icons.Outlined.VerifiedUser to MaterialTheme.colorScheme.primaryContainer
                            "relative" -> Icons.Outlined.FamilyRestroom to MaterialTheme.colorScheme.primaryContainer
                            else -> Icons.Outlined.Timeline to MaterialTheme.colorScheme.primaryContainer
                        }
                        IconCircle(icon, background = bg)
                        Column(Modifier.weight(1f).padding(start = 12.dp)) {
                            Text(n.title, fontWeight = if (n.read) FontWeight.SemiBold else FontWeight.ExtraBold)
                            if (n.body.isNotBlank()) Text(n.body, style = MaterialTheme.typography.bodyMedium)
                            Text(prettyDate(n.createdAt), style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}
