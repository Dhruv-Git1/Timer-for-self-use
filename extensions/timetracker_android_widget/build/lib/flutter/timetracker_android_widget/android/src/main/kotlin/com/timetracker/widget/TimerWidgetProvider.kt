package com.timetracker.widget

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.os.SystemClock
import android.view.View
import android.widget.RemoteViews

class TimerWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        ids.forEach { update(context, manager, it) }
    }

    companion object {
        fun updateAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, TimerWidgetProvider::class.java))
            ids.forEach { update(context, manager, it) }
        }

        private fun update(context: Context, manager: AppWidgetManager, id: Int) {
            val state = TimerWidgetStore.read(context)
            val now = System.currentTimeMillis()
            val finished = state.isCountdown && state.active && now >= state.deadlineEpochMs
            val views = RemoteViews(context.packageName, R.layout.timer_widget)
            val mode = if (state.isCountdown) "COUNTDOWN" else "STOPWATCH"
            views.setTextViewText(R.id.widget_mode, mode)
            views.setTextViewText(
                R.id.widget_category,
                when {
                    finished || state.expired -> "Finished"
                    state.active -> state.categoryLabel
                    else -> "Ready when you are"
                },
            )
            if (finished || state.expired) {
                views.setViewVisibility(R.id.widget_clock, View.GONE)
                views.setViewVisibility(R.id.widget_finished, View.VISIBLE)
                views.setTextViewText(R.id.widget_finished, "Finished")
                views.setTextViewText(R.id.widget_status, "COUNTDOWN COMPLETE")
                views.setTextColor(R.id.widget_status, android.graphics.Color.rgb(253, 230, 138))
            } else if (state.active) {
                views.setViewVisibility(R.id.widget_clock, View.VISIBLE)
                views.setViewVisibility(R.id.widget_finished, View.GONE)
                views.setTextViewText(R.id.widget_status, "RUNNING")
                views.setTextColor(R.id.widget_status, android.graphics.Color.rgb(134, 239, 172))
                if (state.isCountdown) {
                    val remaining = (state.deadlineEpochMs - now).coerceAtLeast(0L)
                    views.setChronometer(
                        R.id.widget_clock,
                        SystemClock.elapsedRealtime() + remaining,
                        null,
                        true,
                    )
                    views.setChronometerCountDown(R.id.widget_clock, true)
                } else {
                    val elapsed = (now - state.startEpochMs).coerceAtLeast(0L)
                    views.setChronometer(
                        R.id.widget_clock,
                        SystemClock.elapsedRealtime() - elapsed,
                        null,
                        true,
                    )
                    views.setChronometerCountDown(R.id.widget_clock, false)
                }
            } else {
                views.setViewVisibility(R.id.widget_clock, View.VISIBLE)
                views.setViewVisibility(R.id.widget_finished, View.GONE)
                views.setChronometer(R.id.widget_clock, SystemClock.elapsedRealtime(), null, false)
                views.setTextViewText(R.id.widget_clock, "0:00")
                views.setTextViewText(R.id.widget_status, "READY IN TIME TRACKER")
                views.setTextColor(R.id.widget_status, android.graphics.Color.rgb(226, 232, 240))
            }

            manager.updateAppWidget(id, views)
        }
    }
}
