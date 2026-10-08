package com.surpay.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.surpay.app.data.Match
import com.surpay.app.ui.claimStatusLabel
import com.surpay.app.ui.deadlineText
import com.surpay.app.ui.dollars
import com.surpay.app.ui.prettyDate
import com.surpay.app.ui.saleTypeLabel

@Composable
fun MatchDetailScreen(
    match: Match,
    claiming: Boolean,
    error: String?,
    onStartClaim: () -> Unit,
    onViewClaim: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val uri = LocalUriHandler.current
    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
    ) {
        ConfidenceChip(match.confidence)
        Spacer(Modifier.height(10.dp))
        HeroCard {
            Text("Surplus held by ${match.county} County, ${match.state}", style = MaterialTheme.typography.bodyMedium)
            Text(dollars(match.amountCents), style = MaterialTheme.typography.displaySmall)
            match.onBehalfOf?.let {
                Spacer(Modifier.height(6.dp))
                Text("For $it", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
            }
        }
        deadlineText(match.deadlineDate)?.let {
            Spacer(Modifier.height(10.dp))
            NoteBox(it + ". " + match.legal.ifMissed.ifBlank { "" })
        }
        Spacer(Modifier.height(12.dp))

        SectionCard {
            Line("Surplus amount", dollars(match.amountCents))
            Line("Fee (${formatPct(match.feePct)}, only if recovered)", "− ${dollars(match.estimatedFeeCents)}")
            HorizontalDivider(Modifier.padding(vertical = 8.dp))
            Line("Estimated to you", dollars(match.estimatedNetCents), bold = true)
        }
        Spacer(Modifier.height(16.dp))

        Text("Record details", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(6.dp))
        Detail("Listed owner", match.ownerName)
        if (match.ownerAddress.isNotBlank()) Detail("Address on record", match.ownerAddress)
        Detail("Sale", "${saleTypeLabel(match.saleType)} on ${prettyDate(match.saleDate)}")
        Detail("Reference", match.reference)
        Detail("Last confirmed on county list", prettyDate(match.lastSeen))
        if (match.sourceUrl.isNotBlank()) {
            TextButton(onClick = { uri.openUri(match.sourceUrl) }) { Text("View the county’s list yourself") }
        }

        Spacer(Modifier.height(12.dp))
        LegalCard(match.legal, deadlineDate = match.deadlineDate, familyBasis = familyBasisOf(match.onBehalfOf))
        Spacer(Modifier.height(12.dp))
        Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.medium) {
            Text(
                "You can claim this money yourself, for free, by contacting the ${match.county} County " +
                    "office that holds it. If you’d rather not, an independent licensed attorney files the claim for you " +
                    "and you pay nothing unless it succeeds. Surpay is a technology platform, not a law firm. Other " +
                    "lienholders may have a claim to part of the funds.",
                Modifier.padding(14.dp),
                style = MaterialTheme.typography.bodySmall,
            )
        }

        error?.let {
            Spacer(Modifier.height(12.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(16.dp))
        if (match.claimStatus != null) {
            Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium, modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Text(claimStatusLabel(match.claimStatus), fontWeight = FontWeight.Bold, modifier = Modifier.testTag("claimStatus"))
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = onViewClaim, modifier = Modifier.fillMaxWidth().testTag("viewClaim")) {
                        Text("View my claim and timeline")
                    }
                }
            }
        } else {
            Button(
                onClick = onStartClaim,
                enabled = !claiming,
                modifier = Modifier.fillMaxWidth().height(52.dp).testTag("startClaim"),
            ) {
                if (claiming) {
                    CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                } else {
                    Text(if (match.onBehalfOf != null) "Start the claim for my family member" else "This is me: start my claim",
                        fontWeight = FontWeight.Bold)
                }
            }
            Spacer(Modifier.height(6.dp))
            Text(
                "Next you’ll verify your identity and e-sign the agreement in the app (about 5 minutes). " +
                    "Starting is free and you pay nothing unless money is recovered.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.height(16.dp))
        Text(
            "The amounts above are approximate estimates, not a promise or guarantee. The final amount " +
                "depends on the county or court, other lienholders and fees.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.testTag("disclaimer"),
        )
    }
}

private fun formatPct(p: Double) = if (p % 1.0 == 0.0) "${p.toInt()}%" else "$p%"

@Composable
private fun Line(label: String, value: String, bold: Boolean = false) {
    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
        Text(label, Modifier.weight(1f), fontWeight = if (bold) FontWeight.Bold else null)
        Text(value, fontWeight = if (bold) FontWeight.Bold else FontWeight.Medium)
    }
}

@Composable
private fun Detail(label: String, value: String) {
    Column(Modifier.padding(vertical = 4.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}
