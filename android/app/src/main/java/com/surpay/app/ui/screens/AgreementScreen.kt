package com.surpay.app.ui.screens

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.outlined.Fingerprint
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.surpay.app.data.AgreementDoc
import com.surpay.app.ui.FormState
import com.surpay.app.ui.prettyDate

/** Letters and spaces only, lower-case, single-spaced: how the server compares a typed name to the ID. */
fun normalizeName(s: String) = s.lowercase().filter { it.isLetterOrDigit() || it.isWhitespace() }.split(Regex("\\s+"))
    .filter { it.isNotEmpty() }.joinToString(" ")

@Composable
fun AgreementScreen(
    agreement: AgreementDoc?,
    expectedName: String,
    form: FormState,
    onSign: (name: String, signaturePng: ByteArray) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (agreement == null) {
        Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            if (form.error != null) Text(form.error, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(24.dp))
            else CircularProgressIndicator()
        }
        return
    }
    val legalName = agreement.expectedName.ifBlank { expectedName }
    var agreed by rememberSaveable { mutableStateOf(false) }
    var typed by rememberSaveable { mutableStateOf("") }
    val pad = rememberSignatureState()
    val nameOk = normalizeName(typed).isNotEmpty() && normalizeName(typed) == normalizeName(legalName)
    val pct = agreement.feePct.let { if (it % 1.0 == 0.0) it.toInt().toString() else it.toString() }

    Column(modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text(if (agreement.signed) "Your signed agreement" else "Review and sign", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(10.dp))
        HeroCard {
            Text("Fee: $pct% of what’s recovered", style = MaterialTheme.typography.titleLarge)
            Text("Only if money is recovered. Nothing upfront, no other charges.", style = MaterialTheme.typography.bodyMedium)
        }
        Spacer(Modifier.height(12.dp))
        SectionCard(padding = 0.dp) {
            Column(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()).padding(16.dp)) {
                Text(agreement.text, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Serif,
                    modifier = Modifier.testTag("agreementText"))
            }
        }
        if (agreement.documentSha256.isNotBlank()) {
            Row(Modifier.padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Fingerprint, null, Modifier.size(14.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(" Document fingerprint ${agreement.documentSha256.take(16)}…", style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Spacer(Modifier.height(16.dp))

        if (agreement.signed) {
            Text("Signed electronically by ${agreement.signatureName} on ${prettyDate(agreement.signedAt)}.", fontStyle = FontStyle.Italic)
            return@Column
        }

        SectionLabel("1. Type your full legal name")
        OutlinedTextField(
            value = typed, onValueChange = { typed = it }, singleLine = true,
            label = { Text("Exactly as on your ID") },
            placeholder = { Text(legalName) },
            supportingText = {
                when {
                    typed.isBlank() -> Text("Must match: $legalName")
                    nameOk -> Text("Matches your verified ID", color = MaterialTheme.colorScheme.primary)
                    else -> Text("Doesn’t match your ID ($legalName)", color = MaterialTheme.colorScheme.error)
                }
            },
            trailingIcon = { if (nameOk) Icon(Icons.Filled.CheckCircle, null, tint = MaterialTheme.colorScheme.primary) },
            textStyle = MaterialTheme.typography.titleMedium.copy(fontFamily = FontFamily.Cursive),
            isError = typed.isNotBlank() && !nameOk,
            modifier = Modifier.fillMaxWidth().testTag("signature"),
        )
        SectionLabel("2. Draw your signature")
        SignaturePad(pad)
        Row {
            TextButton(onClick = { pad.clear() }, modifier = Modifier.testTag("clearSignature")) { Text("Clear") }
        }
        Row(verticalAlignment = Alignment.Top) {
            Checkbox(checked = agreed, onCheckedChange = { agreed = it }, modifier = Modifier.testTag("agree"))
            Text("I have read and agree to this agreement. I understand Surpay is not a law firm and that I can claim " +
                "these funds myself for free.", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 12.dp))
        }
        form.error?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = { onSign(typed.trim(), pad.toPng()) },
            enabled = agreed && nameOk && !pad.isEmpty && !form.busy,
            modifier = Modifier.fillMaxWidth().height(54.dp).testTag("sign"),
        ) {
            if (form.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            else Text("Sign agreement", fontWeight = FontWeight.Bold)
        }
        Text(
            "Your drawn signature and typed name are your legal electronic signature. The time, IP address and device " +
                "are recorded with a fingerprint of this document as proof of signing. You can cancel within 3 business " +
                "days at no cost.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}
