package com.surpay.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.FamilyRestroom
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.PrivacyTip
import androidx.compose.material.icons.outlined.VerifiedUser
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.surpay.app.BuildConfig
import com.surpay.app.data.Policies
import com.surpay.app.data.Profile
import com.surpay.app.ui.FormState

/** The Account tab: details, homes, family, notifications, privacy. */
@Composable
fun AccountScreen(
    profile: Profile,
    onDetails: () -> Unit,
    onFamily: () -> Unit,
    onNotifications: () -> Unit,
    onPrivacy: () -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
        HeroCard {
            Text(profile.fullName, style = MaterialTheme.typography.titleLarge)
            Text(profile.email, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(10.dp))
            Pill(if (profile.identityStatus == "approved") "✓ Identity verified" else "Identity not verified yet",
                androidx.compose.ui.graphics.Color.White.copy(alpha = 0.18f), androidx.compose.ui.graphics.Color.White)
        }
        Spacer(Modifier.height(10.dp))
        NavRow(Icons.Outlined.Home, "Your details and homes", "${profile.addresses.size} home(s) listed", onClick = onDetails,
            modifier = Modifier.testTag("navDetails"))
        NavRow(Icons.Outlined.FamilyRestroom, "Family members", "Claim as an heir, or under a power of attorney",
            onClick = onFamily, modifier = Modifier.testTag("navFamily"))
        NavRow(Icons.Outlined.Notifications, "Notifications", "Claim updates and messages", badge = profile.unreadNotifications,
            onClick = onNotifications, modifier = Modifier.testTag("navNotifications"))
        NavRow(Icons.Outlined.PrivacyTip, "Privacy and data", "Download your data, delete your account",
            onClick = onPrivacy, modifier = Modifier.testTag("navPrivacy"))
        Spacer(Modifier.height(8.dp))
        TextButton(onClick = onLogout, modifier = Modifier.align(Alignment.CenterHorizontally).testTag("signOut")) {
            Text("Sign out")
        }
        Text("Surpay ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.align(Alignment.CenterHorizontally))
    }
}

/** What we hold and how it's protected, plus the person's rights: access, erasure, sign out everywhere. */
@Composable
fun PrivacyScreen(
    form: FormState,
    policies: Policies?,
    onLoadPolicies: () -> Unit,
    onExport: () -> Unit,
    onLogoutEverywhere: () -> Unit,
    onDelete: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var confirmDelete by rememberSaveable { mutableStateOf(false) }
    var reading by rememberSaveable { mutableStateOf<String?>(null) }
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text("Privacy and data", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(10.dp))
        SectionCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconCircle(Icons.Outlined.VerifiedUser)
                Text("  How we protect you", fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(8.dp))
            listOf(
                "Your ID photos, selfie, signature, messages, date of birth and address are encrypted before they’re stored.",
                "All traffic is encrypted (HTTPS). We never sell your data or use it for ads.",
                "Every important action is recorded with the time, network address and device in a tamper-proof log, " +
                    "so nobody (including us) can quietly change what you submitted or signed.",
                "Only your verified attorney sees your documents, and only after accepting your case. They never get " +
                    "your email or phone number from us.",
            ).forEach { Text("•  $it", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(vertical = 3.dp)) }
        }
        SectionLabel("Your rights")
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            OutlinedButton(onClick = onExport, enabled = !form.busy, modifier = Modifier.fillMaxWidth().testTag("exportData")) {
                Text("Download a copy of my data")
            }
            OutlinedButton(onClick = onLogoutEverywhere, enabled = !form.busy, modifier = Modifier.fillMaxWidth()) {
                LogoutIcon(); Text("Sign out on all devices")
            }
            OutlinedButton(onClick = { onLoadPolicies(); reading = "privacy" }, modifier = Modifier.fillMaxWidth()) {
                Text("Read the Privacy Notice")
            }
            OutlinedButton(onClick = { onLoadPolicies(); reading = "terms" }, modifier = Modifier.fillMaxWidth()) {
                Text("Read the Terms of Use")
            }
        }
        SectionLabel("Delete my account")
        Text("This withdraws your consent and erases your account. If you’ve signed a claim agreement, we must keep " +
            "that claim’s records for up to 7 years for legal reasons; everything else is erased.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(8.dp))
        if (!confirmDelete) {
            OutlinedButton(onClick = { confirmDelete = true }, modifier = Modifier.fillMaxWidth().testTag("deleteAccount"),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) {
                Text("Delete my account")
            }
        } else {
            Surface(color = MaterialTheme.colorScheme.errorContainer, shape = MaterialTheme.shapes.medium) {
                Column(Modifier.padding(14.dp)) {
                    Text("Delete your account? This can’t be undone.", fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onErrorContainer)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                        Button(onClick = onDelete, enabled = !form.busy, modifier = Modifier.testTag("confirmDelete"),
                            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)) { Text("Delete") }
                        TextButton(onClick = { confirmDelete = false }) { Text("Cancel") }
                    }
                }
            }
        }
        form.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp)) }
        Spacer(Modifier.height(16.dp))
        Text("Questions or complaints about your data: privacy@surpay.app (Grievance Officer). We reply within 30 days.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    reading?.let { PolicyDialog(it, policies) { reading = null } }
}

@Composable
private fun LogoutIcon() {
    androidx.compose.material3.Icon(Icons.AutoMirrored.Outlined.Logout, null, Modifier.padding(end = 8.dp))
}
