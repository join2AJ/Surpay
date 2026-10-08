package com.surpay.app.ui.screens

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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
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
import com.surpay.app.data.Profile
import com.surpay.app.data.ProfileUpdate
import com.surpay.app.ui.FormState
import com.surpay.app.ui.US_STATES

private data class AddressDraft(
    val street: String = "",
    val city: String = "",
    val state: String = "",
    val zip: String = "",
    val county: String = "",
) {
    val isBlank get() = street.isBlank() && city.isBlank() && zip.isBlank() && county.isBlank()
    val isValid get() = street.trim().length >= 3 && city.trim().length >= 2 && state.length == 2 &&
        zip.length == 5 && county.trim().length >= 2
}

@Composable
fun ProfileScreen(
    profile: Profile,
    form: FormState,
    firstRun: Boolean,
    onSave: (ProfileUpdate) -> Unit,
    onLogout: () -> Unit,
    counties: Map<String, List<String>> = emptyMap(),
    onStateChosen: (String) -> Unit = {},
    modifier: Modifier = Modifier,
    header: (@Composable () -> Unit)? = null,
) {
    var fullName by rememberSaveable { mutableStateOf(profile.fullName) }
    var otherNames by rememberSaveable { mutableStateOf(profile.otherNames.joinToString(", ")) }
    var phone by rememberSaveable { mutableStateOf(profile.phone) }
    val addresses = remember {
        mutableStateListOf<AddressDraft>().apply {
            addAll(profile.addresses.map { AddressDraft(it.street, it.city, it.state, it.zip, it.county) })
            if (isEmpty()) add(AddressDraft())
        }
    }
    val filled = addresses.filterNot { it.isBlank }
    // At least one full address: it's how a county record gets confirmed as theirs.
    val canSave = fullName.trim().length >= 3 && filled.isNotEmpty() && filled.all { it.isValid }
    LaunchedEffect(Unit) { addresses.map { it.state }.filter { it.isNotBlank() }.distinct().forEach(onStateChosen) }

    Column(
        modifier
            .fillMaxSize()
            .imePadding()
            .verticalScroll(rememberScrollState()),
    ) {
      header?.invoke()
      Column(Modifier.padding(20.dp)) {
        Text(
            if (firstRun) "Where have you owned property?" else "Your details",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            "Add every home you’ve ever owned, in any county or state, with its full address. " +
                "Counties list surplus money under the owner’s name and the property address, so this " +
                "is how we confirm the money is yours.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(20.dp))

        // Names are locked to the verified ID so nobody can search under someone else's name.
        val locked = profile.nameLocked
        OutlinedTextField(
            value = fullName, onValueChange = { fullName = it }, readOnly = locked, enabled = !locked,
            label = { Text("Full legal name") }, singleLine = true,
            supportingText = if (locked) ({ Text("Matches your verified ID. Contact support to change it.") }) else null,
            modifier = Modifier.fillMaxWidth().testTag("fullName"),
        )
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = otherNames, onValueChange = { otherNames = it }, readOnly = locked, enabled = !locked,
            label = { Text("Other names (optional)") },
            supportingText = { Text(if (locked) "Locked with your verified ID" else "Maiden or previous names, separated by commas") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(4.dp))
        OutlinedTextField(
            value = phone, onValueChange = { phone = it },
            label = { Text("Mobile phone (optional)") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            modifier = Modifier.fillMaxWidth(),
        )

        Spacer(Modifier.height(20.dp))
        Text("Homes you’ve owned (at least one)", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(8.dp))
        addresses.forEachIndexed { i, a ->
            AddressCard(
                draft = a,
                index = i,
                counties = counties[a.state].orEmpty(),
                onChange = {
                    if (it.state != a.state) onStateChosen(it.state)
                    addresses[i] = it
                },
                onRemove = if (addresses.size > 1) ({ addresses.removeAt(i) }) else null,
            )
            Spacer(Modifier.height(10.dp))
        }
        OutlinedButton(onClick = { addresses.add(AddressDraft()) }) {
            Icon(Icons.Filled.Add, contentDescription = null)
            Spacer(Modifier.width(6.dp))
            Text("Add another home")
        }

        if (!canSave && fullName.trim().length >= 3) {
            Spacer(Modifier.height(12.dp))
            Text(
                "Fill in street, city, state, ZIP and county for each home.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        form.error?.let {
            Spacer(Modifier.height(12.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(20.dp))
        Button(
            onClick = {
                onSave(
                    ProfileUpdate(
                        fullName = fullName.trim(),
                        otherNames = otherNames.split(',').map { it.trim() }.filter { it.isNotEmpty() },
                        phone = phone.trim(),
                        addresses = filled.map {
                            Address(street = it.street.trim(), city = it.city.trim(), state = it.state, zip = it.zip.trim(), county = it.county.trim())
                        },
                    ),
                )
            },
            enabled = canSave && !form.busy,
            modifier = Modifier.fillMaxWidth().height(52.dp).testTag("saveProfile"),
        ) {
            if (form.busy) {
                CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            } else {
                Text(if (firstRun) "Save and continue" else "Save and search again", fontWeight = FontWeight.Bold)
            }
        }
        if (!firstRun) {
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = onLogout, modifier = Modifier.align(Alignment.CenterHorizontally)) {
                Text("Sign out")
            }
        }
      }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddressCard(
    draft: AddressDraft,
    index: Int,
    counties: List<String>,
    onChange: (AddressDraft) -> Unit,
    onRemove: (() -> Unit)?,
) {
    OutlinedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Home ${index + 1}", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                if (onRemove != null) {
                    IconButton(onClick = onRemove) { Icon(Icons.Filled.Close, contentDescription = "Remove property") }
                }
            }
            OutlinedTextField(
                value = draft.street, onValueChange = { onChange(draft.copy(street = it)) },
                label = { Text("Street address") }, singleLine = true,
                modifier = Modifier.fillMaxWidth().testTag("street$index"),
            )
            OutlinedTextField(
                value = draft.city, onValueChange = { onChange(draft.copy(city = it)) },
                label = { Text("City") }, singleLine = true, modifier = Modifier.fillMaxWidth().testTag("city$index"),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                var expanded by remember { mutableStateOf(false) }
                ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }, modifier = Modifier.weight(1f)) {
                    OutlinedTextField(
                        value = draft.state, onValueChange = {}, readOnly = true,
                        label = { Text("State") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                        modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth().testTag("state$index"),
                    )
                    ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                        US_STATES.forEach { s ->
                            DropdownMenuItem(text = { Text(s) }, onClick = {
                                onChange(if (s == draft.state) draft else draft.copy(state = s, county = ""))
                                expanded = false
                            })
                        }
                    }
                }
                OutlinedTextField(
                    value = draft.zip, onValueChange = { v -> onChange(draft.copy(zip = v.filter { it.isDigit() }.take(5))) },
                    label = { Text("ZIP") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.weight(1f).testTag("zip$index"),
                )
            }
            CountyField(draft, counties, index, onChange)
        }
    }
}

/** A dropdown of the state's counties; free text if the list couldn't be loaded. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CountyField(draft: AddressDraft, counties: List<String>, index: Int, onChange: (AddressDraft) -> Unit) {
    if (draft.state.isBlank()) {
        OutlinedTextField(
            value = "", onValueChange = {}, enabled = false, label = { Text("County") },
            supportingText = { Text("Choose the state first") }, modifier = Modifier.fillMaxWidth(),
        )
        return
    }
    if (counties.isEmpty()) {
        OutlinedTextField(
            value = draft.county, onValueChange = { onChange(draft.copy(county = it)) },
            label = { Text("County") }, singleLine = true,
            modifier = Modifier.fillMaxWidth().testTag("county$index"),
        )
        return
    }
    var expanded by remember { mutableStateOf(false) }
    // Keyed on the state (not the county) so clearing the choice while typing keeps the text.
    var query by remember(draft.state) { mutableStateOf(draft.county) }
    val shown = counties.filter { it.contains(query.trim(), ignoreCase = true) }.take(60)
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = query,
            onValueChange = {
                query = it
                expanded = true
                // Only a county picked from the list counts.
                val exact = counties.firstOrNull { c -> c.equals(it.trim(), ignoreCase = true) }.orEmpty()
                if (exact != draft.county) onChange(draft.copy(county = exact))
            },
            label = { Text("County") }, singleLine = true,
            supportingText = { Text("Type to search ${counties.size} counties in ${draft.state}") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryEditable).fillMaxWidth().testTag("county$index"),
        )
        ExposedDropdownMenu(expanded = expanded && shown.isNotEmpty(), onDismissRequest = { expanded = false }) {
            shown.forEach { c ->
                DropdownMenuItem(text = { Text(c) }, onClick = {
                    query = c
                    onChange(draft.copy(county = c))
                    expanded = false
                })
            }
        }
    }
}
