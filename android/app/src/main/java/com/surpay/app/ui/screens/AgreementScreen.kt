package com.surpay.app.ui.screens

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
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

@Composable
fun AgreementScreen(
    agreement: AgreementDoc?,
    expectedName: String,
    form: FormState,
    onSign: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (agreement == null) {
        Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            if (form.error != null) Text(form.error, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(24.dp))
            else CircularProgressIndicator()
        }
        return
    }
    var agreed by rememberSaveable { mutableStateOf(false) }
    var signature by rememberSaveable { mutableStateOf("") }
    val nameOk = signature.trim().length >= 3

    Column(modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text(if (agreement.signed) "Your signed agreement" else "Review and sign", style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(4.dp))
        Text("Fee: ${agreement.feePct.let { if (it % 1.0 == 0.0) it.toInt().toString() else it.toString() }}% of what’s " +
            "recovered, only if money is recovered. Nothing upfront.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(12.dp))
        OutlinedCard(Modifier.fillMaxWidth()) {
            Text(agreement.text, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Serif,
                modifier = Modifier.padding(14.dp).testTag("agreementText"))
        }
        Spacer(Modifier.height(16.dp))

        if (agreement.signed) {
            Text("Signed electronically by ${agreement.signatureName} on ${prettyDate(agreement.signedAt)}.",
                fontStyle = FontStyle.Italic)
            return@Column
        }

        Row(verticalAlignment = Alignment.Top) {
            Checkbox(checked = agreed, onCheckedChange = { agreed = it }, modifier = Modifier.testTag("agree"))
            Text("I have read and agree to this agreement, and I understand I can claim these funds myself for free.",
                style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 12.dp))
        }
        OutlinedTextField(
            value = signature, onValueChange = { signature = it }, singleLine = true,
            label = { Text("Type your full legal name to sign") },
            placeholder = { Text(expectedName) },
            textStyle = MaterialTheme.typography.titleMedium.copy(fontFamily = FontFamily.Cursive),
            modifier = Modifier.fillMaxWidth().testTag("signature"),
        )
        form.error?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = { onSign(signature.trim()) },
            enabled = agreed && nameOk && !form.busy,
            modifier = Modifier.fillMaxWidth().height(52.dp).testTag("sign"),
        ) {
            if (form.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            else Text("Sign agreement", fontWeight = FontWeight.Bold)
        }
        Text(
            "Your typed name is your legal electronic signature. You can cancel within 3 business days at no cost.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}
