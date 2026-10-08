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
import androidx.compose.material.icons.automirrored.outlined.Chat
import androidx.compose.material.icons.outlined.Gavel
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
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
import com.surpay.app.ui.deadlineText
import com.surpay.app.ui.theme.Gold
import com.surpay.app.ui.dollars
import com.surpay.app.ui.prettyDate

/** One claim: what to do next, every step with dates, the attorney, and the estimate disclaimer. */
@Composable
fun ClaimScreen(
    claim: Claim,
    onVerifyIdentity: () -> Unit,
    onSignAgreement: () -> Unit,
    onViewAgreement: () -> Unit,
    onMessages: () -> Unit = {},
    onWithdraw: () -> Unit = {},
    busy: Boolean = false,
    modifier: Modifier = Modifier,
) {
    var confirmWithdraw by rememberSaveable { mutableStateOf(false) }
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
        HeroCard {
            Text("${claim.county} County, ${claim.state} · ${claim.reference}", style = MaterialTheme.typography.bodyMedium)
            Text(dollars(claim.amountCents), style = MaterialTheme.typography.displaySmall)
            Text("About ${dollars(claim.estimatedNetCents)} to you after the ${pct(claim.feePct)} fee (estimate)",
                style = MaterialTheme.typography.bodyMedium)
            claim.onBehalfOf?.let {
                Spacer(Modifier.height(8.dp))
                Pill("For $it", Color.White.copy(alpha = 0.18f), Color.White)
            }
            if (claim.status == "paid") {
                Spacer(Modifier.height(8.dp))
                Pill("🎉 Money released", Gold, Color(0xFF3A2C0B))
            }
        }
        Spacer(Modifier.height(16.dp))

        NextActionCard(claim, onVerifyIdentity, onSignAgreement)

        if (claim.estimatedCompletionEnd != null && claim.status !in setOf("paid", "denied", "withdrawn")) {
            Spacer(Modifier.height(12.dp))
            SectionCard {
                Text("Estimated time to receive your money", style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(
                    dateRange(claim.estimatedCompletionStart, claim.estimatedCompletionEnd),
                    style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold,
                    modifier = Modifier.testTag("eta"),
                )
                Text("Typically 2 to 6 months in total. Some counties take longer.", style = MaterialTheme.typography.bodySmall)
                deadlineText(claim.deadlineDate)?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 4.dp))
                }
            }
        }

        claim.attorney?.let { a ->
            Spacer(Modifier.height(12.dp))
            SectionCard(modifier = Modifier.testTag("yourAttorney")) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconCircle(Icons.Outlined.Gavel)
                    Column(Modifier.weight(1f).padding(start = 12.dp)) {
                        Text("Your attorney", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(a.name, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                        Text(listOf(a.firm, a.bar).filter { it.isNotBlank() }.joinToString(" · "), style = MaterialTheme.typography.bodySmall)
                    }
                }
                if (claim.chatOpen) {
                    Spacer(Modifier.height(10.dp))
                    Button(onClick = onMessages, modifier = Modifier.fillMaxWidth().testTag("openChat")) {
                        BadgedBox(badge = { if (claim.unreadMessages > 0) Badge { Text("${claim.unreadMessages}") } }) {
                            Icon(Icons.AutoMirrored.Outlined.Chat, null)
                        }
                        Text("   Messages with your attorney")
                    }
                }
            }
        }
        Spacer(Modifier.height(20.dp))
        Text("Your claim, step by step", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(10.dp))
        claim.timeline.forEachIndexed { i, step -> TimelineRow(step, isLast = i == claim.timeline.lastIndex) }

        LegalCard(claim.legal, deadlineDate = claim.deadlineDate,
            familyBasis = familyBasisOf(claim.onBehalfOf))
        Spacer(Modifier.height(12.dp))
        if (claim.status !in setOf("requested", "identity_submitted")) {
            OutlinedButton(onClick = onViewAgreement, modifier = Modifier.fillMaxWidth()) { Text("View signed agreement") }
        }
        if (claim.status in setOf("requested", "identity_submitted", "agreement_signed", "identity_verified", "attorney_assigned")) {
            if (!confirmWithdraw) {
                TextButton(onClick = { confirmWithdraw = true }, modifier = Modifier.testTag("withdraw")) {
                    Text("Cancel this claim", color = MaterialTheme.colorScheme.error)
                }
            } else {
                NoteBox("Cancel this claim? You won’t owe anything. You can still claim the money yourself from the county.")
                Row {
                    TextButton(onClick = { onWithdraw(); confirmWithdraw = false }, enabled = !busy,
                        modifier = Modifier.testTag("confirmWithdraw")) { Text("Yes, cancel it", color = MaterialTheme.colorScheme.error) }
                    TextButton(onClick = { confirmWithdraw = false }) { Text("Keep my claim") }
                }
            }
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
            "Surpay is a technology platform, not a law firm. Your claim is made by you through your independent " +
                "attorney, who is responsible for the legal work.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

/** "Mary Parent (your parent, as heir)" -> "heir"; the server writes on_behalf_of in that form. */
fun familyBasisOf(onBehalfOf: String?): String? = onBehalfOf?.let { b ->
    listOf("heir", "power_of_attorney", "guardian").firstOrNull { b.contains(it.replace('_', ' ')) }
}

private fun pct(p: Double) = if (p % 1.0 == 0.0) "${p.toInt()}%" else "$p%"

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
        done && step.status == "paid" -> Gold
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
                SectionCard(onClick = { onOpen(c) }, modifier = Modifier.testTag("claim${c.id}")) {
                    Column {
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
                        c.onBehalfOf?.let { Text("For $it", style = MaterialTheme.typography.bodySmall) }
                        if (c.unreadMessages > 0) {
                            Text("${c.unreadMessages} new message(s) from your attorney", style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                        }
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
