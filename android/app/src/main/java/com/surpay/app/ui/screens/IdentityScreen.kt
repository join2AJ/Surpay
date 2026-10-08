package com.surpay.app.ui.screens

import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.surpay.app.data.IdentityRequest
import com.surpay.app.data.Profile
import com.surpay.app.ui.FormState
import com.surpay.app.ui.US_STATES
import com.surpay.app.ui.rememberPhotoSource
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.format.ResolverStyle

private val ID_TYPES = listOf("drivers_license" to "Driver’s license", "state_id" to "State ID card", "passport" to "Passport")
private val DOB_FORMAT = DateTimeFormatter.ofPattern("MM/dd/uuuu").withResolverStyle(ResolverStyle.STRICT)

/** "04/02/1980" -> "1980-04-02", or null if it isn't a real date of an adult. */
fun parseDob(text: String): String? {
    val d = runCatching { LocalDate.parse(text.trim(), DOB_FORMAT) }.getOrNull() ?: return null
    val today = LocalDate.now()
    return if (d.isAfter(today.minusYears(18)) || d.isBefore(today.minusYears(120))) null else d.toString()
}

/** Formats digits as MM/DD/YYYY while typing. */
private fun formatDob(input: String): String {
    val digits = input.filter { it.isDigit() }.take(8)
    return buildString {
        digits.forEachIndexed { i, c ->
            if (i == 2 || i == 4) append('/')
            append(c)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun IdentityScreen(profile: Profile, form: FormState, onSubmit: (IdentityRequest) -> Unit, modifier: Modifier = Modifier) {
    val photos = rememberPhotoSource()
    var legalName by rememberSaveable { mutableStateOf(profile.fullName) }
    var dob by rememberSaveable { mutableStateOf("") }
    var ssn4 by rememberSaveable { mutableStateOf("") }
    var phone by rememberSaveable { mutableStateOf(profile.phone) }
    var street by rememberSaveable { mutableStateOf("") }
    var city by rememberSaveable { mutableStateOf("") }
    var state by rememberSaveable { mutableStateOf("") }
    var zip by rememberSaveable { mutableStateOf("") }
    var idType by rememberSaveable { mutableStateOf("drivers_license") }
    var consent by rememberSaveable { mutableStateOf(false) }
    // Photos aren't saveable (too big for saved state); they survive recomposition only.
    var idFront by remember { mutableStateOf<ByteArray?>(null) }
    var idBack by remember { mutableStateOf<ByteArray?>(null) }
    var selfie by remember { mutableStateOf<ByteArray?>(null) }

    val dobIso = parseDob(dob)
    val ready = legalName.trim().length >= 3 && dobIso != null && ssn4.length == 4 && phone.filter { it.isDigit() }.length >= 10 &&
        street.trim().length >= 3 && city.trim().length >= 2 && state.length == 2 && zip.length == 5 &&
        idFront != null && selfie != null && consent

    Column(modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text("Verify your identity", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        Text(
            "The county will only release money to the right person, so we confirm it’s you before " +
                "an attorney files. Takes about 5 minutes.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(Modifier.padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.Lock, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(16.dp))
            Text(
                "  Photos are encrypted and only used to verify you and file your claim.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        Section("About you")
        Field(legalName, { legalName = it }, "Full legal name (as on your ID)", "legalName")
        OutlinedTextField(
            value = dob, onValueChange = { dob = formatDob(it) }, label = { Text("Date of birth (MM/DD/YYYY)") },
            singleLine = true, isError = dob.length == 10 && dobIso == null,
            supportingText = if (dob.length == 10 && dobIso == null) ({ Text("Enter a real date; you must be 18 or older") }) else null,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            modifier = Modifier.fillMaxWidth().testTag("dob"),
        )
        OutlinedTextField(
            value = ssn4, onValueChange = { v -> ssn4 = v.filter { it.isDigit() }.take(4) },
            label = { Text("Last 4 digits of your SSN") }, singleLine = true,
            supportingText = { Text("Counties and courts use it to tell apart people with the same name") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
            modifier = Modifier.fillMaxWidth().testTag("ssn4"),
        )
        OutlinedTextField(
            value = phone, onValueChange = { phone = it.take(20) }, label = { Text("Mobile phone") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            modifier = Modifier.fillMaxWidth().testTag("phone"),
        )

        Section("Where you live now")
        Field(street, { street = it }, "Street address", "curStreet")
        Field(city, { city = it }, "City", "curCity")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            var open by remember { mutableStateOf(false) }
            ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }, modifier = Modifier.weight(1f)) {
                OutlinedTextField(
                    value = state, onValueChange = {}, readOnly = true, label = { Text("State") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(open) },
                    modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth().testTag("curState"),
                )
                ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                    US_STATES.forEach { s -> DropdownMenuItem(text = { Text(s) }, onClick = { state = s; open = false }) }
                }
            }
            OutlinedTextField(
                value = zip, onValueChange = { v -> zip = v.filter { it.isDigit() }.take(5) }, label = { Text("ZIP") },
                singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.weight(1f).testTag("curZip"),
            )
        }

        Section("Photo ID")
        var typeOpen by remember { mutableStateOf(false) }
        ExposedDropdownMenuBox(expanded = typeOpen, onExpandedChange = { typeOpen = it }) {
            OutlinedTextField(
                value = ID_TYPES.first { it.first == idType }.second, onValueChange = {}, readOnly = true,
                label = { Text("Type of ID") }, trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(typeOpen) },
                modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth(),
            )
            ExposedDropdownMenu(expanded = typeOpen, onDismissRequest = { typeOpen = false }) {
                ID_TYPES.forEach { (k, label) -> DropdownMenuItem(text = { Text(label) }, onClick = { idType = k; typeOpen = false }) }
            }
        }
        Spacer(Modifier.height(8.dp))
        PhotoSlot("Front of your ID", "All four corners visible, no glare.", idFront, "idFront",
            onCamera = { photos.request(true) { b -> if (b != null) idFront = b } },
            onGallery = { photos.request(false) { b -> if (b != null) idFront = b } })
        if (idType != "passport") {
            PhotoSlot("Back of your ID (optional)", "Helps if the front is hard to read.", idBack, "idBack",
                onCamera = { photos.request(true) { b -> if (b != null) idBack = b } },
                onGallery = { photos.request(false) { b -> if (b != null) idBack = b } })
        }
        PhotoSlot("A selfie", "Face the camera in good light, no hat or sunglasses.", selfie, "selfie",
            onCamera = { photos.request(true) { b -> if (b != null) selfie = b } },
            onGallery = { photos.request(false) { b -> if (b != null) selfie = b } })

        Row(verticalAlignment = Alignment.Top, modifier = Modifier.padding(top = 8.dp)) {
            Checkbox(checked = consent, onCheckedChange = { consent = it }, modifier = Modifier.testTag("consent"))
            Text(
                "I confirm this is my information and my ID, and I authorize Surpay and its partner attorney " +
                    "to use it to verify my identity and pursue my claim.",
                style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 12.dp),
            )
        }

        form.error?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(12.dp))
        Button(
            onClick = {
                onSubmit(IdentityRequest(
                    legalName = legalName.trim(), dateOfBirth = dobIso!!, ssnLast4 = ssn4, phone = phone.trim(),
                    street = street.trim(), city = city.trim(), state = state, zip = zip, idType = idType,
                    idFrontB64 = idFront!!.b64(), idBackB64 = idBack?.b64(), selfieB64 = selfie!!.b64(), consent = consent,
                ))
            },
            enabled = ready && !form.busy,
            modifier = Modifier.fillMaxWidth().height(52.dp).testTag("submitIdentity"),
        ) {
            if (form.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            else Text("Submit and continue to agreement", fontWeight = FontWeight.Bold)
        }
        if (!ready) {
            Text(
                "Fill in every field, add the front of your ID and a selfie, and tick the box.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }
}

private fun ByteArray.b64(): String = Base64.encodeToString(this, Base64.NO_WRAP)

@Composable
private fun Section(title: String) {
    Spacer(Modifier.height(20.dp))
    Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    Spacer(Modifier.height(6.dp))
}

@Composable
private fun Field(value: String, onChange: (String) -> Unit, label: String, tag: String) {
    OutlinedTextField(
        value = value, onValueChange = onChange, label = { Text(label) }, singleLine = true,
        modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp).testTag(tag),
    )
}

@Composable
private fun PhotoSlot(title: String, hint: String, bytes: ByteArray?, tag: String, onCamera: () -> Unit, onGallery: () -> Unit) {
    OutlinedCard(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            val bitmap = remember(bytes) { bytes?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() } }
            if (bitmap != null) {
                Image(bitmap, contentDescription = title, contentScale = ContentScale.Crop, modifier = Modifier.size(64.dp))
                Spacer(Modifier.size(12.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold)
                Text(if (bytes != null) "Added ✓" else hint, style = MaterialTheme.typography.bodySmall,
                    color = if (bytes != null) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.testTag("${tag}Status"))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
                    Button(onClick = onCamera, modifier = Modifier.testTag("${tag}Camera")) { Text(if (bytes != null) "Retake" else "Take photo") }
                    OutlinedButton(onClick = onGallery) { Text("Gallery") }
                }
            }
        }
    }
}
