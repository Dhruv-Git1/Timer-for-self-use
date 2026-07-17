package com.timetracker.widget

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import java.text.DateFormat
import java.util.Date

internal object TaskReminderNotifier {
    private const val CHANNEL_ID = "timetracker_task_reminders"

    fun show(context: Context, spec: TaskReminderSpec) {
        ensureChannel(context)
        val open = Intent(
            Intent.ACTION_VIEW,
            Uri.parse("timetracker://timer/goals/task/${spec.taskId}"),
        ).setPackage(context.packageName).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val pending = PendingIntent.getActivity(
            context,
            20_000 + spec.taskId,
            open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val due = DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT)
            .format(Date(spec.dueEpochMs))
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle(spec.title.ifBlank { "Task reminder" })
            .setContentText("Due $due")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(30_000 + spec.taskId, notification)
        } catch (_: SecurityException) {
            // Permission denial must not affect the task database or app startup.
        }
    }

    private fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "Task reminders",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply { description = "Deadline reminders for Goals tasks" },
        )
    }
}
