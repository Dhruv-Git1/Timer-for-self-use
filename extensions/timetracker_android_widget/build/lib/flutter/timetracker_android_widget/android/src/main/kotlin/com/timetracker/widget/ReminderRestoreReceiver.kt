package com.timetracker.widget

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Restores persisted task reminders after reboot, update, or wall-clock changes. */
class ReminderRestoreReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val supported = setOf(
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED,
            Intent.ACTION_TIME_CHANGED,
            Intent.ACTION_TIMEZONE_CHANGED,
        )
        if (intent.action !in supported) return
        TaskReminderScheduler.reconcile(context, TaskReminderStore.readAll(context))
    }
}
