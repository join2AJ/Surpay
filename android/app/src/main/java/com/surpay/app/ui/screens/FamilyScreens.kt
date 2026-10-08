package com.surpay.app.ui.screens

import android.util.Base64
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.outlined.FamilyRestroom
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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.surpay.app.data.Address
import com.surpay.app.data.Relative
import com.surpay.app.data.RelativeRequest
import com.surpay.app.ui.FormState
import com.surpay.app.ui.prettyDate
import com.surpay.app.ui.rememberPhotoSource
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.format.ResolverStyle

private val RELATIONSHIPS = listOf("spouse", "parent", "child", "sibling", "grandparent", "grandchild", "other")

private val BASES = listOf(
    "heir" to "They have died and I’m their heir",
    "power_of_attorney" to "I hold their power of attorney",
    "guardian" to "I’m their court-appointed guardian",
)

/** Family members the person searches for, with each one's review status. */
@Composable
fun FamilyScreen(
    relatives: List<Relative>?,
    form: FormState,
    onLoad: () -> Unit,
    onAdd: () -> Unit,
    onRemove: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    LaunchedEffect(Unit) { onLoad() }
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
        HeroCard {
            Text("Claim for a family member", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(6.dp))
            Text("If a parent, spouse or other relative has died, surplus money from their home may pass to their heirs. " +
                "You can also act for someone under a power of attorney or guardianship.", style = MaterialTheme.typography.bodyMedium)
        }
        Spacer(Modifier.height(14.dp))
        NoteBox("To protect people’s privacy, we show results for a family member only after our team checks the " +
            "documents that prove your relationship and your right to act for them.")
        SectionLabel("Your family members")
        when {
            relatives == null -> CircularProgressIndicator()
            relatives.isEmpty() -> Text("None added yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> relatives.forEach { r ->
                SectionCard(modifier = Modifier.padding(bottom = 10.dp).testTag("relative${r.id}")) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconCircle(Icons.Outlined.FamilyRestroom)
                        Column(Modifier.weight(1f).padding(start = 12.dp)) {
                            Text(r.fullName, fontWeight = FontWeight.Bold)
                            Text("Your ${r.relationship} · ${BASES.firstOrNull { it.first == r.basis }?.second ?: r.basis}",
                                style = MaterialTheme.typography.bodySmall)
                            r.dateOfDeath?.let { Text("Died ${prettyDate(it)}", style = MaterialTheme.typography.bodySmall) }
                        }
                        when (r.reviewStatus) {
                            "approved" -> Pill("Verified", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer)
                            "rejected" -> Pill("Needs documents", MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer)
                            else -> Pill("In review", MaterialTheme.colorScheme.tertiaryContainer, MaterialTheme.colorScheme.onTertiaryContainer)
                        }
                    }
                    if (r.reviewStatus == "rejected" && r.reviewNote.isNotBlank()) {
                        Text(r.reviewNote, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(top = 6.dp))
                    }
                    if (r.reviewStatus == "approved") {
                        Text("Any records in their name now appear in My money, marked with their name.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 6.dp))
                    }
                    TextButton(onClick = { onRemove(r.id) }, enabled = !form.busy) { Text("Remove") }
                }
            }
        }
        form.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Spacer(Modifier.height(10.dp))
        Button(onClick = onAdd, modifier = Modifier.fillMaxWidth().height(52.dp).testTag("addRelative")) {
            Icon(Icons.Filled.Add, null)
            Spacer(Modifier.width(6.dp))
            Text("Add a family member", fontWeight = FontWeight.Bold)
        }
    }
}

private val DATE = DateTimeFormatter.ofPattern("MM/dd/uuuu").withResolverStyle(ResolverStyle.STRICT)

private fun parsePastDate(text: String): String? =
    runCatching { LocalDate.parse(text.trim(), DATE) }.getOrNull()?.takeIf { !it.isAfter(LocalDate.now()) }?.toString()

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddRelativeScreen(
    form: FormState,
    counties: Map<String, List<String>>,
    onStateChosen: (String) -> Unit,
    onSubmit: (RelativeRequest) -> Unit,
    modifier: Modifier = Modifier,
) {
    val photos = rememberPhotoSource()
    var name by rememberSaveable { mutableStateOf("") }
    var otherNames by rememberSaveable { mutableStateOf("") }
    var relationship by rememberSaveable { mutableStateOf("") }
    var basis by rememberSaveable { mutableStateOf("heir") }
    var died by rememberSaveable { mutableStateOf("") }
    var consent by rememberSaveable { mutableStateOf(false) }
    var deathCert by remember { mutableStateOf<ByteArray?>(null) }
    var proof by remember { mutableStateOf<ByteArray?>(null) }
    var authority by remember { mutableStateOf<ByteArray?>(null) }
    val homes = remember { mutableStateListOf(AddressDraft()) }
    val diedIso = parsePastDate(died)
    val filled = homes.filterNot { it.isBlank }
    val ready = name.trim().length >= 3 && relationship.isNotBlank() && proof != null && consent &&
        filled.isNotEmpty() && filled.all { it.isValid } &&
        (if (basis == "heir") diedIso != null && deathCert != null else authority != null)

    Column(modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text("Add a family member", style = MaterialTheme.typography.headlineSmall)
        Text("We’ll search for surplus in their name once we’ve checked your documents (usually 1 to 2 business days).",
            color = MaterialTheme.colorScheme.onSurfaceVariant)

        SectionLabel("Who are you searching for?")
        OutlinedTextField(name, { name = it }, label = { Text("Their full legal name") }, singleLine = true,
            modifier = Modifier.fillMaxWidth().testTag("relName"))
        OutlinedTextField(otherNames, { otherNames = it }, label = { Text("Other names they used (optional)") }, singleLine = true,
            supportingText = { Text("Maiden or previous names, separated by commas") }, modifier = Modifier.fillMaxWidth())
        var open by remember { mutableStateOf(false) }
        ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }) {
            OutlinedTextField(
                value = relationship.replaceFirstChar { it.uppercase() }, onValueChange = {}, readOnly = true,
                label = { Text("They are my…") }, trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(open) },
                modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth().testTag("relRelationship"),
            )
            ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                RELATIONSHIPS.forEach { r ->
                    DropdownMenuItem(text = { Text(r.replaceFirstChar { it.uppercase() }) }, onClick = { relationship = r; open = false })
                }
            }
        }

        SectionLabel("Your right to claim for them")
        BASES.forEach { (key, label) ->
            Row(Modifier.fillMaxWidth().selectable(selected = basis == key, onClick = { basis = key }).testTag("basis_$key"),
                verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = basis == key, onClick = { basis = key })
                Text(label)
            }
        }
        if (basis == "heir") {
            OutlinedTextField(
                value = died, onValueChange = { died = formatDob(it) }, label = { Text("Date of death (MM/DD/YYYY)") },
                singleLine = true, isError = died.length == 10 && diedIso == null,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth().testTag("relDied"),
            )
        }

        SectionLabel("Documents")
        if (basis == "heir") {
            PhotoSlot("Death certificate", "A certified copy", deathCert, "relDeath",
                onCamera = { photos.request(true) { b -> if (b != null) deathCert = b } },
                onGallery = { photos.request(false) { b -> if (b != null) deathCert = b } })
        } else {
            PhotoSlot(if (basis == "guardian") "Guardianship order" else "Power of attorney", "Signed and notarized",
                authority, "relAuthority",
                onCamera = { photos.request(true) { b -> if (b != null) authority = b } },
                onGallery = { photos.request(false) { b -> if (b != null) authority = b } })
        }
        PhotoSlot("Proof of relationship", "Birth or marriage certificate linking you", proof, "relProof",
            onCamera = { photos.request(true) { b -> if (b != null) proof = b } },
            onGallery = { photos.request(false) { b -> if (b != null) proof = b } })
        Text(
            when (basis) {
                "heir" -> "Your attorney may also need probate documents (letters of administration, the will, or an affidavit " +
                    "of heirship) and the details of any other heirs. They’ll tell you exactly what your county needs."
                "power_of_attorney" -> "Some counties don’t accept claims under a power of attorney and need the owner’s own " +
                    "signature. Your attorney will confirm."
                else -> "Your attorney may also need the owner’s photo ID."
            },
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        SectionLabel("Homes they owned (at least one)")
        homes.forEachIndexed { i, a ->
            AddressCard(draft = a, index = i, counties = counties[a.state].orEmpty(),
                onChange = { if (it.state != a.state) onStateChosen(it.state); homes[i] = it },
                onRemove = if (homes.size > 1) ({ homes.removeAt(i) }) else null)
            Spacer(Modifier.height(8.dp))
        }
        OutlinedButton(onClick = { homes.add(AddressDraft()) }) { Text("Add another home") }

        Row(verticalAlignment = Alignment.Top, modifier = Modifier.padding(top = 12.dp)) {
            Checkbox(consent, { consent = it }, modifier = Modifier.testTag("relConsent"))
            Text("I confirm these documents are genuine, that I am entitled to act for this person, and I understand " +
                "a false claim may be a crime.", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 12.dp))
        }
        form.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = {
                fun ByteArray.b64() = Base64.encodeToString(this, Base64.NO_WRAP)
                onSubmit(RelativeRequest(
                    fullName = name.trim(), otherNames = otherNames.split(',').map { it.trim() }.filter { it.isNotEmpty() },
                    relationship = relationship, basis = basis, dateOfDeath = if (basis == "heir") diedIso else null,
                    deathCertificateB64 = if (basis == "heir") deathCert?.b64() else null,
                    relationshipProofB64 = proof!!.b64(),
                    authorityDocumentB64 = if (basis != "heir") authority?.b64() else null,
                    addresses = filled.map { Address(street = it.street.trim(), city = it.city.trim(), state = it.state, zip = it.zip, county = it.county) },
                    consent = consent,
                ))
            },
            enabled = ready && !form.busy,
            modifier = Modifier.fillMaxWidth().height(52.dp).testTag("submitRelative"),
        ) {
            if (form.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            else Text("Submit for review", fontWeight = FontWeight.Bold)
        }
    }
}
