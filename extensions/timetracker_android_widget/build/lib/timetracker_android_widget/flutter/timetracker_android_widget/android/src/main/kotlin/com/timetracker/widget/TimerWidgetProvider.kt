package com.timetracker.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
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
            views.setInt(R.id.widget_root, "setBackgroundColor", colorOrFallback(state.categoryColor))

            if (finished || state.expired) {
                views.setViewVisibility(R.id.widget_clock, View.GONE)
                views.setViewVisibility(R.id.widget_finished, View.VISIBLE)
                views.setTextViewText(R.id.widget_finished, "Finished")
            } else if (state.active) {
                views.setViewVisibility(R.id.widget_clock, View.VISIBLE)
                views.setViewVisibility(R.id.widget_finished, View.GONE)
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
            }

            val activeRoute = if (state.active && state.isCountdown) "countdown" else "stopwatch"
            views.setOnClickPendingIntent(R.id.widget_clock, deepLink(context, activeRoute, 100))
            views.setOnClickPendingIntent(R.id.widget_timer_button, deepLink(context, "countdown", 101))
            views.setOnClickPendingIntent(R.id.widget_stopwatch_button, deepLink(context, "stopwatch", 102))
            manager.updateAppWidget(id, views)
        }

        private fun deepLink(context: Context, mode: String, requestCode: Int): PendingIntent {
            val intent = Intent(
                Intent.ACTION_VIEW,
                Uri.parse("timetracker://timer/$mode"),
            ).setPackage(context.packageName).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
            return PendingIntent.getActivity(
                context,
                requestCode,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
        }

        private fun colorOrFallback(value: String): Int = try {
            android.graphics.Color.parseColor(value)
        } catch (_: IllegalArgumentException) {
            android.graphics.Color.rgb(17, 24, 39)
        }
    }
}
