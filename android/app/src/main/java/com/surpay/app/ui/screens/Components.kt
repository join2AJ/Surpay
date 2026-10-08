package com.surpay.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.surpay.app.ui.theme.HeroGradient

/** Green gradient headline card with white text. */
@Composable
fun HeroCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Box(
        modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.large)
            .background(HeroGradient),
    ) {
        CompositionLocalProvider(LocalContentColor provides Color.White) {
            Column(Modifier.padding(22.dp), content = content)
        }
    }
}

/** A white (dark: raised) card with a hairline border: the app's standard container. */
@Composable
fun SectionCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    padding: Dp = 16.dp,
    content: @Composable ColumnScope.() -> Unit,
) {
    val colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest)
    val border = CardDefaults.outlinedCardBorder()
    if (onClick != null) {
        Card(onClick = onClick, modifier = modifier.fillMaxWidth(), colors = colors, border = border,
            shape = MaterialTheme.shapes.medium) { Column(Modifier.padding(padding), content = content) }
    } else {
        Card(modifier = modifier.fillMaxWidth(), colors = colors, border = border, shape = MaterialTheme.shapes.medium) {
            Column(Modifier.padding(padding), content = content)
        }
    }
}

@Composable
fun IconCircle(
    icon: ImageVector,
    modifier: Modifier = Modifier,
    size: Dp = 40.dp,
    tint: Color = MaterialTheme.colorScheme.primary,
    background: Color = MaterialTheme.colorScheme.primaryContainer,
) {
    Box(modifier.size(size).clip(CircleShape).background(background), contentAlignment = Alignment.Center) {
        Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(size * 0.55f))
    }
}

@Composable
fun Pill(text: String, background: Color, content: Color, modifier: Modifier = Modifier) {
    Surface(color = background, contentColor = content, shape = RoundedCornerShape(50), modifier = modifier) {
        Text(text, Modifier.padding(horizontal = 10.dp, vertical = 4.dp), style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold)
    }
}

/** The "S" mark and wordmark. */
@Composable
fun Logo(modifier: Modifier = Modifier, onTap: (() -> Unit)? = null) {
    Row(modifier.then(if (onTap != null) Modifier.clickable(onClick = onTap) else Modifier),
        verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(38.dp).clip(RoundedCornerShape(11.dp)).background(HeroGradient), contentAlignment = Alignment.Center) {
            Text("S", color = Color.White, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.titleMedium)
        }
        Spacer(Modifier.size(10.dp))
        Text("Surpay", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
    }
}

/** A tappable row in a settings-style list. */
@Composable
fun NavRow(icon: ImageVector, title: String, subtitle: String? = null, badge: Int = 0, modifier: Modifier = Modifier,
           onClick: () -> Unit) {
    Row(
        modifier.fillMaxWidth().clip(MaterialTheme.shapes.medium).clickable(onClick = onClick).padding(vertical = 12.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        BadgedBox(badge = { if (badge > 0) Badge { Text("$badge") } }) { IconCircle(icon, size = 38.dp) }
        Column(Modifier.weight(1f).padding(horizontal = 14.dp)) {
            Text(title, fontWeight = FontWeight.SemiBold)
            subtitle?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(text.uppercase(), modifier.padding(top = 18.dp, bottom = 6.dp), style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant, fontWeight = FontWeight.Bold)
}

/** Amber "note" box for things the person should know. */
@Composable
fun NoteBox(text: String, modifier: Modifier = Modifier, icon: ImageVector? = null) {
    Surface(color = MaterialTheme.colorScheme.tertiaryContainer, contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
        shape = MaterialTheme.shapes.medium, modifier = modifier.fillMaxWidth()) {
        Row(Modifier.padding(14.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            icon?.let { Icon(it, null, modifier = Modifier.size(20.dp)) }
            Text(text, style = MaterialTheme.typography.bodySmall)
        }
    }
}
