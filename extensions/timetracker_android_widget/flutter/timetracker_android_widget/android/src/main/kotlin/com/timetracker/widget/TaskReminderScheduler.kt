package com.timetracker.widget

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build

internal object TaskReminderScheduler {
    fun reconcile(context: Context, specs: List<TaskReminderSpec>) {
        val previousIds = TaskReminderStore.readAll(context).map { it.taskId }.toSet()
        val current = specs
            .filter { it.reminderEpochMs > System.currentTimeMillis() }
            .distinctBy { it.taskId }
        val currentIds = current.map { it.taskId }.toSet()
        (previousIds - currentIds).forEach { cancel(context, it) }
        TaskReminderStore.replace(context, current)
        current.forEach { schedule(context, it) }
    }

    fun schedule(context: Context, spec: TaskReminderSpec) {
        cancel(context, spec.taskId)
        if (spec.reminderEpochMs <= System.currentTimeMillis()) return
        val alarm = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pending = pendingIntent(context, spec.taskId, PendingIntent.FLAG_UPDATE_CURRENT) ?: return
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S || alarm.canScheduleExactAlarms()) {
            alarm.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, spec.reminderEpochMs, pending)
        } else {
            alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, spec.reminderEpochMs, pending)
        }
    }

    fun cancel(context: Context, taskId: Int) {
        val alarm = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pending = pendingIntent(context, taskId, PendingIntent.FLAG_NO_CREATE)
        if (pending != null) {
            alarm.cancel(pending)
            pending.cancel()
        }
    }

    private fun pendingIntent(context: Context, taskId: Int, extraFlag: Int): PendingIntent? {
        val intent = Intent(context, TaskReminderReceiver::class.java)
            .setAction("${context.packageName}.TASK_REMINDER.$taskId")
            .putExtra(TaskReminderReceiver.EXTRA_TASK_ID, taskId)
        return PendingIntent.getBroadcast(
            context,
            10_000 + taskId,
            intent,
            extraFlag or PendingIntent.FLAG_IMMUTABLE,
        )
    }
}
