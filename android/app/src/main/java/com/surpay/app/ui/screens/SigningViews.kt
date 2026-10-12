package com.surpay.app.ui.screens

import android.graphics.Bitmap
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.Email
import androidx.compose.material.icons.outlined.Fingerprint
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Smartphone
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.surpay.app.data.ActivityEntry
import com.surpay.app.data.CodeSent
import com.surpay.app.data.FormPrefill
import com.surpay.app.data.SignedDoc
import com.surpay.app.data.VerifyState
import com.surpay.app.ui.FormState
import com.surpay.app.ui.prettyDate
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Confirm it's you before signing: a 6-digit code to your email and one to your phone. A test server
 * (which can't send real messages) shows the code, with a button to fill it in.
 */
@Composable
fun TwoFactorPanel(
    state: VerifyState?,
    sent: Map<String, CodeSent>,
    busy: Boolean,
    onSend: (String) -> Unit,
    onConfirm: (String, String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val ready = state?.readyToSign == true
    Surface(
        color = if (ready) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainer,
        shape = RoundedCornerShape(16.dp), modifier = modifier.fillMaxWidth().testTag("twoFactor"),
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(if (ready) Icons.Filled.CheckCircle else Icons.Outlined.Fingerprint, null,
                    tint = MaterialTheme.colorScheme.primary)
                Text(if (ready) "  It’s you: ready to sign" else "  Confirm it’s you",
                    fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleSmall)
            }
            if (!ready) {
                Text("We send a code to your email and to your phone. Both are recorded with your signature.",
                    style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 4.dp))
            }
            listOf("email" to Icons.Outlined.Email, "phone" to Icons.Outlined.Smartphone).forEach { (ch, icon) ->
                val channel = if (ch == "email") state?.email else state?.phone
                Spacer(Modifier.height(10.dp))
                CodeRow(ch, icon, channel?.destination.orEmpty(), channel?.fresh == true, sent[ch], busy, onSend, onConfirm)
            }
        }
    }
}

@Composable
private fun CodeRow(
    channel: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    destination: String,
    confirmed: Boolean,
    sent: CodeSent?,
    busy: Boolean,
    onSend: (String) -> Unit,
    onConfirm: (String, String) -> Unit,
) {
    var code by rememberSaveable(channel) { mutableStateOf("") }
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, Modifier.size(20.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("  ${if (channel == "email") "Email" else "Phone"} ${destination.ifBlank { sent?.sentTo.orEmpty() }}",
                Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
            if (confirmed) {
                Text("✓ Confirmed", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelLarge, modifier = Modifier.testTag("${channel}Confirmed"))
            } else {
                TextButton(onClick = { onSend(channel) }, enabled = !busy, modifier = Modifier.testTag("send_$channel")) {
                    Text(if (sent == null) "Send code" else "Resend")
                }
            }
        }
        if (!confirmed && sent != null) {
            sent.testCode?.let { test ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Test server: your code is $test", style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.tertiary, modifier = Modifier.weight(1f).testTag("testCode_$channel"))
                    TextButton(onClick = { code = test }, modifier = Modifier.testTag("useCode_$channel")) { Text("Use it") }
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(code, { code = it.filter(Char::isDigit).take(6) }, singleLine = true,
                    label = { Text("6-digit code") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                    modifier = Modifier.weight(1f).testTag("code_$channel"))
                Spacer(Modifier.width(8.dp))
                Button(onClick = { onConfirm(channel, code) }, enabled = code.length == 6 && !busy,
                    modifier = Modifier.testTag("confirm_$channel")) { Text("Confirm") }
            }
        }
    }
}

/** The fields each in-app form asks for, with labels and help. */
private data class FieldSpec(val key: String, val label: String, val help: String = "", val readOnly: Boolean = false,
                             val secret: Boolean = false, val multiline: Boolean = false, val optional: Boolean = false)

private fun specs(kind: String) = when (kind) {
    "w9" -> listOf(
        FieldSpec("name", "1. Name (as on your ID and tax return)", readOnly = true),
        FieldSpec("business_name", "2. Business name, if different", optional = true),
        FieldSpec("address", "5. Street address"),
        FieldSpec("city_state_zip", "6. City, state and ZIP"),
        FieldSpec("ssn", "Social Security number (or ITIN)", "All 9 digits. It must end in the last 4 you gave when "
            + "you verified your ID. Encrypted, and only ever printed on this form.", secret = true),
        FieldSpec("requester", "Requester (the office paying you)", readOnly = true),
        FieldSpec("account_numbers", "7. Account numbers", readOnly = true),
    )
    "heirship_affidavit" -> listOf(
        FieldSpec("name", "Your name (as on your ID)", readOnly = true),
        FieldSpec("current_address", "Your address"),
        FieldSpec("deceased", "The owner who died", readOnly = true),
        FieldSpec("relationship", "How you’re related to them"),
        FieldSpec("date_of_death", "Date of death"),
        FieldSpec("heirs", "All the heirs and how each is related", "For example: “Sam Child (son), Alex Child (daughter)”",
            multiline = true),
        FieldSpec("will", "If there was a will, where it is and who it names", optional = true, multiline = true),
        FieldSpec("probate", "Any probate case (court and number)", optional = true),
    )
    else -> listOf(
        FieldSpec("name", "Your name (as on your ID)", readOnly = true),
        FieldSpec("current_address", "Where you live now"),
        FieldSpec("property_address", "The property that was sold"),
        FieldSpec("reference", "County reference", readOnly = true),
        FieldSpec("other_owners", "Anyone else who owned it with you", "Leave empty if you were the only owner",
            optional = true),
        FieldSpec("liens", "Mortgages or liens you know of", "Leave empty if none", optional = true),
    )
}

/**
 * Fill in and sign a form in the app (W-9 or affidavit). We fill in what we already know; the
 * client checks it, completes the rest, confirms the two codes, draws a signature and signs.
 */
@Composable
fun FormSignScreen(
    prefill: FormPrefill?,
    verify: VerifyState?,
    sent: Map<String, CodeSent>,
    form: FormState,
    onSend: (String) -> Unit,
    onConfirm: (String, String) -> Unit,
    onSign: (Map<String, String>, ByteArray) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (prefill == null) {
        Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            form.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(24.dp)) }
                ?: CircularProgressIndicator()
        }
        return
    }
    val values = remember(prefill.kind) { mutableStateMapOf<String, String>().apply { putAll(prefill.fields) } }
    var certify by rememberSaveable { mutableStateOf(false) }
    var estate by rememberSaveable { mutableStateOf(prefill.fields["classification"] == "trust_estate") }
    val pad = rememberSignatureState()
    val fields = specs(prefill.kind)
    val missing = fields.filter { !it.optional && !it.readOnly && values[it.key].isNullOrBlank() }
    val ssnOk = prefill.kind != "w9" || values["ssn"].orEmpty().filter(Char::isDigit).length == 9

    Column(modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text(prefill.title, style = MaterialTheme.typography.headlineSmall)
        Text(if (prefill.kind == "w9") "We fill in the official IRS form for you. Check each line, then sign."
            else "A sworn statement your attorney files with the claim. Check each line, then sign.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(12.dp))
        if (prefill.kind == "w9") {
            SectionLabel("3a. Tax classification")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(!estate, { estate = false }, label = { Text("Individual") })
                FilterChip(estate, { estate = true }, label = { Text("Estate of someone who died") })
            }
        }
        fields.forEach { f ->
            OutlinedTextField(
                value = values[f.key].orEmpty(),
                onValueChange = { v -> values[f.key] = if (f.key == "ssn") v.filter { it.isDigit() || it == '-' }.take(11) else v },
                label = { Text(f.label + if (f.optional) " (optional)" else "") },
                supportingText = if (f.help.isNotBlank()) ({ Text(f.help) }) else null,
                readOnly = f.readOnly, enabled = !f.readOnly, singleLine = !f.multiline, minLines = if (f.multiline) 2 else 1,
                visualTransformation = if (f.secret) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
                keyboardOptions = if (f.secret) KeyboardOptions(keyboardType = KeyboardType.NumberPassword) else KeyboardOptions.Default,
                modifier = Modifier.fillMaxWidth().padding(top = 6.dp).testTag("field_${f.key}"),
            )
        }
        SectionLabel("Certification")
        Row(verticalAlignment = Alignment.Top) {
            Checkbox(certify, { certify = it }, modifier = Modifier.testTag("certify"))
            Text(prefill.certification, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 12.dp))
        }
        SectionLabel("Draw your signature")
        SignaturePad(pad)
        TextButton(onClick = { pad.clear() }) { Text("Clear") }
        TwoFactorPanel(verify, sent, form.busy, onSend, onConfirm)
        form.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp).testTag("formError")) }
        Spacer(Modifier.height(12.dp))
        val ready = certify && !pad.isEmpty && missing.isEmpty() && ssnOk && verify?.readyToSign == true
        Button(
            onClick = {
                val out = values.toMap() + ("classification" to if (estate) "trust_estate" else "individual")
                onSign(out, pad.toPng())
            },
            enabled = ready && !form.busy, modifier = Modifier.fillMaxWidth().height(54.dp).testTag("signForm"),
        ) {
            if (form.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            else Text("Sign ${if (prefill.kind == "w9") "W-9" else "affidavit"}", fontWeight = FontWeight.Bold)
        }
        if (!ready) {
            val todo = buildList {
                if (missing.isNotEmpty()) add("fill in ${missing.joinToString { it.label.substringAfter(". ") }}")
                if (!ssnOk) add("enter all 9 digits of your SSN")
                if (!certify) add("tick the certification")
                if (pad.isEmpty) add("draw your signature")
                if (verify?.readyToSign != true) add("confirm both codes")
            }
            Text("To sign: " + todo.joinToString(", "), style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 6.dp))
        }
        Text("Your signature, the time (in your time zone and UTC), your IP address, device and the two confirmed codes " +
            "are recorded with a fingerprint of the signed PDF.", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp))
    }
}

/** Every page of a PDF, as images (Android's built-in renderer). */
@Composable
fun PdfPages(bytes: ByteArray, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val pages by produceState<List<Bitmap>?>(null, bytes) {
        value = withContext(Dispatchers.IO) {
            runCatching {
                val file = File.createTempFile("doc", ".pdf", context.cacheDir).apply { writeBytes(bytes) }
                ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { fd ->
                    PdfRenderer(fd).use { r ->
                        (0 until r.pageCount).map { i ->
                            r.openPage(i).use { p ->
                                val bmp = Bitmap.createBitmap(p.width * 2, p.height * 2, Bitmap.Config.ARGB_8888)
                                bmp.eraseColor(android.graphics.Color.WHITE)
                                p.render(bmp, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                                bmp
                            }
                        }
                    }
                }.also { file.delete() }
            }.getOrDefault(emptyList())
        }
    }
    Column(modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        when {
            pages == null -> CircularProgressIndicator()
            pages!!.isEmpty() -> Text("The PDF couldn’t be shown here.")
            else -> pages!!.forEach { bmp ->
                Image(bmp.asImageBitmap(), null, contentScale = ContentScale.FillWidth,
                    modifier = Modifier.fillMaxWidth().background(Color.White).testTag("pdfPage"))
            }
        }
    }
}

/** Documents you've signed in Surpay, each with its fingerprint. */
@Composable
fun SignedDocumentsScreen(docs: List<SignedDoc>?, opened: Pair<String, ByteArray>?, onOpen: (SignedDoc) -> Unit,
                          modifier: Modifier = Modifier) {
    LazyColumn(modifier.fillMaxSize().testTag("signedDocs"), contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Text("Every document you sign is kept exactly as signed, under a fingerprint you can quote if it’s ever " +
                "needed. Any change to the file would change the fingerprint.", style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (docs == null) item { CircularProgressIndicator() }
        else if (docs.isEmpty()) item { Text("Nothing signed yet.") }
        else items(docs, key = { it.docId }) { d ->
            SectionCard(onClick = { onOpen(d) }, modifier = Modifier.testTag("doc_${d.docId}")) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconCircle(Icons.Outlined.Description)
                    Column(Modifier.weight(1f).padding(start = 12.dp)) {
                        Text(d.title, fontWeight = FontWeight.Bold)
                        Text("Signed ${d.signedAtDisplay}", style = MaterialTheme.typography.bodySmall)
                        Text("Fingerprint ${d.docId}" + if (d.twoFactor) " · email and phone confirmed" else "",
                            style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                if (opened?.first == d.docId) {
                    Spacer(Modifier.height(10.dp))
                    PdfPages(opened.second)
                }
            }
        }
    }
}

/** Your account's audit trail: what happened, when, and from which device. */
@Composable
fun ActivityScreen(entries: List<ActivityEntry>?, onRefresh: () -> Unit, modifier: Modifier = Modifier) {
    LaunchedEffect(Unit) { onRefresh() }
    LazyColumn(modifier.fillMaxSize().testTag("activity"), contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Text("Everything recorded about your account in our tamper-proof activity log. Each entry is chained to the " +
                "one before, so none can be changed or removed unnoticed.", style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (entries == null) item { CircularProgressIndicator() }
        else items(entries, key = { it.id }) { e ->
            Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.Top) {
                Box(Modifier.padding(top = 6.dp).size(10.dp).background(
                    if (e.mine) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.tertiary, RoundedCornerShape(5.dp)))
                Column(Modifier.padding(start = 12.dp)) {
                    Text(e.label, fontWeight = FontWeight.SemiBold)
                    Text(prettyDate(e.at) + " · " + listOf(e.deviceInfo, e.ip).filter { it.isNotBlank() }.joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("#${e.hash.take(10)}", style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace,
                        color = MaterialTheme.colorScheme.outline)
                }
            }
        }
        item { OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Outlined.History, null); Text("  Refresh") } }
    }
}
