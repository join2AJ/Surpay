package com.surpay.app.notify

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.surpay.app.BuildConfig
import com.surpay.app.MainActivity
import com.surpay.app.R
import com.surpay.app.data.AppPrefs
import com.surpay.app.data.OfflineDemoApi
import com.surpay.app.data.ServerStore
import com.surpay.app.data.SurpayApi
import com.surpay.app.data.TokenStore
import com.surpay.app.data.deviceInfo
import java.util.concurrent.TimeUnit

/**
 * Checks the server for new updates about every 15 minutes (Android's minimum for background
 * work) and shows them as phone notifications: claim progress, money released, new messages,
 * new case offers. No third-party push service is involved.
 */
class NotificationWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val ctx = applicationContext
        val tokens = TokenStore(ctx)
        val token = tokens.load() ?: return Result.success()
        if (token == OfflineDemoApi.OFFLINE_DEMO_TOKEN) return Result.success()
        val server = ServerStore(ctx, BuildConfig.API_BASE_URL).also { it.load() }
        val api = SurpayApi.create({ server.current }, { tokens.cached }, deviceInfo(ctx, BuildConfig.VERSION_NAME))
        val prefs = AppPrefs(ctx)
        val last = prefs.lastNotification()
        val fresh = runCatching { api.notifications(afterId = last) }.getOrElse { return Result.retry() }
        val unread = fresh.items.filter { !it.read }.sortedBy { it.id }
        // The first run after sign-in only sets the bookmark, so old updates don't all pop up at once.
        if (last > 0) unread.forEach { show(ctx, it.id, it.title, it.body, it.kind) }
        fresh.items.maxOfOrNull { it.id }?.let { if (it > last) prefs.setLastNotification(it) }
        return Result.success()
    }

    companion object {
        private const val WORK = "surpay-notifications"
        const val CHANNEL_UPDATES = "claim_updates"
        const val CHANNEL_MONEY = "money_released"

        fun schedule(context: Context) {
            createChannels(context)
            val request = PeriodicWorkRequestBuilder<NotificationWorker>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.KEEP, request)
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK)
        }

        private fun createChannels(context: Context) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
            val nm = context.getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(NotificationChannel(CHANNEL_UPDATES, "Claim updates and messages",
                NotificationManager.IMPORTANCE_DEFAULT))
            nm.createNotificationChannel(NotificationChannel(CHANNEL_MONEY, "Money released",
                NotificationManager.IMPORTANCE_HIGH))
        }

        fun show(context: Context, id: Int, title: String, body: String, kind: String) {
            if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                return
            }
            createChannels(context)
            val open = PendingIntent.getActivity(
                context, id, Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            val n = NotificationCompat.Builder(context, if (kind == "money_released") CHANNEL_MONEY else CHANNEL_UPDATES)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(NotificationCompat.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setContentIntent(open)
                .setPriority(if (kind == "money_released") NotificationCompat.PRIORITY_HIGH else NotificationCompat.PRIORITY_DEFAULT)
                .build()
            NotificationManagerCompat.from(context).notify(id, n)
        }
    }
}
