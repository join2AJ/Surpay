package com.surpay.app.ui.screens

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.HelpOutline
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.InputChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.surpay.app.data.AttorneyCase
import com.surpay.app.data.AttorneyProfile
import com.surpay.app.data.AttorneyUpdate
import com.surpay.app.data.DocumentRequest
import com.surpay.app.ui.FormState
import com.surpay.app.ui.rememberPhotoSource

fun requestedFileKey(caseId: Int, r: DocumentRequest) = "$caseId/r${r.id}/${r.uploadedAt}"

/** Same list as backend/surpay/documents.py. */
val DOCUMENT_KINDS = listOf(
    "w9" to "IRS Form W-9", "deed" to "Deed to the property", "tax_bill" to "Property tax bill",
    "utility_bill" to "Utility bill", "bank_statement" to "Bank statement", "death_certificate" to "Death certificate",
    "probate" to "Probate or heirship documents", "notarized_affidavit" to "Signed, notarized affidavit",
    "photo_id" to "A clearer photo ID", "other" to "Other document",
)

@Composable
private fun StatusPill(status: String) {
    val (text, bg, fg) = when (status) {
        "accepted" -> Triple("Accepted", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer)
        "uploaded" -> Triple("Sent, being checked", MaterialTheme.colorScheme.secondaryContainer, MaterialTheme.colorScheme.onSurface)
        "rejected" -> Triple("Please upload again", MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer)
        else -> Triple("Needed", MaterialTheme.colorScheme.tertiaryContainer, MaterialTheme.colorScheme.onTertiaryContainer)
    }
    Pill(text, bg, fg)
}

/** Client side: what the attorney asked for, with a camera/gallery upload for each. */
@Composable
fun ClaimDocumentsCard(requests: List<DocumentRequest>, busy: Boolean, onUpload: (Int, ByteArray) -> Unit) {
    if (requests.isEmpty()) return
    val photos = rememberPhotoSource()
    SectionCard(modifier = Modifier.testTag("claimDocuments")) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconCircle(Icons.Outlined.Description)
            Column(Modifier.padding(start = 12.dp)) {
                Text("Documents your attorney needs", fontWeight = FontWeight.Bold)
                val open = requests.count { it.status in setOf("requested", "rejected") }
                Text(if (open == 0) "All sent. Thank you!" else "$open to send",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        requests.forEach { r ->
            Column(Modifier.padding(top = 14.dp).testTag("docRequest${r.id}")) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(r.label, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                    StatusPill(r.status)
                }
                Text(r.note.ifBlank { r.hint }, style = MaterialTheme.typography.bodySmall)
                if (r.note.isNotBlank()) Text(r.hint, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (r.status == "rejected" && r.reviewNote.isNotBlank()) {
                    Text("Your attorney: ${r.reviewNote}", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
                if (r.status in setOf("requested", "rejected")) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
                        Button(onClick = { photos.request(true) { b -> if (b != null) onUpload(r.id, b) } }, enabled = !busy,
                            modifier = Modifier.testTag("docCamera${r.id}")) { Text("Take photo") }
                        OutlinedButton(onClick = { photos.request(false) { b -> if (b != null) onUpload(r.id, b) } },
                            enabled = !busy) { Text("Gallery") }
                    }
                }
            }
        }
    }
}

/** Attorney side: ask for a document, see what came back, accept it or ask again. */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun CaseDocumentsSection(
    case: AttorneyCase,
    form: FormState,
    images: Map<String, ByteArray>,
    onLoad: (DocumentRequest) -> Unit,
    onRequest: (kind: String, note: String) -> Unit,
    onReview: (requestId: Int, accept: Boolean, note: String) -> Unit,
) {
    SectionLabel("Documents from your client")
    if (case.documentRequests.isEmpty()) {
        Text("Ask for anything your county needs (W-9, deed, affidavit...). Your client gets a notification and uploads a photo.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    case.documentRequests.forEach { r ->
        SectionCard(modifier = Modifier.padding(bottom = 8.dp).testTag("caseDoc${r.id}")) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(r.label, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                StatusPill(r.status)
            }
            if (r.note.isNotBlank()) Text("You asked: ${r.note}", style = MaterialTheme.typography.bodySmall)
            if (r.hasFile) {
                LaunchedEffect(r.uploadedAt) { onLoad(r) }
                val bytes = images[requestedFileKey(case.id, r)]
                val bmp = remember(bytes) { bytes?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() } }
                if (bmp != null) Image(bmp, r.label, contentScale = ContentScale.Fit,
                    modifier = Modifier.fillMaxWidth().heightIn(max = 260.dp).padding(top = 8.dp))
            }
            if (r.status == "uploaded") {
                var note by rememberSaveable(r.id) { mutableStateOf("") }
                OutlinedTextField(note, { note = it.take(500) }, label = { Text("Note if asking again (optional)") },
                    modifier = Modifier.fillMaxWidth().padding(top = 6.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { onReview(r.id, true, "") }, enabled = !form.busy,
                        modifier = Modifier.testTag("acceptDoc${r.id}")) { Text("Accept") }
                    OutlinedButton(onClick = { onReview(r.id, false, note) }, enabled = !form.busy) { Text("Ask again") }
                }
            }
        }
    }
    var kind by rememberSaveable { mutableStateOf("w9") }
    var note by rememberSaveable { mutableStateOf("") }
    var open by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }) {
        OutlinedTextField(
            value = DOCUMENT_KINDS.first { it.first == kind }.second, onValueChange = {}, readOnly = true,
            label = { Text("Request a document") }, trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(open) },
            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth().testTag("docKind"),
        )
        ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            DOCUMENT_KINDS.forEach { (k, label) -> DropdownMenuItem(text = { Text(label) }, onClick = { kind = k; open = false }) }
        }
    }
    OutlinedTextField(note, { note = it.take(500) }, label = { Text("Instructions for your client (optional)") },
        modifier = Modifier.fillMaxWidth().testTag("docNote"))
    OutlinedButton(onClick = { onRequest(kind, note); note = "" }, enabled = !form.busy,
        modifier = Modifier.fillMaxWidth().padding(top = 6.dp).testTag("requestDoc")) { Text("Send request to client") }
}

/** Attorney: pause new offers, update contact details and counties. */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun AttorneySettingsScreen(
    profile: AttorneyProfile,
    form: FormState,
    counties: List<String>,
    onLoadCounties: () -> Unit,
    onSave: (AttorneyUpdate) -> Unit,
    onHelp: () -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    LaunchedEffect(Unit) { onLoadCounties() }
    var firm by rememberSaveable { mutableStateOf(profile.firm) }
    var phone by rememberSaveable { mutableStateOf(profile.phone) }
    var office by rememberSaveable { mutableStateOf(profile.officeAddress) }
    val chosen = remember { mutableStateListOf<String>().apply { addAll(profile.counties) } }
    var filter by rememberSaveable { mutableStateOf("") }
    Column(modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp)) {
        HeroCard {
            Text(profile.fullName, style = MaterialTheme.typography.titleLarge)
            Text("${profile.barState} Bar #${profile.barNumber} · ${profile.status}", style = MaterialTheme.typography.bodyMedium)
        }
        SectionLabel("Availability")
        SectionCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(if (profile.available) "Taking new cases" else "New cases paused", fontWeight = FontWeight.SemiBold)
                    Text("Pause while you're away or full. Your current cases continue.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(checked = profile.available, onCheckedChange = { onSave(AttorneyUpdate(available = it)) },
                    enabled = !form.busy, modifier = Modifier.testTag("availability"))
            }
        }
        SectionLabel("Contact and office")
        OutlinedTextField(firm, { firm = it }, label = { Text("Firm") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(phone, { phone = it }, label = { Text("Office phone (for Surpay only)") }, singleLine = true,
            modifier = Modifier.fillMaxWidth())
        OutlinedTextField(office, { office = it }, label = { Text("Office address") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        SectionLabel("Counties you serve (${chosen.size})")
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            chosen.forEach { c ->
                InputChip(selected = true, onClick = { if (chosen.size > 1) chosen.remove(c) }, label = { Text(c) },
                    trailingIcon = { Icon(Icons.Filled.Close, "Remove", Modifier.size(16.dp)) })
            }
        }
        OutlinedTextField(filter, { filter = it }, label = { Text("Add a county in ${profile.barState}") }, singleLine = true,
            modifier = Modifier.fillMaxWidth())
        if (filter.isNotBlank()) {
            counties.filter { it.contains(filter.trim(), ignoreCase = true) && it !in chosen }.take(6).forEach { c ->
                Text("+ $c", Modifier.fillMaxWidth().clickable { chosen.add(c); filter = "" }.padding(vertical = 8.dp),
                    color = MaterialTheme.colorScheme.primary)
            }
        }
        form.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp)) }
        Button(
            onClick = { onSave(AttorneyUpdate(firm = firm.trim(), phone = phone.trim(), officeAddress = office.trim(), counties = chosen.toList())) },
            enabled = !form.busy && phone.filter { it.isDigit() }.length >= 7 && office.trim().length >= 5,
            modifier = Modifier.fillMaxWidth().height(52.dp).padding(top = 8.dp).testTag("saveAttorney"),
        ) { if (form.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp) else Text("Save changes") }
        Text("To change your bar number or state, contact Surpay so we can verify the new license.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 8.dp))
        Spacer(Modifier.height(8.dp))
        NavRow(Icons.Outlined.HelpOutline, "Help and FAQ", "How cases, payment and messages work", onClick = onHelp)
        TextButton(onClick = onLogout, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Sign out") }
    }
}

/** Ready-made openings for the attorney (they can edit before sending). */
val QUICK_REPLIES = listOf(
    "Hello, I'm your attorney for this claim. I've reviewed your case and will keep you updated here.",
    "I've requested a document in the app. Please upload it when you can.",
    "Your claim has been filed. The county or court usually takes a few weeks to respond.",
    "Do you have any questions about the process so far?",
)

@Composable
fun QuickReplies(onPick: (String) -> Unit) {
    androidx.compose.foundation.lazy.LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp),
        modifier = Modifier.padding(bottom = 6.dp).testTag("quickReplies")) {
        items(QUICK_REPLIES) { r -> AssistChip(onClick = { onPick(r) }, label = { Text(r.take(28) + "…") }) }
    }
}

private val CLAIMANT_FAQ = listOf(
    "Is this money really mine?" to "When a home is sold at a tax or foreclosure auction for more than was owed, the extra belongs to the former owner (or their heirs). The U.S. Supreme Court confirmed this in Tyler v. Hennepin County (2023).",
    "Do I have to use Surpay?" to "No. You can always claim the money yourself, for free, from the county or court. Surpay connects you with a licensed attorney and handles the paperwork if you'd rather not.",
    "What does it cost?" to "Nothing upfront. If money is recovered, the fee shown in your agreement is taken from what is paid out. If nothing is recovered, you owe nothing.",
    "How long does it take?" to "Usually 2 to 6 months from filing, depending on the county and court. Your claim's timeline shows estimated dates for each step.",
    "Why do you need my ID and a selfie?" to "So only the real owner can see and claim the money. Nobody can use Surpay to look someone else up.",
    "How do I reach my attorney?" to "Once your attorney accepts the case, use Messages on your claim. Your attorney writes first. Contact details aren't shared, so everything stays in the app.",
    "How will I be paid?" to "The county or court issues the payment, usually by check, once the claim is approved. Your attorney tells you exactly how in Messages.",
    "Can I change my attorney?" to "Yes, any time before your claim is filed: open your claim and tap “Ask for a different attorney”.",
    "How do I cancel?" to "Write to support within 3 business days of signing to cancel at no cost (see your agreement). After that, contact support before the claim is filed.",
    "Is my data safe?" to "Your documents and personal details are encrypted, every action is logged, and you can download or delete your data under Privacy and data.",
)

private val ATTORNEY_FAQ = listOf(
    "How are cases assigned?" to "Verified, signed cases in your counties are offered to the approved attorney with the fewest open cases. Offers not answered within 3 days go to the next attorney.",
    "How am I paid?" to "The per-case fee shown in your terms, due when the case closes (money released or denied). Surpay records the payment on the case.",
    "Who is my client?" to "The claimant. You exercise independent judgment; Surpay doesn't direct your legal work (see your partner terms).",
    "Can I hand a case back?" to "Yes, until you file it. The client is told and the case goes to another attorney.",
    "What do I need to file?" to "Each case shows a step-by-step filing guide for its state and a printable claim packet. Use document requests for anything else.",
)

@Composable
fun HelpScreen(attorney: Boolean, supportEmail: String = "support@surpay.app", modifier: Modifier = Modifier) {
    var open by rememberSaveable { mutableStateOf<Int?>(null) }
    val faq = if (attorney) ATTORNEY_FAQ else CLAIMANT_FAQ
    LazyColumn(modifier.fillMaxSize().padding(horizontal = 16.dp).testTag("help"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { Spacer(Modifier.height(8.dp)); Text("Help and FAQ", style = MaterialTheme.typography.headlineSmall) }
        items(faq.size) { i ->
            val (q, a) = faq[i]
            SectionCard(onClick = { open = if (open == i) null else i }) {
                Text(q, fontWeight = FontWeight.SemiBold)
                if (open == i) Text(a, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 6.dp))
            }
        }
        item {
            NoteBox("Still stuck? Write to $supportEmail and include your claim reference (for example SP-000123).")
            Spacer(Modifier.height(16.dp))
        }
    }
}
