package com.surpay.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.outlined.Gavel
import androidx.compose.material.icons.outlined.MoneyOff
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.surpay.app.BuildConfig
import com.surpay.app.data.Coverage
import com.surpay.app.ui.FormState
import com.surpay.app.ui.dollars

@Composable
fun AuthScreen(
    form: FormState,
    coverage: Coverage?,
    onSignup: (email: String, password: String, fullName: String) -> Unit,
    onLogin: (email: String, password: String) -> Unit,
    onClearError: () -> Unit,
    onDemoLogin: () -> Unit = {},
    onServerSettings: () -> Unit = {},
) {
    // Test builds always offer it; a release build only when the server has demo mode on.
    val showDemo = BuildConfig.DEBUG || coverage?.demoLogin == true
    val slow = rememberIsSlow(form.busy)
    var signingUp by rememberSaveable { mutableStateOf(true) }
    var name by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }

    val canSubmit = email.contains('@') && password.length >= 8 && (!signingUp || name.trim().length >= 3)

    Column(
        Modifier
            .fillMaxSize()
            .systemBarsPadding()
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 24.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Surface(color = MaterialTheme.colorScheme.primary, shape = RoundedCornerShape(10.dp)) {
                Box(Modifier.size(36.dp), contentAlignment = Alignment.Center) {
                    Text("S", color = MaterialTheme.colorScheme.onPrimary, fontWeight = FontWeight.ExtraBold)
                }
            }
            Spacer(Modifier.size(10.dp))
            Text("Surpay", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
        }
        Spacer(Modifier.height(28.dp))
        Text(
            "The county won’t tell you they owe you money. We will.",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(10.dp))
        Text(
            "When a home sells at a tax or foreclosure auction for more than was owed, the extra " +
                "money belongs to the former owner. Create an account and we’ll check every county list we track for your name.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (coverage != null && coverage.records > 0) {
            Spacer(Modifier.height(14.dp))
            Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(12.dp)) {
                Text(
                    "Tracking ${dollars(coverage.totalAmountCents)} in unclaimed surplus across " +
                        "${coverage.counties.size} ${if (coverage.counties.size == 1) "county" else "counties"}",
                    Modifier.padding(12.dp),
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
        Spacer(Modifier.height(24.dp))

        if (showDemo) {
            OutlinedButton(
                onClick = { onClearError(); onDemoLogin() },
                enabled = !form.busy,
                modifier = Modifier.fillMaxWidth().height(48.dp).testTag("demoLogin"),
            ) {
                Text("Try the demo account (testing)")
            }
            Text(
                "Signs in as “Jordan Testwell”, a made-up person with demo matches.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.align(Alignment.CenterHorizontally).padding(top = 4.dp),
            )
            Spacer(Modifier.height(20.dp))
        }

        Text(
            if (signingUp) "Create your free account" else "Welcome back",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(Modifier.height(12.dp))
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (signingUp) {
                OutlinedTextField(
                    value = name, onValueChange = { name = it; onClearError() },
                    label = { Text("Full legal name") },
                    supportingText = { Text("As it appeared on the property deed") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                    modifier = Modifier.fillMaxWidth().testTag("name"),
                )
            }
            OutlinedTextField(
                value = email, onValueChange = { email = it; onClearError() },
                label = { Text("Email") }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
                modifier = Modifier.fillMaxWidth().testTag("email"),
            )
            OutlinedTextField(
                value = password, onValueChange = { password = it; onClearError() },
                label = { Text("Password") }, singleLine = true,
                supportingText = if (signingUp) ({ Text("At least 8 characters") }) else null,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                modifier = Modifier.fillMaxWidth().testTag("password"),
            )
        }
        form.error?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("error"))
        }
        if (slow) {
            Spacer(Modifier.height(8.dp))
            Text(WAKING_UP_MESSAGE, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = { if (signingUp) onSignup(email, password, name) else onLogin(email, password) },
            enabled = canSubmit && !form.busy,
            modifier = Modifier.fillMaxWidth().height(52.dp).testTag("submit"),
        ) {
            if (form.busy) {
                CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
            } else {
                Text(if (signingUp) "Create account — it’s free" else "Sign in", fontWeight = FontWeight.Bold)
            }
        }
        TextButton(
            onClick = { signingUp = !signingUp; onClearError() },
            modifier = Modifier.align(Alignment.CenterHorizontally),
        ) {
            Text(if (signingUp) "Already have an account? Sign in" else "New here? Create an account")
        }

        Spacer(Modifier.height(20.dp))
        Text("How it works", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(8.dp))
        HowStep("1", "Create your account and verify your ID", "About 5 minutes. Only verified owners can see results, so nobody can look you up.")
        HowStep("2", "List every home you’ve owned", "We check county surplus lists for your name and those addresses.")
        HowStep("3", "See what you’re owed and claim it", "The law that entitles you, what you need to prove, and a licensed attorney to file.")

        Spacer(Modifier.height(16.dp))
        TrustRow(Icons.Filled.Lock, "Your details are encrypted and never sold")
        TrustRow(Icons.Outlined.Gavel, "Claims are filed by licensed attorneys in your state")
        TrustRow(Icons.Outlined.MoneyOff, "No upfront fees. We’re paid only if you are")
        Spacer(Modifier.height(16.dp))
        Text(
            "Surpay is not a law firm or a government agency. You can always claim surplus funds " +
                "yourself, for free, from the county that holds them.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        TextButton(onClick = onServerSettings, modifier = Modifier.align(Alignment.CenterHorizontally)) {
            Text("Server settings", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun HowStep(n: String, title: String, body: String) {
    Row(Modifier.padding(vertical = 6.dp), verticalAlignment = Alignment.Top) {
        Surface(shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.size(28.dp)) {
            Box(contentAlignment = Alignment.Center) {
                Text(n, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            }
        }
        Spacer(Modifier.size(12.dp))
        Column {
            Text(title, fontWeight = FontWeight.SemiBold)
            Text(body, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun TrustRow(icon: ImageVector, text: String) {
    Row(Modifier.padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp))
        Spacer(Modifier.size(10.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
