package com.timetracker.widget

import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.graphics.Color
import android.widget.RemoteViews

/** A compact, non-click-through summary of today's daily targets. */
class TargetWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        ids.forEach { update(context, manager, it) }
    }

    companion object {
        fun updateAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, TargetWidgetProvider::class.java))
            ids.forEach { update(context, manager, it) }
        }

        private fun update(context: Context, manager: AppWidgetManager, id: Int) {
            val target = TimerWidgetStore.readTarget(context)
            val views = RemoteViews(context.packageName, R.layout.target_widget)
            when {
                !target.hasTarget -> {
                    views.setTextViewText(R.id.target_widget_status, "NO DAILY TARGET")
                    views.setTextViewText(R.id.target_widget_detail, "Add a target in Time Tracker")
                    views.setTextColor(R.id.target_widget_status, Color.rgb(226, 232, 240))
                }
                target.reached -> {
                    views.setTextViewText(R.id.target_widget_status, "TARGET REACHED")
                    views.setTextViewText(
                        R.id.target_widget_detail,
                        "${target.completedGoals} of ${target.totalGoals} goals completed - 100%",
                    )
                    views.setTextColor(R.id.target_widget_status, Color.rgb(110, 231, 183))
                }
                else -> {
                    views.setTextViewText(R.id.target_widget_status, "KEEP GOING")
                    views.setTextViewText(
                        R.id.target_widget_detail,
                        "${target.completedGoals} of ${target.totalGoals} goals completed - ${target.progressPercent}%",
                    )
                    views.setTextColor(R.id.target_widget_status, Color.rgb(253, 230, 138))
                }
            }
            views.setProgressBar(R.id.target_widget_progress, 100, target.progressPercent, false)
            manager.updateAppWidget(id, views)
        }
    }
}
