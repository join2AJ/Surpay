package com.surpay.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.outlined.Gavel
import androidx.compose.material.icons.outlined.MoneyOff
import androidx.compose.material.icons.outlined.Savings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
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
import com.surpay.app.data.Policies
import com.surpay.app.ui.FormState
import com.surpay.app.ui.dollars

@Composable
fun AuthScreen(
    form: FormState,
    coverage: Coverage?,
    onSignup: (email: String, password: String, fullName: String, role: String) -> Unit,
    onLogin: (email: String, password: String) -> Unit,
    onClearError: () -> Unit,
    onDemoLogin: () -> Unit = {},
    onDemoAttorneyLogin: () -> Unit = {},
    onDemoAdmin: () -> Unit = {},
    onStaffDashboard: () -> Unit = {},
    onServerSettings: () -> Unit = {},
    policies: Policies? = null,
    onLoadPolicies: () -> Unit = {},
    developer: Boolean = false,
    onUnlockDeveloper: () -> Unit = {},
) {
    // "claimant" | "attorney" | "signin" once chosen; null shows the choice.
    var path by rememberSaveable { mutableStateOf<String?>(null) }
    var taps by remember { mutableIntStateOf(0) }
    val showDemo = BuildConfig.DEBUG || coverage?.demoLogin == true

    Column(
        Modifier.fillMaxSize().systemBarsPadding().imePadding().verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 20.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (path != null) {
                IconButton(onClick = { path = null; onClearError() }, modifier = Modifier.testTag("authBack")) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                }
            }
            // Tap the logo 7 times for tester options (server address).
            Logo(onTap = { if (++taps >= 7 && !developer) onUnlockDeveloper() })
        }
        Spacer(Modifier.height(20.dp))
        when (path) {
            null -> ChooseRole(coverage, showDemo, form, onChoose = { path = it; onClearError() },
                onDemoLogin = { onClearError(); onDemoLogin() },
                onDemoAttorneyLogin = { onClearError(); onDemoAttorneyLogin() },
                onDemoAdmin = { onClearError(); onDemoAdmin() })
            else -> AccountForm(
                path = path!!, form = form, policies = policies, onLoadPolicies = onLoadPolicies,
                onSwitch = { path = it; onClearError() }, onSignup = onSignup, onLogin = onLogin, onClearError = onClearError,
            )
        }
        Spacer(Modifier.height(24.dp))
        TrustRow(Icons.Filled.Lock, "Encrypted, never sold, and only you can see your results")
        TrustRow(Icons.Outlined.Gavel, "Claims are filed by licensed attorneys in your state")
        TrustRow(Icons.Outlined.MoneyOff, "Nothing upfront. A fee only if money is recovered")
        Spacer(Modifier.height(12.dp))
        Text(
            "Surpay is a technology platform, not a law firm or a government agency. Claims are made by you through " +
                "an independent licensed attorney. You can always claim surplus funds yourself, for free, from the county.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        TextButton(onClick = onStaffDashboard, modifier = Modifier.align(Alignment.CenterHorizontally).testTag("staffDashboard")) {
            Text("Surpay staff? Open the review dashboard", style = MaterialTheme.typography.bodySmall)
        }
        if (developer) {
            TextButton(onClick = onServerSettings, modifier = Modifier.align(Alignment.CenterHorizontally).testTag("serverSettings")) {
                Text("Server settings (testers)", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun ColumnScope.ChooseRole(
    coverage: Coverage?,
    showDemo: Boolean,
    form: FormState,
    onChoose: (String) -> Unit,
    onDemoLogin: () -> Unit,
    onDemoAttorneyLogin: () -> Unit,
    onDemoAdmin: () -> Unit,
) {
    Text("The county won’t tell you they owe you money. We will.", style = MaterialTheme.typography.headlineMedium)
    Spacer(Modifier.height(10.dp))
    Text(
        "When a home sells at a tax or foreclosure auction for more than was owed, the extra money belongs to the " +
            "former owner, or their family.",
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    if (coverage != null && coverage.records > 0) {
        Spacer(Modifier.height(14.dp))
        Pill(
            "Tracking ${dollars(coverage.totalAmountCents)} across ${coverage.counties.size} " +
                if (coverage.counties.size == 1) "county" else "counties",
            MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer,
        )
    }
    Spacer(Modifier.height(24.dp))
    Text("How would you like to use Surpay?", style = MaterialTheme.typography.titleMedium)
    Spacer(Modifier.height(10.dp))
    RoleCard(Icons.Outlined.Savings, "Find money owed to me",
        "For former homeowners, and heirs of a family member who has died", "roleClaimant") { onChoose("claimant") }
    Spacer(Modifier.height(10.dp))
    RoleCard(Icons.Outlined.Gavel, "I’m an attorney",
        "Join the network and take verified surplus cases in your counties", "roleAttorney") { onChoose("attorney") }
    Spacer(Modifier.height(6.dp))
    TextButton(onClick = { onChoose("signin") }, modifier = Modifier.align(Alignment.CenterHorizontally).testTag("goSignIn")) {
        Text("Already have an account? Sign in", fontWeight = FontWeight.SemiBold)
    }
    if (showDemo) {
        Spacer(Modifier.height(8.dp))
        Text("Testing? Try a demo account", style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(6.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onDemoLogin, enabled = !form.busy,
                modifier = Modifier.weight(1f).height(48.dp).testTag("demoLogin")) {
                if (form.busy) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) else Text("Claimant")
            }
            OutlinedButton(onClick = onDemoAttorneyLogin, enabled = !form.busy,
                modifier = Modifier.weight(1f).height(48.dp).testTag("demoAttorneyLogin")) {
                if (form.busy) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) else Text("Attorney")
            }
            OutlinedButton(onClick = onDemoAdmin, enabled = !form.busy,
                modifier = Modifier.weight(1f).height(48.dp).testTag("demoAdmin")) {
                if (form.busy) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) else Text("Admin")
            }
        }
        Text("Made-up people: “Jordan Testwell” with two matches, attorney “Avery Counsel” with a verified case " +
            "waiting, and the staff dashboard limited to demo data. They reset each time.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 4.dp))
        form.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 6.dp).testTag("error")) }
    }
}

@Composable
private fun RoleCard(icon: ImageVector, title: String, subtitle: String, tag: String, onClick: () -> Unit) {
    SectionCard(onClick = onClick, modifier = Modifier.testTag(tag), padding = 18.dp) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconCircle(icon, size = 48.dp)
            Column(Modifier.weight(1f).padding(start = 14.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun ColumnScope.AccountForm(
    path: String,
    form: FormState,
    policies: Policies?,
    onLoadPolicies: () -> Unit,
    onSwitch: (String) -> Unit,
    onSignup: (String, String, String, String) -> Unit,
    onLogin: (String, String) -> Unit,
    onClearError: () -> Unit,
) {
    val slow = rememberIsSlow(form.busy)
    val role = if (path == "attorney") "attorney" else "claimant"
    var signingUp by rememberSaveable(path) { mutableStateOf(path != "signin") }
    var name by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var agreed by rememberSaveable { mutableStateOf(false) }
    var reading by rememberSaveable { mutableStateOf<String?>(null) }
    val canSubmit = email.contains('@') && password.length >= 8 && (!signingUp || (name.trim().length >= 3 && agreed))

    Text(
        when {
            path == "attorney" -> "Attorney network"
            path == "signin" -> "Welcome back"
            else -> "Find money owed to you"
        },
        style = MaterialTheme.typography.headlineSmall,
    )
    Text(
        when {
            path == "attorney" -> "Create an attorney account, then apply with your bar license. We verify every attorney."
            path == "signin" -> "Sign in to your claimant or attorney account."
            else -> "Free to search. You’ll verify your ID next, so only you can see your results."
        },
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(16.dp))
    if (path != "signin") {
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            SegmentedButton(selected = signingUp, onClick = { signingUp = true; onClearError() },
                shape = SegmentedButtonDefaults.itemShape(0, 2), modifier = Modifier.testTag("tabSignUp")) { Text("Create account") }
            SegmentedButton(selected = !signingUp, onClick = { signingUp = false; onClearError() },
                shape = SegmentedButtonDefaults.itemShape(1, 2), modifier = Modifier.testTag("tabSignIn")) { Text("Sign in") }
        }
        Spacer(Modifier.height(14.dp))
    }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (signingUp) {
            OutlinedTextField(
                value = name, onValueChange = { name = it; onClearError() },
                label = { Text("Full legal name") },
                supportingText = { Text(if (role == "attorney") "As on your bar record" else "As on your photo ID") },
                singleLine = true, keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                modifier = Modifier.fillMaxWidth().testTag("name"),
            )
        }
        OutlinedTextField(
            value = email, onValueChange = { email = it; onClearError() }, label = { Text("Email") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
            modifier = Modifier.fillMaxWidth().testTag("email"),
        )
        OutlinedTextField(
            value = password, onValueChange = { password = it; onClearError() }, label = { Text("Password") }, singleLine = true,
            supportingText = if (signingUp) ({ Text("At least 8 characters") }) else null,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
            modifier = Modifier.fillMaxWidth().testTag("password"),
        )
    }
    if (signingUp) {
        Row(verticalAlignment = Alignment.Top, modifier = Modifier.padding(top = 8.dp)) {
            Checkbox(checked = agreed, onCheckedChange = { agreed = it; onClearError() }, modifier = Modifier.testTag("agreeTerms"))
            Column(Modifier.padding(top = 12.dp)) {
                Text("I agree to the Terms of Use and Privacy Notice, and confirm I’m 18 or older. I understand " +
                    "Surpay is not a law firm.", style = MaterialTheme.typography.bodyMedium)
                Row {
                    TextButton(onClick = { onLoadPolicies(); reading = "terms" }) { Text("Read Terms") }
                    TextButton(onClick = { onLoadPolicies(); reading = "privacy" }) { Text("Read Privacy Notice") }
                }
            }
        }
    }
    form.error?.let {
        Spacer(Modifier.height(8.dp))
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("error"))
    }
    if (slow) {
        Spacer(Modifier.height(8.dp))
        Text(WAKING_UP_MESSAGE, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    Spacer(Modifier.height(14.dp))
    Button(
        onClick = { if (signingUp) onSignup(email, password, name, role) else onLogin(email, password) },
        enabled = canSubmit && !form.busy,
        modifier = Modifier.fillMaxWidth().height(54.dp).testTag("submit"),
    ) {
        if (form.busy) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
        else Text(
            when {
                !signingUp -> "Sign in"
                role == "attorney" -> "Continue to attorney application"
                else -> "Create my free account"
            },
            fontWeight = FontWeight.Bold,
        )
    }
    if (path == "signin") {
        TextButton(onClick = { onSwitch("claimant") }, modifier = Modifier.align(Alignment.CenterHorizontally)) {
            Text("New here? Create an account")
        }
    }
    reading?.let { which ->
        PolicyDialog(which, policies, onDismiss = { reading = null })
    }
}

@Composable
fun PolicyDialog(which: String, policies: Policies?, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (which == "terms") "Terms of Use" else "Privacy Notice") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                if (policies == null) CircularProgressIndicator()
                else Text(if (which == "terms") policies.terms else policies.privacy, style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}

@Composable
private fun TrustRow(icon: ImageVector, text: String) {
    Row(Modifier.padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp))
        Spacer(Modifier.size(10.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
