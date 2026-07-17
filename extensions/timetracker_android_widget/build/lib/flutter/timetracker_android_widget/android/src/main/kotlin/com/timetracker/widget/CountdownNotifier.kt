package com.timetracker.widget

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

internal object CountdownNotifier {
    private const val CHANNEL_ID = "timetracker_countdown_complete"

    fun show(context: Context, token: String) {
        ensureChannel(context)
        val open = Intent(Intent.ACTION_VIEW, Uri.parse("timetracker://timer/countdown"))
            .setPackage(context.packageName)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val pending = PendingIntent.getActivity(
            context,
            902,
            open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle(context.getString(R.string.notification_title))
            .setContentText("Your Time Tracker countdown is complete.")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .setVibrate(longArrayOf(0, 300, 180, 300))
            .build()
        try {
            NotificationManagerCompat.from(context).notify(token.hashCode(), notification)
        } catch (_: SecurityException) {
            // Android 13 notification permission denial must never stop timing.
        }
    }

    private fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            context.getString(R.string.notification_channel_name),
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 300, 180, 300)
            setSound(
                android.provider.Settings.System.DEFAULT_ALARM_ALERT_URI,
                AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build(),
            )
        }
        manager.createNotificationChannel(channel)
    }
}
