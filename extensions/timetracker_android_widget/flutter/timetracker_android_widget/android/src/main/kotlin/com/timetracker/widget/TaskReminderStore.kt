package com.timetracker.widget

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

internal data class TaskReminderSpec(
    val taskId: Int,
    val title: String,
    val dueEpochMs: Long,
    val reminderEpochMs: Long,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("task_id", taskId)
        .put("title", title)
        .put("due_epoch_ms", dueEpochMs)
        .put("reminder_epoch_ms", reminderEpochMs)

    companion object {
        fun fromMap(values: Map<*, *>?): TaskReminderSpec? {
            if (values == null) return null
            val taskId = (values["task_id"] as? Number)?.toInt() ?: return null
            val due = (values["due_epoch_ms"] as? Number)?.toLong() ?: return null
            val reminder = (values["reminder_epoch_ms"] as? Number)?.toLong() ?: return null
            return TaskReminderSpec(
                taskId = taskId,
                title = (values["title"] as? String)?.trim().orEmpty(),
                dueEpochMs = due,
                reminderEpochMs = reminder,
            )
        }

        fun fromJson(values: JSONObject): TaskReminderSpec? = try {
            TaskReminderSpec(
                taskId = values.getInt("task_id"),
                title = values.optString("title"),
                dueEpochMs = values.getLong("due_epoch_ms"),
                reminderEpochMs = values.getLong("reminder_epoch_ms"),
            )
        } catch (_: Exception) {
            null
        }
    }
}

/** Native copy of reminder specifications so Android can recover alarms itself. */
internal object TaskReminderStore {
    private const val PREFS = "timetracker_task_reminders"
    private const val ITEMS = "items"

    fun readAll(context: Context): List<TaskReminderSpec> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(ITEMS, "[]") ?: "[]"
        return try {
            val array = JSONArray(raw)
            buildList {
                for (index in 0 until array.length()) {
                    TaskReminderSpec.fromJson(array.getJSONObject(index))?.let(::add)
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun get(context: Context, taskId: Int): TaskReminderSpec? =
        readAll(context).firstOrNull { it.taskId == taskId }

    fun replace(context: Context, specs: List<TaskReminderSpec>) {
        val array = JSONArray()
        specs.distinctBy { it.taskId }.forEach { array.put(it.toJson()) }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(ITEMS, array.toString())
            .apply()
    }

    fun upsert(context: Context, spec: TaskReminderSpec) {
        replace(context, readAll(context).filterNot { it.taskId == spec.taskId } + spec)
    }

    fun remove(context: Context, taskId: Int) {
        replace(context, readAll(context).filterNot { it.taskId == taskId })
    }
}
