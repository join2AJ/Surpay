package com.surpay.app.ui

import java.text.NumberFormat
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private val usd: NumberFormat = NumberFormat.getCurrencyInstance(Locale.US)

fun dollars(cents: Long): String = usd.format(cents / 100.0)

fun prettyDate(iso: String?): String = iso?.let {
    runCatching { LocalDate.parse(it.take(10)).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US)) }
        .getOrDefault(it)
} ?: "Unknown"

fun saleTypeLabel(type: String): String = when (type) {
    "tax_sale" -> "Tax sale"
    "mortgage_foreclosure" -> "Mortgage foreclosure"
    else -> type.replace('_', ' ').replaceFirstChar { it.uppercase() }
}

fun claimStatusLabel(status: String): String = when (status) {
    "requested" -> "Claim started: verify your identity"
    "identity_submitted" -> "ID submitted: sign the agreement"
    "agreement_signed" -> "Agreement signed: ID under review"
    "identity_verified" -> "Identity verified: preparing filing"
    "filed" -> "Filed with the county or court"
    "approved" -> "Approved: funds being released"
    "paid" -> "Paid"
    "denied" -> "Claim denied"
    "withdrawn" -> "Withdrawn"
    else -> status
}

private val SHORT = DateTimeFormatter.ofPattern("MMM d", Locale.US)
private val LONG = DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US)

/** "Oct 10 – Nov 2, 2026", or one date when both ends match. */
fun dateRange(start: String?, end: String?): String {
    val a = start?.let { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() } ?: return ""
    val b = end?.let { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() } ?: a
    return when {
        a == b -> a.format(LONG)
        a.year == b.year -> "${a.format(SHORT)} – ${b.format(LONG)}"
        else -> "${a.format(LONG)} – ${b.format(LONG)}"
    }
}

val US_STATES = listOf(
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM",
    "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
)
