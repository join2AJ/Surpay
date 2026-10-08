package com.surpay.app.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File

/** Gets a photo as JPEG bytes, from the camera or the gallery. null = cancelled or failed. */
fun interface PhotoSource {
    fun request(fromCamera: Boolean, onResult: (ByteArray?) -> Unit)
}

/** Tests provide a fake here; the app uses the real camera and photo picker. */
val LocalPhotoSource = staticCompositionLocalOf<PhotoSource?> { null }

@Composable
fun rememberPhotoSource(): PhotoSource {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val pending = remember { arrayOfNulls<(ByteArray?) -> Unit>(1) }
    val captureUri = remember { arrayOfNulls<Uri>(1) }

    fun deliver(uri: Uri?) {
        val callback = pending[0] ?: return
        pending[0] = null
        if (uri == null) return callback(null)
        scope.launch {
            val bytes = withContext(Dispatchers.IO) { runCatching { compressPhoto(context, uri) }.getOrNull() }
            callback(bytes)
        }
    }

    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
        deliver(if (ok) captureUri[0] else null)
    }
    val gallery = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri -> deliver(uri) }

    val real = remember {
        PhotoSource { fromCamera, onResult ->
            pending[0] = onResult
            if (fromCamera) {
                val dir = File(context.cacheDir, "photos").apply { mkdirs() }
                val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", File(dir, "capture.jpg"))
                captureUri[0] = uri
                camera.launch(uri)
            } else {
                gallery.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
            }
        }
    }
    return LocalPhotoSource.current ?: real
}

/** Downscale to at most 1600px on the long side and re-encode as JPEG (keeps uploads ~200-500 KB). */
fun compressPhoto(context: Context, uri: Uri, maxSide: Int = 1600): ByteArray {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    context.contentResolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, bounds) }
    var sample = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= maxSide) sample *= 2
    val decoded = context.contentResolver.openInputStream(uri).use {
        BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample })
    } ?: error("Not an image")
    val scale = maxSide.toFloat() / maxOf(decoded.width, decoded.height)
    val bitmap = if (scale < 1f) {
        Bitmap.createScaledBitmap(decoded, (decoded.width * scale).toInt(), (decoded.height * scale).toInt(), true)
    } else {
        decoded
    }
    return ByteArrayOutputStream().use { out ->
        bitmap.compress(Bitmap.CompressFormat.JPEG, 82, out)
        out.toByteArray()
    }
}
