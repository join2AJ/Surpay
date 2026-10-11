package com.surpay.app.ui.screens

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.HourglassBottom
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.surpay.app.data.Deadline
import com.surpay.app.ui.prettyDate
import java.time.LocalDate
import java.time.temporal.ChronoUnit

/** Same thresholds as the server (surpay/legal.py). */
private const val FILE_BY_MARGIN_DAYS = 45L
private const val URGENT_DAYS = 60
private const val SOON_DAYS = 180
private val MET = setOf("filed", "hearing_pending", "approved", "paid")

/**
 * The legal clock worked out on the phone, for the offline demo and servers older than 0.5.
 * The server's version (with the state's own wording) is preferred whenever it's sent.
 */
fun localDeadline(saleDate: String?, deadlineDate: String?, status: String?, rule: String = "", ifMissed: String = ""): Deadline {
    if (status in MET) return Deadline("met", label = "Filed in time", rule = rule, ifMissed = ifMissed,
        message = "Your claim was filed before the deadline, so the deadline no longer applies. The court or county now decides.")
    val deadline = deadlineDate?.let { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() }
        ?: return Deadline("unknown", label = "Claim as soon as possible", message = rule, rule = rule, ifMissed = ifMissed)
    val sale = saleDate?.let { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() }
    val left = ChronoUnit.DAYS.between(LocalDate.now(), deadline).toInt()
    val total = sale?.let { ChronoUnit.DAYS.between(it, deadline).toInt().coerceAtLeast(1) }
    val fileBy = deadline.minusDays(FILE_BY_MARGIN_DAYS)
    val base = Deadline(deadline = deadline.toString(), fileBy = fileBy.toString(), saleDate = sale?.toString(),
        daysLeft = left, totalDays = total, elapsedPct = total?.let { ((100.0 * (it - left) / it).toInt()).coerceIn(0, 100) },
        rule = rule, ifMissed = ifMissed)
    val days = if (left == 1) "1 day" else "%,d days".format(left)
    return when {
        left < 0 -> base.copy(urgency = "expired", canClaim = false, label = "Deadline passed ${prettyDate(deadline.toString())}",
            message = "The deadline to claim this money has passed. $ifMissed")
        left <= URGENT_DAYS -> base.copy(urgency = "urgent", label = if (left == 0) "Last day to claim" else "$days left",
            message = "Only $days left. The claim must be filed by ${prettyDate(deadline.toString())}. Act today.")
        left <= SOON_DAYS -> base.copy(urgency = "soon", label = "$days left",
            message = "$days left. Start now so the attorney can file by ${prettyDate(fileBy.toString())}.")
        else -> base.copy(urgency = "safe", label = "$days left",
            message = "$days left to claim, until ${prettyDate(deadline.toString())}. Plenty of time, but don't wait.")
    }
}

/** Colours for each level, readable on light and dark backgrounds. */
data class UrgencyStyle(val color: Color, val container: Color, val icon: ImageVector, val title: String)

@Composable
fun urgencyStyle(urgency: String): UrgencyStyle {
    val dark = isSystemInDarkTheme()
    fun pick(light: Long, darkC: Long) = Color(if (dark) darkC else light)
    return when (urgency) {
        "urgent" -> UrgencyStyle(pick(0xFFB91C1C, 0xFFFF8A80), pick(0xFFFDECEC, 0xFF3A1416), Icons.Outlined.ErrorOutline, "Act now")
        "soon" -> UrgencyStyle(pick(0xFFB45309, 0xFFF6C26B), pick(0xFFFFF4E0, 0xFF33260F), Icons.Outlined.WarningAmber, "Don’t wait")
        "safe" -> UrgencyStyle(pick(0xFF15803D, 0xFF5BD68C), pick(0xFFE8F6EE, 0xFF0F2A1C), Icons.Outlined.Schedule, "Time to claim")
        "expired" -> UrgencyStyle(pick(0xFF6B7280, 0xFFA3AAB8), pick(0xFFF0F1F4, 0xFF1F2430), Icons.Outlined.HourglassBottom, "Deadline passed")
        "met" -> UrgencyStyle(pick(0xFF1D4ED8, 0xFF8AB4FF), pick(0xFFE8EFFE, 0xFF15213D), Icons.Outlined.CheckCircle, "Deadline met")
        else -> UrgencyStyle(pick(0xFF475569, 0xFFB0BACB), pick(0xFFF1F4F8, 0xFF1C2333), Icons.Outlined.Schedule, "Deadline")
    }
}

/** "123 days left" with a coloured dot: for list rows. */
@Composable
fun DeadlineChip(d: Deadline, modifier: Modifier = Modifier) {
    val s = urgencyStyle(d.urgency)
    Surface(color = s.container, contentColor = s.color, shape = RoundedCornerShape(50), modifier = modifier.testTag("deadlineChip")) {
        Row(Modifier.padding(horizontal = 10.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(s.color))
            Spacer(Modifier.width(6.dp))
            Text(d.label, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
        }
    }
}

/**
 * The full countdown: days left in big type, a timeline from the sale to the deadline with
 * today and the file-by date marked, what to do now, and what happens if it's missed.
 * [forAttorney] words it for the attorney who has to file.
 */
@Composable
fun DeadlineCard(d: Deadline, modifier: Modifier = Modifier, forAttorney: Boolean = false) {
    val s = urgencyStyle(d.urgency)
    var showMissed by rememberSaveable { mutableStateOf(d.urgency == "expired") }
    Surface(color = s.container, shape = RoundedCornerShape(20.dp),
        modifier = modifier.fillMaxWidth().border(1.dp, s.color.copy(alpha = 0.35f), RoundedCornerShape(20.dp))
            .animateContentSize().testTag("deadlineCard")) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(s.icon, null, tint = s.color)
                Spacer(Modifier.width(8.dp))
                Text(if (forAttorney && d.urgency in setOf("safe", "soon", "urgent")) "Time left to file" else s.title,
                    style = MaterialTheme.typography.labelLarge, color = s.color, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(6.dp))
            val big = d.daysLeft?.takeIf { it >= 0 && d.urgency != "met" }
            if (big != null) {
                Row(verticalAlignment = Alignment.Bottom) {
                    Text("%,d".format(big), style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Black,
                        color = s.color, modifier = Modifier.testTag("daysLeft"))
                    Text(if (big == 1) "  day left" else "  days left", style = MaterialTheme.typography.titleMedium,
                        color = s.color, modifier = Modifier.padding(bottom = 6.dp))
                }
            } else {
                Text(d.label, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = s.color)
            }
            if (d.deadline != null && d.urgency != "met") {
                Spacer(Modifier.height(12.dp))
                ClockTimeline(d, s.color)
            }
            Spacer(Modifier.height(12.dp))
            Text(d.message, style = MaterialTheme.typography.bodyMedium)
            if (d.ifMissed.isNotBlank() && d.urgency != "met") {
                Spacer(Modifier.height(8.dp))
                Text(if (showMissed) "What happens if the deadline is missed" else "What happens if the deadline is missed  ›",
                    style = MaterialTheme.typography.labelLarge, color = s.color, fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.clickable { showMissed = !showMissed }.padding(vertical = 4.dp).testTag("ifMissedToggle"))
                if (showMissed) Text(d.ifMissed, style = MaterialTheme.typography.bodySmall)
            }
            if (d.rule.isNotBlank() && d.urgency != "unknown") {
                Spacer(Modifier.height(6.dp))
                Text("The rule: ${d.rule}", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

/** Sale ●────●today────●file by──● deadline, filled up to today in the urgency colour. */
@Composable
private fun ClockTimeline(d: Deadline, color: Color) {
    val total = d.totalDays
    val todayFrac = (d.elapsedPct ?: 0) / 100f
    val fileByFrac = if (total != null && total > 0) (1f - FILE_BY_MARGIN_DAYS.toFloat() / total).coerceIn(0f, 1f) else 0.9f
    val track = MaterialTheme.colorScheme.outlineVariant
    Column(Modifier.testTag("deadlineTimeline")) {
        BoxWithConstraints(Modifier.fillMaxWidth().height(18.dp)) {
            val w = maxWidth
            Box(Modifier.align(Alignment.CenterStart).fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)).background(track))
            Box(Modifier.align(Alignment.CenterStart).fillMaxWidth(todayFrac.coerceIn(0.02f, 1f)).height(6.dp)
                .clip(RoundedCornerShape(3.dp)).background(color))
            Dot(Modifier.align(Alignment.CenterStart), color, 10)
            Dot(Modifier.align(Alignment.CenterStart).offset(x = w * fileByFrac - 5.dp), MaterialTheme.colorScheme.onSurfaceVariant, 10)
            Dot(Modifier.align(Alignment.CenterEnd), color, 12, ring = true)
            if (d.urgency != "expired") {
                Box(Modifier.align(Alignment.CenterStart).offset(x = (w * todayFrac - 9.dp).coerceAtLeast(0.dp))
                    .size(18.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surface)
                    .border(4.dp, color, CircleShape))
            }
        }
        Spacer(Modifier.height(6.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Mark("Sold", d.saleDate, TextAlign.Start)
            if (d.urgency != "expired") Mark("Aim to file by", d.fileBy, TextAlign.Center)
            Mark("Last day", d.deadline, TextAlign.End, bold = true)
        }
    }
}

@Composable
private fun Dot(modifier: Modifier, color: Color, size: Int, ring: Boolean = false) {
    Box(modifier.size(size.dp).clip(CircleShape).background(if (ring) MaterialTheme.colorScheme.surface else color)
        .then(if (ring) Modifier.border(3.dp, color, CircleShape) else Modifier))
}

@Composable
private fun Mark(title: String, iso: String?, align: TextAlign, bold: Boolean = false) {
    Column(horizontalAlignment = when (align) {
        TextAlign.Start -> Alignment.Start
        TextAlign.End -> Alignment.End
        else -> Alignment.CenterHorizontally
    }) {
        Text(title, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(iso?.let { prettyDate(it) } ?: "—", style = MaterialTheme.typography.labelMedium,
            fontWeight = if (bold) FontWeight.Bold else FontWeight.Medium, textAlign = align)
    }
}

/** A banner over a list when some money is close to its deadline. */
@Composable
fun DeadlineBanner(urgent: Int, soon: Int, modifier: Modifier = Modifier, forAttorney: Boolean = false) {
    if (urgent == 0 && soon == 0) return
    val s = urgencyStyle(if (urgent > 0) "urgent" else "soon")
    Surface(color = s.container, contentColor = s.color, shape = RoundedCornerShape(16.dp),
        modifier = modifier.fillMaxWidth().testTag("deadlineBanner")) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(s.icon, null)
            Spacer(Modifier.width(10.dp))
            Column {
                val what = if (forAttorney) "case" else "claim"
                Text(when {
                    urgent > 0 -> "$urgent ${what}${if (urgent == 1) "" else "s"} with 60 days or less to the deadline"
                    else -> "$soon ${what}${if (soon == 1) "" else "s"} with under 6 months left"
                }, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
                Text(if (forAttorney) "Most urgent cases are listed first." else "Money not claimed in time can be lost for good.",
                    style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

/** Colour key for the levels, shown under the countdown on the help screen and match list. */
@Composable
fun DeadlineLegend(modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        listOf("safe" to "6+ months", "soon" to "2–6 months", "urgent" to "≤ 60 days", "expired" to "Passed").forEach { (k, t) ->
            val s = urgencyStyle(k)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(8.dp).clip(CircleShape).background(s.color))
                Text(" $t", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

fun com.surpay.app.data.Match.clock(): Deadline =
    deadline ?: localDeadline(saleDate, deadlineDate, claimStatus, legal.deadline, legal.ifMissed)

fun com.surpay.app.data.Claim.clock(): Deadline =
    deadline ?: localDeadline(null, deadlineDate, status, legal.deadline, legal.ifMissed)

fun com.surpay.app.data.AttorneyCase.clock(): Deadline =
    deadline ?: localDeadline(saleDate, null, status, legal.deadline, legal.ifMissed)
