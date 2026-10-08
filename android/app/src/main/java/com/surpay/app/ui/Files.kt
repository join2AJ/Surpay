package com.surpay.app.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import java.io.File

/** Write [bytes] to a private cache file and open it with another app (PDF viewer, Files, Drive...). */
fun openOrShare(context: Context, bytes: ByteArray, fileName: String, mime: String) {
    val dir = File(context.cacheDir, "shared").apply { mkdirs() }
    val file = File(dir, fileName).apply { writeBytes(bytes) }
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
    val view = Intent(Intent.ACTION_VIEW).setDataAndType(uri, mime).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    val send = Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM, uri)
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    val intent = if (mime == "application/pdf") view else send
    try {
        context.startActivity(Intent.createChooser(intent, fileName).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (_: ActivityNotFoundException) {
        context.startActivity(Intent.createChooser(send, fileName).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
