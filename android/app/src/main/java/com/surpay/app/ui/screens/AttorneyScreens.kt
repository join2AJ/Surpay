package com.surpay.app.ui.screens

import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Chat
import androidx.compose.material.icons.outlined.Badge
import androidx.compose.material.icons.outlined.Checklist
import androidx.compose.material.icons.outlined.Print
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material.icons.outlined.HourglassTop
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.surpay.app.data.AttorneyApplication
import com.surpay.app.data.AttorneyCase
import com.surpay.app.data.AttorneyProfile
import com.surpay.app.data.AttorneyTerms
import com.surpay.app.ui.FormState
import com.surpay.app.ui.US_STATES
import com.surpay.app.ui.claimStatusLabel
import com.surpay.app.ui.dollars
import com.surpay.app.ui.prettyDate
import com.surpay.app.ui.rememberPhotoSource
import com.surpay.app.ui.saleTypeLabel

// --- Application ------------------------------------------------------------------------------

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AttorneyApplyScreen(
    name: String,
    form: FormState,
    counties: Map<String, List<String>>,
    terms: AttorneyTerms?,
    rejectedNote: String?,
    onStateChosen: (String) -> Unit,
    onSubmit: (AttorneyApplication) -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val photos = rememberPhotoSource()
    var fullName by rememberSaveable { mutableStateOf(name) }
    var barState by rememberSaveable { mutableStateOf("") }
    var barNumber by rememberSaveable { mutableStateOf("") }
    var firm by rememberSaveable { mutableStateOf("") }
    var phone by rememberSaveable { mutableStateOf("") }
    var office by rememberSaveable { mutableStateOf("") }
    var accept by rememberSaveable { mutableStateOf(false) }
    var filter by rememberSaveable { mutableStateOf("") }
    val chosen = remember { mutableStateListOf<String>() }
    var barCard by remember { mutableStateOf<ByteArray?>(null) }
    val list = counties[barState].orEmpty()

    val ready = fullName.trim().length >= 3 && barState.length == 2 && barNumber.trim().length >= 2 &&
        phone.filter { it.isDigit() }.length >= 10 && office.trim().length >= 5 && chosen.isNotEmpty() &&
        barCard != null && accept

    Column(modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text("Join the Surpay attorney network", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        Text(
            "Take surplus-funds cases for verified clients in the counties you serve. Clients are ID-verified " +
                "and have signed before a case reaches you. You’re paid per case.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        rejectedNote?.let {
            Spacer(Modifier.height(12.dp))
            Surface(color = MaterialTheme.colorScheme.errorContainer, shape = MaterialTheme.shapes.medium, modifier = Modifier.fillMaxWidth()) {
                Text("Your last application wasn’t approved: $it", Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onErrorContainer)
            }
        }

        Heading("Your license")
        Input(fullName, { fullName = it }, "Full name (as on your bar record)", "attyName")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            var open by remember { mutableStateOf(false) }
            ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }, modifier = Modifier.weight(1f)) {
                OutlinedTextField(
                    value = barState, onValueChange = {}, readOnly = true, label = { Text("Licensed in") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(open) },
                    modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth().testTag("barState"),
                )
                ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                    US_STATES.forEach { st ->
                        DropdownMenuItem(text = { Text(st) }, onClick = {
                            if (st != barState) chosen.clear()
                            barState = st
                            onStateChosen(st)
                            open = false
                        })
                    }
                }
            }
            OutlinedTextField(
                value = barNumber, onValueChange = { barNumber = it.take(64) }, label = { Text("Bar number") },
                singleLine = true, modifier = Modifier.weight(1f).testTag("barNumber"),
            )
        }
        Input(firm, { firm = it }, "Firm (optional)", "firm")
        OutlinedTextField(
            value = phone, onValueChange = { phone = it.take(20) }, label = { Text("Office phone") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp).testTag("attyPhone"),
        )
        Input(office, { office = it }, "Office address", "office")

        Heading("Counties you’ll take cases in")
        when {
            barState.isEmpty() -> Text("Choose the state you’re licensed in first.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            list.isEmpty() -> CircularProgressIndicator(Modifier.size(24.dp))
            else -> {
                Text("${chosen.size} selected", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.testTag("countyCount"))
                OutlinedTextField(
                    value = filter, onValueChange = { filter = it }, singleLine = true, label = { Text("Search counties") },
                    modifier = Modifier.fillMaxWidth().testTag("countyFilter"),
                )
                OutlinedCard(Modifier.fillMaxWidth().heightIn(max = 280.dp).padding(top = 6.dp)) {
                    LazyColumn {
                        items(list.filter { it.contains(filter.trim(), ignoreCase = true) }) { c ->
                            Row(
                                Modifier.fillMaxWidth().clickable { if (c in chosen) chosen.remove(c) else chosen.add(c) }
                                    .padding(horizontal = 8.dp).testTag("county_$c"),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Checkbox(checked = c in chosen, onCheckedChange = { if (it) chosen.add(c) else chosen.remove(c) })
                                Text(c)
                            }
                        }
                    }
                }
            }
        }

        Heading("Bar card or license")
        Text("A photo of your bar card or certificate. We also check the state bar’s directory.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
            val bmp = remember(barCard) { barCard?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() } }
            if (bmp != null) {
                Image(bmp, "Bar card", contentScale = ContentScale.Crop, modifier = Modifier.size(64.dp))
                Spacer(Modifier.size(12.dp))
            }
            Button(onClick = { photos.request(true) { b -> if (b != null) barCard = b } }, modifier = Modifier.testTag("barCardCamera")) {
                Text(if (barCard == null) "Take photo" else "Retake")
            }
            Spacer(Modifier.size(8.dp))
            OutlinedButton(onClick = { photos.request(false) { b -> if (b != null) barCard = b } }) { Text("Gallery") }
        }

        Heading("Partner terms")
        if (terms != null) {
            Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium, modifier = Modifier.fillMaxWidth()) {
                Text("You’re paid ${dollars(terms.feePerCaseCents)} per case in $barState",
                    Modifier.padding(12.dp).testTag("feePerCase"), fontWeight = FontWeight.Bold)
            }
            OutlinedCard(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Text(terms.text, Modifier.padding(12.dp), style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Serif)
            }
        } else {
            Text("Choose your state to see the terms.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Row(verticalAlignment = Alignment.Top, modifier = Modifier.padding(top = 8.dp)) {
            Checkbox(checked = accept, onCheckedChange = { accept = it }, enabled = terms != null, modifier = Modifier.testTag("acceptTerms"))
            Text("I hold an active license in good standing and accept the partner terms.",
                style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 12.dp))
        }
        form.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp)) }
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = {
                onSubmit(AttorneyApplication(
                    fullName = fullName.trim(), barState = barState, barNumber = barNumber.trim(), firm = firm.trim(),
                    phone = phone.trim(), officeAddress = office.trim(), counties = chosen.toList(),
                    barCardB64 = Base64.encodeToString(barCard!!, Base64.NO_WRAP), acceptTerms = accept,
                ))
            },
            enabled = ready && !form.busy,
            modifier = Modifier.fillMaxWidth().height(52.dp).testTag("submitApplication"),
        ) {
            if (form.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            else Text("Submit for verification", fontWeight = FontWeight.Bold)
        }
        TextButton(onClick = onLogout, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Sign out") }
    }
}

@Composable
fun AttorneyPendingScreen(profile: AttorneyProfile, onRefresh: () -> Unit, onLogout: () -> Unit) {
    LaunchedEffect(Unit) {
        while (true) {
            onRefresh()
            kotlinx.coroutines.delay(30_000)
        }
    }
    Column(Modifier.fillMaxSize().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center) {
        Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.size(72.dp)) {
            Box(contentAlignment = Alignment.Center) {
                Icon(Icons.Outlined.HourglassTop, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(36.dp))
            }
        }
        Spacer(Modifier.height(16.dp))
        Text("We’re verifying your license", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center, modifier = Modifier.testTag("attyPending"))
        Spacer(Modifier.height(8.dp))
        Text(
            "${profile.barState} Bar #${profile.barNumber} · ${profile.counties.size} counties. We check the state bar’s " +
                "directory, usually within 1–2 business days. Cases in your counties appear here as soon as you’re approved.",
            textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(20.dp))
        Button(onClick = onRefresh) { Text("Check status now") }
        TextButton(onClick = onLogout) { Text("Sign out") }
    }
}

// --- Cases ------------------------------------------------------------------------------------

@Composable
fun CasesScreen(profile: AttorneyProfile, cases: List<AttorneyCase>?, onOpen: (AttorneyCase) -> Unit, onRefresh: () -> Unit,
                modifier: Modifier = Modifier) {
    if (cases == null) {
        Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        return
    }
    val offered = cases.filter { it.assignmentStatus == "offered" }
    val active = cases.filter { it.assignmentStatus == "accepted" && it.status !in CLOSED }
    val closed = cases.filter { it.assignmentStatus == "accepted" && it.status in CLOSED }
    val earned = closed.sumOf { it.feeCents }
    LazyColumn(modifier.fillMaxSize().testTag("cases"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            HeroCard {
                Text("${profile.fullName} · ${profile.barState} Bar #${profile.barNumber}", style = MaterialTheme.typography.labelLarge)
                Text("${active.size} active · ${offered.size} new", style = MaterialTheme.typography.headlineSmall)
                Text("${dollars(profile.feePerCaseCents)} per case · ${dollars(earned)} from closed cases",
                    style = MaterialTheme.typography.bodyMedium)
            }
        }
        if (cases.isEmpty()) {
            item {
                Text("No cases yet. When a verified client in ${profile.counties.size} of your counties signs, their case comes " +
                    "to you here.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        section("New cases: accept or decline", offered, onOpen)
        section("Active", active, onOpen)
        section("Closed", closed, onOpen)
        item { OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) { Text("Refresh") } }
    }
}

private val CLOSED = setOf("paid", "denied", "withdrawn")

private fun androidx.compose.foundation.lazy.LazyListScope.section(title: String, list: List<AttorneyCase>, onOpen: (AttorneyCase) -> Unit) {
    if (list.isEmpty()) return
    item { Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp)) }
    items(list, key = { it.id }) { c -> CaseCard(c, onClick = { onOpen(c) }) }
}

@Composable
private fun CaseCard(c: AttorneyCase, onClick: () -> Unit) {
    SectionCard(onClick = onClick, modifier = Modifier.testTag("case${c.id}")) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(dollars(c.amountCents), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                if (c.assignmentStatus == "offered") {
                    Surface(color = Color(0xFFFFF1D6), contentColor = Color(0xFF6B4A00), shape = MaterialTheme.shapes.small) {
                        Text("New", Modifier.padding(horizontal = 8.dp, vertical = 2.dp), style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
            Text("${c.county} County, ${c.state} · ${c.reference}")
            if (c.unreadMessages > 0) {
                Text("${c.unreadMessages} new message(s)", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
            }
            Text(
                if (c.assignmentStatus == "offered") "Fee ${dollars(c.feeCents)} · respond within 2 business days"
                else "${claimStatusLabel(c.status)} · fee ${dollars(c.feeCents)}${payoutLabel(c.payoutStatus)}",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private fun payoutLabel(p: String) = when (p) {
    "due" -> " (payment due)"
    "paid" -> " (paid)"
    else -> ""
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
fun CaseDetailScreen(
    case: AttorneyCase,
    form: FormState,
    documents: Map<String, ByteArray>,
    onAccept: () -> Unit,
    onDecline: (String) -> Unit,
    onStatus: (String, String) -> Unit,
    onLoadDocument: (String) -> Unit,
    onPacket: () -> Unit = {},
    onMessages: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val uri = LocalUriHandler.current
    var dialog by rememberSaveable { mutableStateOf<String?>(null) } // status to confirm, or "decline"
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text("${case.county} County, ${case.state} · ${case.reference}", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(dollars(case.amountCents), style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.ExtraBold)
        Text("${saleTypeLabel(case.saleType)} on ${prettyDate(case.saleDate)} · your fee ${dollars(case.feeCents)}${payoutLabel(case.payoutStatus)}")
        if (case.sourceUrl.isNotBlank()) TextButton(onClick = { uri.openUri(case.sourceUrl) }) { Text("County list") }
        form.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Spacer(Modifier.height(8.dp))

        if (case.assignmentStatus == "offered") {
            Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.medium, modifier = Modifier.fillMaxWidth()) {
                Text("The client’s identity is verified and the agreement is signed. Their details and documents appear once " +
                    "you accept.", Modifier.padding(12.dp), style = MaterialTheme.typography.bodyMedium)
            }
            if (case.otherClaimants > 0) {
                Spacer(Modifier.height(8.dp))
                NoteBox("${case.otherClaimants} other person(s) have also claimed this record (a co-owner, another heir, " +
                    "or a disputed claim). Consider this in your conflict check.")
            }
            Spacer(Modifier.height(12.dp))
            var conflictChecked by rememberSaveable { mutableStateOf(false) }
            Row(verticalAlignment = Alignment.Top) {
                Checkbox(conflictChecked, { conflictChecked = it }, modifier = Modifier.testTag("conflictChecked"))
                Text("I’ve run a conflict check and have no conflict with this client, the former owner, other " +
                    "claimants or lienholders (Rule 1.7).", style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 12.dp))
            }
            Button(onClick = onAccept, enabled = conflictChecked && !form.busy,
                modifier = Modifier.fillMaxWidth().height(50.dp).testTag("acceptCase")) {
                Text("Accept case", fontWeight = FontWeight.Bold)
            }
            OutlinedButton(onClick = { dialog = "decline" }, enabled = !form.busy, modifier = Modifier.fillMaxWidth()) { Text("Decline") }
            dialog?.let { a -> ConfirmPanel(a, form.busy, onConfirm = { note -> onDecline(note); dialog = null }, onCancel = { dialog = null }) }
            Spacer(Modifier.height(12.dp))
            FilingGuideCard(case)
            Spacer(Modifier.height(12.dp))
            LegalCard(case.legal)
        } else {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = onMessages, enabled = case.chatOpen, modifier = Modifier.weight(1f).testTag("caseChat")) {
                    BadgedBox(badge = { if (case.unreadMessages > 0) Badge { Text("${case.unreadMessages}") } }) {
                        Icon(Icons.AutoMirrored.Outlined.Chat, null)
                    }
                    Text("  Message client")
                }
                OutlinedButton(onClick = onPacket, enabled = !form.busy, modifier = Modifier.weight(1f).testTag("casePacket")) {
                    Icon(Icons.Outlined.Print, null)
                    Text("  Claim packet")
                }
            }
            Text("Contact details aren’t shared: keep all client communication in the app.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            case.claimant?.let { cl ->
                Heading("Client")
                SectionCard(modifier = Modifier.testTag("client")) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(cl.name, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                        case.onBehalfOf?.let { Text("Claiming for $it", color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.SemiBold) }
                        Detail2("Date of birth", prettyDate(cl.dateOfBirth))
                        Detail2("Lives at", cl.currentAddress)
                        Detail2("SSN (last 4)", cl.ssnLast4)
                        if (cl.otherNames.isNotEmpty()) Detail2("Other names", cl.otherNames.joinToString(", "))
                        Detail2("Homes they owned", cl.homes.joinToString("\n"))
                    }
                }
                Heading("Documents")
                val kinds = listOfNotNull("id_front", "id_back".takeIf { cl.hasIdBack }, "selfie") +
                    cl.relative?.documents.orEmpty() + listOfNotNull("signature".takeIf { case.agreement?.hasSignatureImage == true })
                androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    kinds.forEach { kind ->
                        LaunchedEffect(kind) { onLoadDocument(kind) }
                        val bytes = documents["${case.id}/$kind"]
                        val bmp = remember(bytes) { bytes?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() } }
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Box(Modifier.size(96.dp), contentAlignment = Alignment.Center) {
                                if (bmp != null) Image(bmp, kind, contentScale = ContentScale.Crop, modifier = Modifier.size(96.dp))
                                else Icon(Icons.Outlined.Badge, null)
                            }
                            Text(kind.replace("_", " "), style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
            case.record?.let { r ->
                Heading("County record")
                Detail2("Listed owner", r.ownerName)
                if (r.ownerAddress.isNotBlank()) Detail2("Address on record", r.ownerAddress)
            }
            case.agreement?.let { a ->
                Heading("Signed agreement")
                Text("Signed by ${a.signatureName} on ${prettyDate(a.signedAt)}", style = MaterialTheme.typography.bodyMedium)
                if (a.documentSha256.isNotBlank()) {
                    Text("Fingerprint ${a.documentSha256.take(16)}… · ${a.device.ifBlank { "device recorded" }}",
                        style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                var showText by remember { mutableStateOf(false) }
                TextButton(onClick = { showText = !showText }) { Text(if (showText) "Hide agreement" else "Read agreement") }
                if (showText) Text(a.text, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Serif)
            }
            Spacer(Modifier.height(12.dp))
            FilingGuideCard(case)
            Spacer(Modifier.height(12.dp))
            LegalCard(case.legal, familyBasis = case.claimant?.relative?.basis)

            Heading("Update the client")
            Text("Each update appears on your client’s timeline.", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            val next = when (case.status) {
                "identity_verified", "attorney_assigned" -> listOf("filed")
                "filed" -> listOf("hearing_pending", "approved", "denied")
                "hearing_pending" -> listOf("approved", "denied")
                "approved" -> listOf("paid", "denied")
                else -> emptyList()
            }
            if (next.isEmpty()) {
                Text("Case closed: ${claimStatusLabel(case.status)}", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 8.dp))
            }
            next.forEach { s ->
                val label = when (s) {
                    "filed" -> "I’ve filed the claim"
                    "hearing_pending" -> "Waiting for the county or court (hearing set / under review)"
                    "approved" -> "Hearing held: the claim was approved"
                    "paid" -> "Money released to the client"
                    else -> "Claim was denied"
                }
                OutlinedButton(onClick = { dialog = s }, enabled = !form.busy, modifier = Modifier.fillMaxWidth().testTag("status_$s")) { Text(label) }
            }
            if (case.status in setOf("identity_verified", "attorney_assigned")) {
                TextButton(onClick = { dialog = "decline" }, enabled = !form.busy) { Text("Hand this case back") }
            }
            dialog?.let { a ->
                ConfirmPanel(a, form.busy, onConfirm = { note -> if (a == "decline") onDecline(note) else onStatus(a, note); dialog = null },
                    onCancel = { dialog = null })
            }
            if (case.history.isNotEmpty()) {
                Heading("History")
                case.history.forEach { h ->
                    Text("${prettyDate(h.at)} · ${claimStatusLabel(h.status)}${if (h.note.isNotBlank()) " · ${h.note}" else ""}",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }

}

/** Where and how to file in this state, step by step, and what to print. */
@Composable
private fun FilingGuideCard(case: AttorneyCase) {
    val g = case.filingGuide
    if (g.steps.isEmpty()) return
    var open by rememberSaveable { mutableStateOf(case.assignmentStatus == "accepted") }
    SectionCard(modifier = Modifier.testTag("filingGuide"), onClick = { open = !open }) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconCircle(Icons.Outlined.Checklist)
            Column(Modifier.weight(1f).padding(start = 12.dp)) {
                Text("How to file in ${case.state}", fontWeight = FontWeight.Bold)
                Text(g.online, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
            }
        }
        if (open) {
            Text("Where: ${g.where}", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 10.dp))
            g.steps.forEachIndexed { i, step ->
                Row(Modifier.padding(top = 8.dp)) {
                    Text("${i + 1}.", fontWeight = FontWeight.Bold, modifier = Modifier.padding(end = 8.dp))
                    Text(step, style = MaterialTheme.typography.bodyMedium)
                }
            }
            if (g.print.isNotEmpty()) {
                Text("PRINT AND SIGN", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 12.dp))
                g.print.forEach { Text("☐  $it", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 4.dp)) }
                Text("The claim packet (PDF) has a cover sheet, a draft affidavit with a notary block, the signed agreement and " +
                    "the documents, ready to print.", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp))
            }
        }
    }
}

/** Inline confirm step (instead of a pop-up) with an optional note. */
@Composable
private fun ConfirmPanel(action: String, busy: Boolean, onConfirm: (String) -> Unit, onCancel: () -> Unit) {
    var note by rememberSaveable(action) { mutableStateOf("") }
    Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.medium,
        modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp).testTag("confirmPanel")) {
        Column(Modifier.padding(14.dp)) {
            Text(if (action == "decline") "Decline or hand back this case?" else "Update to “${claimStatusLabel(action)}”?",
                fontWeight = FontWeight.Bold)
            if (action != "decline") {
                Text("Your client gets a notification with this update.", style = MaterialTheme.typography.bodySmall)
            }
            OutlinedTextField(
                value = note, onValueChange = { note = it.take(500) },
                label = { Text(if (action == "decline") "Reason (optional)" else "Note for the client (e.g. court case number)") },
                modifier = Modifier.fillMaxWidth().testTag("dialogNote"),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                Button(onClick = { onConfirm(note) }, enabled = !busy, modifier = Modifier.testTag("dialogConfirm")) { Text("Confirm") }
                TextButton(onClick = onCancel) { Text("Cancel") }
            }
        }
    }
}

@Composable
private fun Heading(text: String) {
    Spacer(Modifier.height(18.dp))
    Text(text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    Spacer(Modifier.height(6.dp))
}

@Composable
private fun Input(value: String, onChange: (String) -> Unit, label: String, tag: String) {
    OutlinedTextField(value = value, onValueChange = onChange, label = { Text(label) }, singleLine = true,
        modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp).testTag(tag))
}

@Composable
private fun Detail2(label: String, value: String) {
    if (value.isBlank()) return
    Column(Modifier.padding(vertical = 2.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
