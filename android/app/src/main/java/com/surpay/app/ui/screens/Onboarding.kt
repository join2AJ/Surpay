package com.surpay.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.outlined.HourglassTop
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.surpay.app.data.MatchPreview
import com.surpay.app.data.Profile
import kotlinx.coroutines.delay

val ONBOARDING_STEPS = listOf("Account", "Verify ID", "Your homes", "Review")

/** "Step 2 of 4 · Verify ID" with a progress bar and the step names. */
@Composable
fun OnboardingHeader(step: Int, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp)) {
        Text(
            "Step ${step + 1} of ${ONBOARDING_STEPS.size} · ${ONBOARDING_STEPS[step]}",
            style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.testTag("onboardingStep"),
        )
        Spacer(Modifier.height(8.dp))
        LinearProgressIndicator(
            progress = { (step + 1f) / ONBOARDING_STEPS.size },
            modifier = Modifier.fillMaxWidth().height(6.dp),
            strokeCap = androidx.compose.ui.graphics.StrokeCap.Round,
        )
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            ONBOARDING_STEPS.forEachIndexed { i, name ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        shape = CircleShape,
                        color = if (i <= step) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant,
                        modifier = Modifier.size(16.dp),
                    ) {
                        if (i < step) Icon(Icons.Filled.Check, null, tint = MaterialTheme.colorScheme.onPrimary, modifier = Modifier.padding(2.dp))
                    }
                    Text(" $name", style = MaterialTheme.typography.labelSmall,
                        color = if (i == step) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/** Shown after ID and homes are in, until staff approve the ID. Nothing about the records leaks. */
@Composable
fun VerifyingScreen(
    profile: Profile,
    preview: MatchPreview?,
    onRefresh: () -> Unit,
    onEditHomes: () -> Unit,
    onLogout: () -> Unit,
) {
    // Check every 30 seconds while this screen is open.
    LaunchedEffect(Unit) {
        while (true) {
            onRefresh()
            delay(30_000)
        }
    }
    Column(Modifier.fillMaxSize().systemBarsPadding().verticalScroll(rememberScrollState())) {
        OnboardingHeader(step = 3)
        Column(Modifier.padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.size(72.dp)) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.HourglassTop, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(36.dp))
                }
            }
            Spacer(Modifier.height(16.dp))
            Text("We’re verifying your identity", style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold, textAlign = TextAlign.Center, modifier = Modifier.testTag("verifyingTitle"))
            Spacer(Modifier.height(8.dp))
            Text(
                "Usually within 1 business day. To protect people’s money, results are only shown to " +
                    "the verified owner. Nobody can look up someone else.",
                textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(20.dp))

            if (preview != null && preview.possibleMatches > 0) {
                Surface(color = MaterialTheme.colorScheme.primary, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(18.dp)) {
                        Text("Good news", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onPrimary)
                        Text(
                            "We found ${preview.possibleMatches} possible ${if (preview.possibleMatches == 1) "record" else "records"} under your name",
                            style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onPrimary, modifier = Modifier.testTag("previewCount"),
                        )
                        Text("Amounts and details unlock as soon as you’re verified.",
                            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onPrimary)
                    }
                }
            } else {
                OutlinedCard(Modifier.fillMaxWidth()) {
                    Text(
                        "No records under your name in the counties we track yet. We add counties every week and " +
                            "will check again automatically.",
                        Modifier.padding(16.dp), style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }

            Spacer(Modifier.height(20.dp))
            OutlinedCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("What happens next", fontWeight = FontWeight.SemiBold)
                    NextStep("1", "Our team checks your ID and selfie (usually within 1 business day).")
                    NextStep("2", "You see every record that matches you, with amounts and the law that entitles you to it.")
                    NextStep("3", "Start a claim and e-sign. A licensed attorney files it with the county.")
                }
            }
            Spacer(Modifier.height(16.dp))
            Button(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) { Text("Check status now") }
            OutlinedButton(onClick = onEditHomes, modifier = Modifier.fillMaxWidth()) {
                Text("Add or edit homes (${profile.addresses.size} listed)")
            }
            TextButton(onClick = onLogout) { Text("Sign out") }
        }
    }
}

@Composable
private fun NextStep(n: String, text: String) {
    Row(verticalAlignment = Alignment.Top) {
        Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.size(24.dp)) {
            Box(contentAlignment = Alignment.Center) {
                Text(n, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
            }
        }
        Spacer(Modifier.size(10.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium)
    }
}
