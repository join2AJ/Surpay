package com.surpay.app.ui.screens

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.surpay.app.data.Chat
import com.surpay.app.ui.FormState
import kotlinx.coroutines.delay
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Same rules as the server (surpay/chat.py), checked as you type so you know before sending. */
private val CONTACT_PATTERNS = listOf(
    Regex("""\(?\b\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}\b""") to "phone numbers",
    Regex("""\+\d[\d\s\-().]{7,}\d""") to "phone numbers",
    Regex("""\d{10,}""") to "phone numbers",
    Regex("""[\w.+\-]+@[\w\-]+\.[\w.\-]+""") to "email addresses",
    Regex("""(?:https?://|www\.)\S+""", RegexOption.IGNORE_CASE) to "links",
    Regex("""\b[\w\-]+\.(?:com|net|org|io|me|co|us|app|info|biz|ly)\b""", RegexOption.IGNORE_CASE) to "links",
    Regex("""\b(?:whats\s*app|telegram|signal app|wechat|instagram|insta|facebook|messenger|snapchat|skype|zoom|google meet|text me|call me|my cell|my number)\b""",
        RegexOption.IGNORE_CASE) to "other contact methods",
)

fun contactWarning(text: String): String? {
    val found = CONTACT_PATTERNS.filter { it.first.containsMatchIn(text) }.map { it.second }.distinct()
    return if (found.isEmpty()) null else "Messages can’t include ${found.joinToString(" or ")}. Keep the conversation in Surpay."
}

private val TIME = DateTimeFormatter.ofPattern("MMM d, h:mm a", Locale.US)

private fun stamp(iso: String) = runCatching {
    OffsetDateTime.parse(if (iso.endsWith("Z") || iso.contains('+')) iso else "${iso}Z").atZoneSameInstant(ZoneId.systemDefault()).format(TIME)
}.getOrDefault(iso.take(16))

/** Messages between a client and their attorney about one claim. [me] is "claimant" or "attorney". */
@Composable
fun ChatScreen(
    chat: Chat?,
    me: String,
    form: FormState,
    onRefresh: () -> Unit,
    onSend: (String, () -> Unit) -> Unit,
    modifier: Modifier = Modifier,
) {
    LaunchedEffect(Unit) {
        while (true) {
            onRefresh()
            delay(20_000)
        }
    }
    if (chat == null) {
        Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        return
    }
    var draft by rememberSaveable { mutableStateOf("") }
    var showRules by rememberSaveable { mutableStateOf(chat.messages.isEmpty()) }
    val list = rememberLazyListState()
    LaunchedEffect(chat.messages.size) { if (chat.messages.isNotEmpty()) list.animateScrollToItem(chat.messages.size) }
    val warning = contactWarning(draft)

    Column(modifier.fillMaxSize().imePadding()) {
        Surface(color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.fillMaxWidth().animateContentSize()
            .clickable { showRules = !showRules }.testTag("codeOfConduct")) {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 10.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.Shield, null, tint = MaterialTheme.colorScheme.primary)
                    Text("  Private, recorded, and kept in the app", fontWeight = FontWeight.SemiBold,
                        style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                    Text(if (showRules) "Hide" else "Rules", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                }
                if (showRules) {
                    chat.codeOfConduct.forEach {
                        Text("•  $it", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 4.dp))
                    }
                }
            }
        }
        LazyColumn(Modifier.weight(1f).fillMaxWidth(), state = list, contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item {
                Text("Conversation with ${chat.counterpart}", style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            items(chat.messages, key = { it.id }) { m ->
                val mine = m.senderRole == me
                Row(Modifier.fillMaxWidth(), horizontalArrangement = if (mine) Arrangement.End else Arrangement.Start) {
                    Surface(
                        color = if (mine) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceContainer,
                        contentColor = if (mine) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
                        shape = RoundedCornerShape(18.dp, 18.dp, if (mine) 4.dp else 18.dp, if (mine) 18.dp else 4.dp),
                        modifier = Modifier.widthIn(max = 300.dp).testTag("message${m.id}"),
                    ) {
                        Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                            Text(m.body)
                            Text(stamp(m.createdAt) + if (mine && m.read) " · Read" else "",
                                style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        }
        if (!chat.canSend) {
            Surface(color = MaterialTheme.colorScheme.surfaceVariant, modifier = Modifier.fillMaxWidth()) {
                Text(chat.waitingReason.ifBlank { "You can’t send messages on this case yet." },
                    Modifier.padding(16.dp).testTag("chatWaiting"), style = MaterialTheme.typography.bodyMedium)
            }
            return@Column
        }
        Column(Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
            (warning ?: form.error)?.let {
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(bottom = 4.dp).testTag("chatWarning"))
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = draft, onValueChange = { draft = it.take(2000) },
                    placeholder = { Text(if (me == "attorney") "Write to your client" else "Write to your attorney") },
                    modifier = Modifier.weight(1f).testTag("chatInput"), maxLines = 5,
                    shape = RoundedCornerShape(24.dp),
                )
                IconButton(
                    onClick = { onSend(draft.trim()) { draft = "" } },
                    enabled = draft.isNotBlank() && warning == null && !form.busy,
                    modifier = Modifier.testTag("chatSend"),
                ) { Icon(Icons.AutoMirrored.Filled.Send, "Send", tint = MaterialTheme.colorScheme.primary) }
            }
        }
    }
}
