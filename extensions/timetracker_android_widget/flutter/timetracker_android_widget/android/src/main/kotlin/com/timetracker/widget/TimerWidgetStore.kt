package com.timetracker.widget

import android.content.Context

internal data class WidgetTimerState(
    val active: Boolean,
    val mode: String,
    val startEpochMs: Long,
    val targetSeconds: Long,
    val categoryLabel: String,
    val categoryColor: String,
    val token: String,
    val expired: Boolean,
    val notifiedToken: String,
) {
    val isCountdown: Boolean get() = mode == "countdown"
    val deadlineEpochMs: Long get() = startEpochMs + targetSeconds * 1000L
}

internal data class WidgetTargetState(
    val hasTarget: Boolean,
    val reached: Boolean,
    val completedGoals: Int,
    val totalGoals: Int,
    val progressPercent: Int,
)

/** Private native mirror of the Python timer state. It never writes SQLite. */
internal object TimerWidgetStore {
    private const val PREFS = "timetracker_timer_widget"
    private const val ACTIVE = "active"
    private const val MODE = "mode"
    private const val START = "start_epoch_ms"
    private const val TARGET = "target_seconds"
    private const val CATEGORY = "category_label"
    private const val COLOR = "category_color"
    private const val TOKEN = "timer_token"
    private const val EXPIRED = "expired"
    private const val NOTIFIED = "notified_token"
    private const val HAS_TARGET = "has_target"
    private const val TARGET_REACHED = "target_reached"
    private const val COMPLETED_GOALS = "completed_goals"
    private const val TOTAL_GOALS = "total_goals"
    private const val PROGRESS_PERCENT = "progress_percent"

    fun read(context: Context): WidgetTimerState {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return WidgetTimerState(
            active = prefs.getBoolean(ACTIVE, false),
            mode = prefs.getString(MODE, "stopwatch") ?: "stopwatch",
            startEpochMs = prefs.getLong(START, 0L),
            targetSeconds = prefs.getLong(TARGET, 0L),
            categoryLabel = prefs.getString(CATEGORY, "") ?: "",
            categoryColor = prefs.getString(COLOR, "#B91C1C") ?: "#B91C1C",
            token = prefs.getString(TOKEN, "") ?: "",
            expired = prefs.getBoolean(EXPIRED, false),
            notifiedToken = prefs.getString(NOTIFIED, "") ?: "",
        )
    }

    fun write(context: Context, values: Map<*, *>) {
        val prior = read(context)
        val active = values["active"] as? Boolean ?: false
        val token = values["token"] as? String ?: ""
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().apply {
            putBoolean(ACTIVE, active)
            putString(MODE, values["mode"] as? String ?: "stopwatch")
            putLong(START, (values["start_epoch_ms"] as? Number)?.toLong() ?: 0L)
            putLong(TARGET, (values["target_seconds"] as? Number)?.toLong() ?: 0L)
            putString(CATEGORY, values["category_label"] as? String ?: "")
            putString(COLOR, values["category_color"] as? String ?: "#B91C1C")
            // Keep the last token after Python clears the active state. It lets
            // a foreground completion alert race safely with the final sync.
            if (token.isNotBlank()) putString(TOKEN, token) else putString(TOKEN, prior.token)
            putBoolean(EXPIRED, active && (values["mode"] as? String == "countdown") &&
                System.currentTimeMillis() >= ((values["start_epoch_ms"] as? Number)?.toLong() ?: 0L) +
                    ((values["target_seconds"] as? Number)?.toLong() ?: 0L) * 1000L)
            apply()
        }
    }

    fun markExpired(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putBoolean(EXPIRED, true)
            .apply()
    }

    fun markNotified(context: Context, token: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(NOTIFIED, token)
            .apply()
    }

    fun readTarget(context: Context): WidgetTargetState {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return WidgetTargetState(
            hasTarget = prefs.getBoolean(HAS_TARGET, false),
            reached = prefs.getBoolean(TARGET_REACHED, false),
            completedGoals = prefs.getInt(COMPLETED_GOALS, 0),
            totalGoals = prefs.getInt(TOTAL_GOALS, 0),
            progressPercent = prefs.getInt(PROGRESS_PERCENT, 0).coerceIn(0, 100),
        )
    }

    fun writeTarget(context: Context, values: Map<*, *>) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().apply {
            putBoolean(HAS_TARGET, values["has_target"] as? Boolean ?: false)
            putBoolean(TARGET_REACHED, values["is_reached"] as? Boolean ?: false)
            putInt(COMPLETED_GOALS, (values["completed_goals"] as? Number)?.toInt() ?: 0)
            putInt(TOTAL_GOALS, (values["total_goals"] as? Number)?.toInt() ?: 0)
            putInt(
                PROGRESS_PERCENT,
                ((values["progress_percent"] as? Number)?.toInt() ?: 0).coerceIn(0, 100),
            )
            apply()
        }
    }
}
