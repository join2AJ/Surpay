package com.surpay.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.surpay.app.data.Match
import com.surpay.app.data.MatchesResponse
import com.surpay.app.ui.MatchesState
import com.surpay.app.ui.claimStatusLabel
import com.surpay.app.ui.dollars
import com.surpay.app.ui.prettyDate
import com.surpay.app.ui.saleTypeLabel

@Composable
fun MatchesScreen(
    state: MatchesState,
    onRefresh: () -> Unit,
    onOpen: (Match) -> Unit,
    onEditProfile: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val data = state.data
    when {
        data == null && state.loading -> Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            LoadingScreen("Searching county surplus lists…")
        }
        data == null -> Box(modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(state.error ?: "Couldn’t load your results.", color = MaterialTheme.colorScheme.error)
                Spacer(Modifier.height(12.dp))
                OutlinedButton(onClick = onRefresh) { Text("Try again") }
            }
        }
        else -> LazyColumn(
            modifier.fillMaxSize().testTag("matchesList"),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { SummaryCard(data) }
            val open = data.matches.filter { it.claimStatus == null }.map { it.clock() }
            if (open.any { it.urgency == "urgent" || it.urgency == "soon" }) {
                item { DeadlineBanner(open.count { it.urgency == "urgent" }, open.count { it.urgency == "soon" }) }
            }
            state.error?.let { err -> item { Text(err, color = MaterialTheme.colorScheme.error) } }
            if (data.matches.isEmpty()) {
                item { EmptyState(data, onEditProfile) }
            } else {
                // Money that can still be claimed first, closest deadline first; passed deadlines last.
                val ordered = data.matches.sortedWith(compareBy<Match>(
                    { it.clock().urgency == "expired" },
                    { it.clock().daysLeft ?: Int.MAX_VALUE },
                ))
                // Money you're already claiming, set apart (and coloured) from money not claimed yet.
                val claimed = ordered.filter { it.claimStatus != null }
                val open = ordered.filter { it.claimStatus == null }
                if (open.isNotEmpty()) {
                    item { GroupHeader("Not claimed yet", open.size, open.sumOf { it.amountCents }, claimed = false) }
                    items(open, key = { it.recordId }) { MatchCard(it, onClick = { onOpen(it) }) }
                }
                if (claimed.isNotEmpty()) {
                    item { GroupHeader("Claims in progress", claimed.size, claimed.sumOf { it.amountCents }, claimed = true) }
                    items(claimed, key = { it.recordId }) { MatchCard(it, onClick = { onOpen(it) }) }
                }
                item { DeadlineLegend() }
                item {
                    Text(
                        data.disclaimer.ifBlank {
                            "Amounts are approximate estimates, not a promise or guarantee. Other lienholders " +
                                "may also have a right to part of these funds."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            item {
                OutlinedButton(onClick = onRefresh, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) {
                    Text(if (state.loading) "Searching…" else "Search again")
                }
            }
        }
    }
}

@Composable
private fun SummaryCard(data: MatchesResponse) {
    val found = data.matches.isNotEmpty()
    if (!found) {
        SectionCard {
            Text("No surplus found yet", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(
                "Searched ${"%,d".format(data.recordsSearched)} records in ${data.countiesCovered.size} " +
                    if (data.countiesCovered.size == 1) "county" else "counties",
                style = MaterialTheme.typography.bodySmall,
            )
        }
        return
    }
    HeroCard {
        Text("You may be owed", style = MaterialTheme.typography.titleSmall)
        Text(dollars(data.totalAmountCents), style = MaterialTheme.typography.displaySmall, modifier = Modifier.testTag("totalAmount"))
        Spacer(Modifier.height(4.dp))
        Text(
            "About ${dollars(data.totalEstimatedNetCents)} to you after fees · " +
                "${data.matches.size} possible ${if (data.matches.size == 1) "record" else "records"}",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(10.dp))
        Text(
            "Searched ${"%,d".format(data.recordsSearched)} records in ${data.countiesCovered.size} " +
                if (data.countiesCovered.size == 1) "county" else "counties",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun EmptyState(data: MatchesResponse, onEditProfile: () -> Unit) {
    Column {
        Text(
            "We add counties every week and re-check your name automatically. Adding past addresses " +
                "and any previous names gives you the best chance of a match.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(12.dp))
        OutlinedButton(onClick = onEditProfile) { Text("Add addresses or names") }
        if (data.countiesCovered.isNotEmpty()) {
            Spacer(Modifier.height(16.dp))
            Text("Counties we currently check", fontWeight = FontWeight.SemiBold)
            data.countiesCovered.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium) }
        }
    }
}

@Composable
fun ConfidenceChip(confidence: String) {
    val (label, bg, fg) = when (confidence) {
        "strong" -> Triple("Name & address match", Color(0xFFD7F2E5), Color(0xFF06402E))
        "likely" -> Triple("Name match", Color(0xFFE3ECFB), Color(0xFF1D3F7A))
        else -> Triple("Possible match", Color(0xFFFFF1D6), Color(0xFF6B4A00))
    }
    Surface(color = bg, contentColor = fg, shape = RoundedCornerShape(50)) {
        Text(label, Modifier.padding(horizontal = 10.dp, vertical = 4.dp), style = MaterialTheme.typography.labelMedium)
    }
}

@Composable
private fun GroupHeader(title: String, count: Int, cents: Long, claimed: Boolean) {
    val color = if (claimed) InProgressBlue else MaterialTheme.colorScheme.primary
    Row(Modifier.fillMaxWidth().padding(top = 8.dp).testTag(if (claimed) "groupClaimed" else "groupOpen"),
        verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(10.dp).background(color, RoundedCornerShape(5.dp)))
        Text("  $title ($count)", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold,
            color = color, modifier = Modifier.weight(1f))
        Text(dollars(cents), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** Blue for claims under way, so they stand apart from the green "money found" cards. */
private val InProgressBlue = Color(0xFF2563EB)

@Composable
private fun MatchCard(match: Match, onClick: () -> Unit) {
    val claimed = match.claimStatus != null
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().testTag("match${match.recordId}"),
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = if (claimed) InProgressBlue.copy(alpha = 0.07f)
            else MaterialTheme.colorScheme.surfaceContainerLowest),
        border = androidx.compose.foundation.BorderStroke(if (claimed) 1.5.dp else 1.dp,
            if (claimed) InProgressBlue.copy(alpha = 0.6f) else MaterialTheme.colorScheme.outlineVariant),
    ) { Row(Modifier.height(androidx.compose.foundation.layout.IntrinsicSize.Min)) { Box(Modifier.width(6.dp).fillMaxHeight().background(if (claimed) InProgressBlue else MaterialTheme.colorScheme.primary))
      Column(Modifier.padding(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(dollars(match.amountCents), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f))
            ConfidenceChip(match.confidence)
        }
        Spacer(Modifier.height(6.dp))
        match.onBehalfOf?.let {
            Pill("For $it", MaterialTheme.colorScheme.secondaryContainer, MaterialTheme.colorScheme.onSurface)
            Spacer(Modifier.height(6.dp))
        }
        Text("${match.county} County, ${match.state} · ${saleTypeLabel(match.saleType)}", fontWeight = FontWeight.SemiBold)
        Text("Listed owner: ${match.ownerName}", style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("Sold ${prettyDate(match.saleDate)} · ${match.reference}", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        val clock = match.clock()
        if (clock.urgency != "unknown") {
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                DeadlineChip(clock)
                clock.deadline?.takeIf { clock.urgency != "met" && clock.urgency != "expired" }?.let {
                    Text("  claim by ${prettyDate(it)}", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        match.claimStatus?.let {
            Spacer(Modifier.height(8.dp))
            Pill("Claim in progress · ${claimStatusLabel(it)}", InProgressBlue.copy(alpha = 0.14f), InProgressBlue,
                modifier = Modifier.testTag("claimedPill"))
        }
    } } }
}
