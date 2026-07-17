package com.timetracker.widget

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class TaskReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val taskId = intent.getIntExtra(EXTRA_TASK_ID, -1)
        if (taskId < 0) return
        val spec = TaskReminderStore.get(context, taskId) ?: return
        if (System.currentTimeMillis() < spec.reminderEpochMs) {
            TaskReminderScheduler.schedule(context, spec)
            return
        }
        TaskReminderNotifier.show(context, spec)
        TaskReminderStore.remove(context, taskId)
    }

    companion object {
        const val EXTRA_TASK_ID = "goal_task_id"
    }
}
