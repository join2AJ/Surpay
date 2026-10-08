package com.surpay.app.ui.screens

import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Chat
import androidx.compose.material.icons.outlined.AccountBalance
import androidx.compose.material.icons.outlined.Gavel
import androidx.compose.material.icons.outlined.NewReleases
import androidx.compose.material.icons.outlined.VerifiedUser
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.surpay.app.ui.theme.HeroGradient
import kotlinx.coroutines.launch

private data class IntroPage(val icon: ImageVector, val title: String, val body: String, val points: List<String>)

private val PAGES = listOf(
    IntroPage(
        Icons.Outlined.AccountBalance,
        "Money from a home sale may be waiting for you",
        "When a home is sold at a tax or foreclosure auction for more than was owed, the extra money belongs to " +
            "the former owner. Counties hold billions of dollars of it, and most owners never hear about it.",
        listOf("We check county surplus lists every day", "Search under your name and every home you've owned"),
    ),
    IntroPage(
        Icons.Outlined.VerifiedUser,
        "Only you can see your money",
        "Before any result is shown, we verify your photo ID and a selfie. Nobody, including brokers, can use " +
            "Surpay to look someone else up.",
        listOf("ID and documents encrypted", "Every action recorded in a tamper-proof log"),
    ),
    IntroPage(
        Icons.Outlined.Gavel,
        "A licensed attorney files your claim",
        "Sign the agreement in the app and a licensed attorney in that county takes your case. Nothing upfront: " +
            "a fee only if money is recovered. You can always claim it yourself, free.",
        listOf("See the law that entitles you", "Know your deadline and what to prove"),
    ),
    IntroPage(
        Icons.AutoMirrored.Outlined.Chat,
        "Follow every step",
        "Your claim's timeline shows each stage with estimated dates. Message your attorney in the app, and get " +
            "a notification when your money is released.",
        listOf("Filed, hearing, approved, money released", "Private messages with your attorney"),
    ),
)

/** First launch only: what Surpay is, in four swipeable pages. */
@Composable
fun IntroScreen(onDone: () -> Unit) {
    val pager = rememberPagerState { PAGES.size }
    val scope = rememberCoroutineScope()
    val last = pager.currentPage == PAGES.lastIndex
    Column(Modifier.fillMaxSize().systemBarsPadding().testTag("intro")) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Logo()
            Spacer(Modifier.weight(1f))
            if (!last) TextButton(onClick = onDone, modifier = Modifier.testTag("introSkip")) { Text("Skip") }
        }
        HorizontalPager(pager, Modifier.weight(1f)) { i ->
            val p = PAGES[i]
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 28.dp),
                verticalArrangement = Arrangement.Center) {
                Box(Modifier.size(120.dp).clip(CircleShape).background(HeroGradient).align(Alignment.CenterHorizontally),
                    contentAlignment = Alignment.Center) {
                    Icon(p.icon, null, tint = androidx.compose.ui.graphics.Color.White, modifier = Modifier.size(56.dp))
                }
                Spacer(Modifier.height(32.dp))
                Text(p.title, style = MaterialTheme.typography.headlineMedium, textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(12.dp))
                Text(p.body, style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(20.dp))
                p.points.forEach {
                    Text("✓  $it", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.primary, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                PAGES.indices.forEach { i ->
                    Box(Modifier.height(8.dp).width(if (i == pager.currentPage) 22.dp else 8.dp).clip(CircleShape)
                        .background(if (i == pager.currentPage) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline))
                }
            }
            Spacer(Modifier.weight(1f))
            Button(
                onClick = { if (last) onDone() else scope.launch { pager.animateScrollToPage(pager.currentPage + 1) } },
                modifier = Modifier.height(50.dp).testTag("introNext"),
            ) { Text(if (last) "Get started" else "Next", fontWeight = FontWeight.Bold) }
        }
    }
}

/** What changed in each version, newest first. Shown once after an update. */
val CHANGELOG: List<Pair<Int, List<String>>> = listOf(
    2 to listOf(
        "A short intro on first launch, and this “What’s new” after each update",
        "Clear start: choose “Find my money” or “I’m an attorney”",
        "Sign agreements with your finger, and your typed name must match your ID",
        "New claim steps: attorney assigned, waiting for the county or court, hearing approved, money released",
        "Notifications when your claim moves forward or your money is released",
        "Private in-app messages with your attorney (contact details can’t be shared)",
        "Claim for a family member who has died, as their heir",
        "Your deadline to claim, and what happens if it’s missed",
        "Privacy and data: download your data, delete your account, sign out everywhere",
        "Stronger security: more encryption and a tamper-proof activity log",
        "For attorneys: step-by-step filing guide and a printable claim packet",
    ),
)

@Composable
fun WhatsNewDialog(fromVersion: Int, onDismiss: () -> Unit) {
    val items = CHANGELOG.filter { it.first > fromVersion }.flatMap { it.second }
    if (items.isEmpty()) {
        androidx.compose.runtime.LaunchedEffect(Unit) { onDismiss() }
        return
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Outlined.NewReleases, null) },
        title = { Text("What’s new in this version") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items.forEach { Text("•  $it", style = MaterialTheme.typography.bodyMedium) }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss, modifier = Modifier.testTag("whatsNewOk")) { Text("Got it") } },
    )
}
