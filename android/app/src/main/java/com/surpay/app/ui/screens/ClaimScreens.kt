package com.surpay.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
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
import com.surpay.app.data.Claim
import com.surpay.app.data.TimelineStep
import com.surpay.app.ui.claimStatusLabel
import com.surpay.app.ui.dateRange
import com.surpay.app.ui.dollars
import com.surpay.app.ui.prettyDate

/** One claim: what to do next, every step with dates, and the estimate disclaimer. */
@Composable
fun ClaimScreen(
    claim: Claim,
    onVerifyIdentity: () -> Unit,
    onSignAgreement: () -> Unit,
    onViewAgreement: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text("${claim.county} County, ${claim.state} · ${claim.reference}", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(dollars(claim.amountCents), style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.ExtraBold)
        Text(
            "About ${dollars(claim.estimatedNetCents)} to you after our fee (estimate)",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(16.dp))

        NextActionCard(claim, onVerifyIdentity, onSignAgreement)

        if (claim.estimatedCompletionEnd != null) {
            Spacer(Modifier.height(16.dp))
            Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp)) {
                    Text("Estimated time to receive your money", style = MaterialTheme.typography.labelLarge)
                    Text(
                        dateRange(claim.estimatedCompletionStart, claim.estimatedCompletionEnd),
                        style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold,
                        modifier = Modifier.testTag("eta"),
                    )
                    Text("Typically 2–6 months in total. Some counties take longer.", style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        claim.attorney?.let { a ->
            Spacer(Modifier.height(16.dp))
            OutlinedCard(Modifier.fillMaxWidth().testTag("yourAttorney")) {
                Column(Modifier.padding(14.dp)) {
                    Text("Your attorney", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(a.name, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                    Text(listOf(a.firm, a.bar).filter { it.isNotBlank() }.joinToString(" · "), style = MaterialTheme.typography.bodySmall)
                    if (a.phone.isNotBlank()) Text(a.phone, style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        Spacer(Modifier.height(20.dp))
        Text("Your claim, step by step", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(8.dp))
        claim.timeline.forEachIndexed { i, step -> TimelineRow(step, isLast = i == claim.timeline.lastIndex) }

        LegalCard(claim.legal)
        Spacer(Modifier.height(12.dp))
        if (claim.status in setOf("agreement_signed", "identity_verified", "filed", "approved", "paid")) {
            OutlinedButton(onClick = onViewAgreement) { Text("View signed agreement") }
        }

        Spacer(Modifier.height(16.dp))
        Text(
            claim.disclaimer.ifBlank { "All amounts and dates are approximate estimates, not a promise or guarantee." },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.testTag("disclaimer"),
        )
        Spacer(Modifier.height(4.dp))
        Text(
            "Open this screen any time from “My claims” to see where things stand.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun NextActionCard(claim: Claim, onVerifyIdentity: () -> Unit, onSignAgreement: () -> Unit) {
    val (title, body, button, action) = when (claim.nextAction) {
        "verify_identity" -> Quad(
            if (claim.identityStatus == "rejected") "Please resubmit your ID" else "Verify your identity",
            if (claim.identityStatus == "rejected") {
                "We couldn’t verify your last submission: ${claim.identityNote.ifBlank { "please try again" }}"
            } else {
                "Takes about 5 minutes. You’ll need a government photo ID and your phone’s camera."
            },
            "Verify my identity", onVerifyIdentity,
        )
        "sign_agreement" -> Quad(
            "One step left: sign the agreement",
            "Review and e-sign the contingency agreement. No fee unless your money is recovered.",
            "Review and sign", onSignAgreement,
        )
        else -> null
    } ?: run {
        Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.medium, modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(14.dp)) {
                Text(claimStatusLabel(claim.status), fontWeight = FontWeight.Bold, modifier = Modifier.testTag("claimStatus"))
                Text(
                    "Nothing for you to do right now. We’ll update this timeline as your claim moves forward.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
        return
    }
    OutlinedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium, modifier = Modifier.testTag("nextActionTitle"))
            Spacer(Modifier.height(4.dp))
            Text(body, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(12.dp))
            Button(onClick = action, modifier = Modifier.fillMaxWidth().height(50.dp).testTag("nextAction")) {
                Text(button, fontWeight = FontWeight.Bold)
            }
        }
    }
}

private data class Quad(val a: String, val b: String, val c: String, val d: () -> Unit)

@Composable
private fun TimelineRow(step: TimelineStep, isLast: Boolean) {
    val done = step.state == "done"
    val current = step.state == "current"
    val dot = when {
        done -> MaterialTheme.colorScheme.primary
        current -> Color(0xFFE6A700)
        else -> MaterialTheme.colorScheme.outline
    }
    Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min)) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.width(28.dp)) {
            Box(Modifier.size(22.dp).background(dot, CircleShape), contentAlignment = Alignment.Center) {
                if (done) Icon(Icons.Filled.Check, null, tint = MaterialTheme.colorScheme.onPrimary, modifier = Modifier.size(14.dp))
            }
            if (!isLast) Box(Modifier.width(2.dp).fillMaxHeight().background(MaterialTheme.colorScheme.outline))
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.padding(bottom = 18.dp).weight(1f)) {
            Text(
                step.title,
                fontWeight = if (current) FontWeight.Bold else FontWeight.SemiBold,
                color = if (step.state == "upcoming") MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
            )
            val whenText = when {
                done -> "Done ${prettyDate(step.completedAt)}"
                step.estimateStart != null -> (if (current) "Now · est. " else "Est. ") + dateRange(step.estimateStart, step.estimateEnd)
                step.state == "stopped" -> "Not reached"
                else -> ""
            }
            if (whenText.isNotEmpty()) {
                Text(whenText, style = MaterialTheme.typography.labelMedium,
                    color = if (current) Color(0xFFB07F00) else MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (step.description.isNotBlank() && !done) {
                Text(step.description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

/** Every claim the person has started, with where each one stands. */
@Composable
fun ClaimsScreen(claims: List<Claim>?, onOpen: (Claim) -> Unit, onFindMoney: () -> Unit, modifier: Modifier = Modifier) {
    when {
        claims == null -> Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        claims.isEmpty() -> Column(modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally) {
            Text("No claims yet", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            Text("When you start a claim on one of your matches, you can follow it here, step by step.")
            Spacer(Modifier.height(12.dp))
            OutlinedButton(onClick = onFindMoney) { Text("See my matches") }
        }
        else -> LazyColumn(modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            items(claims, key = { it.id }) { c ->
                OutlinedCard(Modifier.fillMaxWidth().clickable { onOpen(c) }.testTag("claim${c.id}")) {
                    Column(Modifier.padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(dollars(c.amountCents), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold,
                                modifier = Modifier.weight(1f))
                            if (c.nextAction != null) {
                                Surface(color = Color(0xFFFFF1D6), contentColor = Color(0xFF6B4A00), shape = MaterialTheme.shapes.small) {
                                    Text("Action needed", Modifier.padding(horizontal = 8.dp, vertical = 2.dp), style = MaterialTheme.typography.labelMedium)
                                }
                            }
                        }
                        Text("${c.county} County, ${c.state} · ${c.reference}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(4.dp))
                        Text(claimStatusLabel(c.status), fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.primary)
                        if (c.estimatedCompletionEnd != null) {
                            Text("Est. money by ${dateRange(c.estimatedCompletionEnd, c.estimatedCompletionEnd)}",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            item {
                Text(
                    "All amounts and dates are approximate estimates, not a promise or guarantee.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
