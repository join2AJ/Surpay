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
    "requested" -> "Claim requested"
    "identity_verified" -> "Identity verified"
    "agreement_signed" -> "Agreement signed"
    "filed" -> "Filed with the court"
    "approved" -> "Approved"
    "paid" -> "Paid"
    "denied" -> "Denied"
    else -> status
}

val US_STATES = listOf(
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM",
    "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
)
