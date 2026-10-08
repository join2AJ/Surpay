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
) {
    val isBlank get() = street.isBlank() && city.isBlank() && zip.isBlank()
    val isValid get() = street.trim().length >= 3 && state.length == 2
}

@Composable
fun ProfileScreen(
    profile: Profile,
    form: FormState,
    firstRun: Boolean,
    onSave: (ProfileUpdate) -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var fullName by rememberSaveable { mutableStateOf(profile.fullName) }
    var otherNames by rememberSaveable { mutableStateOf(profile.otherNames.joinToString(", ")) }
    var phone by rememberSaveable { mutableStateOf(profile.phone) }
    val addresses = remember {
        mutableStateListOf<AddressDraft>().apply {
            addAll(profile.addresses.map { AddressDraft(it.street, it.city, it.state, it.zip) })
            if (isEmpty()) add(AddressDraft())
        }
    }
    val filled = addresses.filterNot { it.isBlank }
    val canSave = fullName.trim().length >= 3 && filled.all { it.isValid }

    Column(
        modifier
            .fillMaxSize()
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
    ) {
        Text(
            if (firstRun) "Where have you owned property?" else "Your details",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            "Counties list surplus money under the owner’s name and the property address. " +
                "Adding the homes you’ve owned lets us confirm a match instead of guessing.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(20.dp))

        OutlinedTextField(
            value = fullName, onValueChange = { fullName = it },
            label = { Text("Full legal name") }, singleLine = true,
            modifier = Modifier.fillMaxWidth().testTag("fullName"),
        )
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = otherNames, onValueChange = { otherNames = it },
            label = { Text("Other names (optional)") },
            supportingText = { Text("Maiden or previous names, separated by commas") },
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
        Text("Homes you owned", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(8.dp))
        addresses.forEachIndexed { i, a ->
            AddressCard(
                draft = a,
                index = i,
                onChange = { addresses[i] = it },
                onRemove = if (addresses.size > 1) ({ addresses.removeAt(i) }) else null,
            )
            Spacer(Modifier.height(10.dp))
        }
        OutlinedButton(onClick = { addresses.add(AddressDraft()) }) {
            Icon(Icons.Filled.Add, contentDescription = null)
            Spacer(Modifier.width(6.dp))
            Text("Add another property")
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
                        addresses = filled.map { Address(street = it.street.trim(), city = it.city.trim(), state = it.state, zip = it.zip.trim()) },
                    ),
                )
            },
            enabled = canSave && !form.busy,
            modifier = Modifier.fillMaxWidth().height(52.dp).testTag("saveProfile"),
        ) {
            if (form.busy) {
                CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            } else {
                Text(if (firstRun) "Search for my money" else "Save and search again", fontWeight = FontWeight.Bold)
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddressCard(draft: AddressDraft, index: Int, onChange: (AddressDraft) -> Unit, onRemove: (() -> Unit)?) {
    OutlinedCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Property ${index + 1}", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
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
                label = { Text("City") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
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
                            DropdownMenuItem(text = { Text(s) }, onClick = { onChange(draft.copy(state = s)); expanded = false })
                        }
                    }
                }
                OutlinedTextField(
                    value = draft.zip, onValueChange = { v -> onChange(draft.copy(zip = v.filter { it.isDigit() }.take(5))) },
                    label = { Text("ZIP") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}
