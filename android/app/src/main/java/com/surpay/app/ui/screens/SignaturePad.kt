package com.surpay.app.ui.screens

import android.graphics.Bitmap
import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import java.io.ByteArrayOutputStream

/** Strokes drawn with a finger, and a way to turn them into a PNG for the signed record. */
@Stable
class SignatureState {
    val strokes = mutableStateListOf<List<Offset>>()
    private val current = mutableStateListOf<Offset>()
    internal var size = mutableStateOf(IntSize.Zero)

    val isEmpty: Boolean get() = strokes.sumOf { it.size } < 6

    internal fun start(p: Offset) { current.clear(); current.add(p) }
    internal fun move(p: Offset) { current.add(p) }
    internal fun end() { if (current.isNotEmpty()) strokes.add(current.toList()); current.clear() }
    internal fun dot(p: Offset) { strokes.add(listOf(p, p + Offset(1f, 1f))) }
    internal val live: List<Offset> get() = current

    fun clear() { strokes.clear(); current.clear() }

    /** Black ink on white, the pad's size. */
    fun toPng(): ByteArray {
        val w = size.value.width.coerceAtLeast(300)
        val h = size.value.height.coerceAtLeast(120)
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        val canvas = android.graphics.Canvas(bmp)
        canvas.drawColor(android.graphics.Color.WHITE)
        val paint = Paint().apply {
            color = android.graphics.Color.BLACK; strokeWidth = 5f; style = Paint.Style.STROKE
            strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND; isAntiAlias = true
        }
        strokes.forEach { s ->
            val path = android.graphics.Path()
            s.forEachIndexed { i, p -> if (i == 0) path.moveTo(p.x, p.y) else path.lineTo(p.x, p.y) }
            canvas.drawPath(path, paint)
        }
        return ByteArrayOutputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it); it.toByteArray() }
    }
}

@Composable
fun rememberSignatureState() = remember { SignatureState() }

@Composable
fun SignaturePad(state: SignatureState, modifier: Modifier = Modifier) {
    val ink = Color(0xFF0F172A)
    Box(
        modifier.fillMaxWidth().height(160.dp)
            .background(Color.White, MaterialTheme.shapes.medium)
            .border(1.dp, MaterialTheme.colorScheme.outline, MaterialTheme.shapes.medium)
            .testTag("signaturePad"),
    ) {
        if (state.strokes.isEmpty() && state.live.isEmpty()) {
            Text("Sign here with your finger", Modifier.align(Alignment.Center), color = Color(0xFF94A3B8))
        }
        Text("✕", Modifier.align(Alignment.BottomStart).padding(start = 14.dp, bottom = 26.dp), color = Color(0xFF94A3B8))
        Box(Modifier.align(Alignment.BottomCenter).padding(horizontal = 32.dp, vertical = 30.dp).fillMaxWidth().height(1.dp)
            .background(Color(0xFFCBD5E1)))
        Canvas(
            Modifier.fillMaxSize()
                .onSizeChanged { state.size.value = it }
                .pointerInput(state) {
                    detectDragGestures(
                        onDragStart = { state.start(it) },
                        onDrag = { change, _ -> state.move(change.position) },
                        onDragEnd = { state.end() },
                        onDragCancel = { state.end() },
                    )
                }
                .pointerInput(state) { detectTapGestures(onTap = { state.dot(it) }) },
        ) {
            (state.strokes + listOf(state.live.toList())).forEach { s ->
                if (s.size < 2) return@forEach
                val path = Path().apply { s.forEachIndexed { i, p -> if (i == 0) moveTo(p.x, p.y) else lineTo(p.x, p.y) } }
                drawPath(path, ink, style = Stroke(width = 5f, cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
        }
    }
}
