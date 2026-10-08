package com.surpay.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.surpay.app.BuildConfig
import kotlinx.coroutines.delay

/** True once [busy] has been true for a few seconds — the server is probably waking up. */
@Composable
fun rememberIsSlow(busy: Boolean, afterMillis: Long = 5_000): Boolean {
    var slow by remember { mutableStateOf(false) }
    LaunchedEffect(busy) {
        slow = false
        if (busy) {
            delay(afterMillis)
            slow = true
        }
    }
    return slow
}

const val WAKING_UP_MESSAGE = "Waking up the Surpay server. The first request after a quiet spell can take up to a minute."

@Composable
fun ServerSettingsDialog(current: String, onSave: (String) -> Unit, onDismiss: () -> Unit) {
    var url by rememberSaveable { mutableStateOf(current) }
    val valid = url.trim().let { it.startsWith("https://") || it.startsWith("http://") } && url.trim().length > 10
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Server") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "The address of your Surpay backend, e.g. your Render URL. Changing it signs you out.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                OutlinedTextField(
                    value = url, onValueChange = { url = it.trim() },
                    singleLine = true, label = { Text("Server URL") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    modifier = Modifier.fillMaxWidth().testTag("serverUrl"),
                )
                TextButton(onClick = { url = BuildConfig.API_BASE_URL }) { Text("Reset to default") }
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(url) }, enabled = valid, modifier = Modifier.testTag("saveServer")) { Text("Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
fun LoadingScreen(message: String = "Connecting…") {
    val slow = rememberIsSlow(true)
    Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator()
            Spacer(Modifier.height(16.dp))
            Text(if (slow) WAKING_UP_MESSAGE else message, textAlign = TextAlign.Center)
        }
    }
}

@Composable
fun UnreachableScreen(message: String, serverUrl: String, onRetry: () -> Unit, onServerSettings: () -> Unit) {
    Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Can’t reach Surpay", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(8.dp))
            Text(message, textAlign = TextAlign.Center)
            Spacer(Modifier.height(4.dp))
            Text(
                serverUrl,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(16.dp))
            Button(onClick = onRetry) { Text("Try again") }
            TextButton(onClick = onServerSettings) { Text("Server settings") }
        }
    }
}
