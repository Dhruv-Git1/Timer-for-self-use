package com.timetracker.widget

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class CountdownAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val token = intent.getStringExtra(EXTRA_TOKEN) ?: return
        val state = TimerWidgetStore.read(context)
        if (!state.active || !state.isCountdown || state.token != token) return
        if (System.currentTimeMillis() < state.deadlineEpochMs) {
            CountdownAlarmScheduler.schedule(context, state)
            return
        }
        TimerWidgetStore.markExpired(context)
        TimerWidgetProvider.updateAll(context)
        if (state.notifiedToken != token) {
            CountdownNotifier.show(context, token)
            TimerWidgetStore.markNotified(context, token)
        }
    }

    companion object {
        const val EXTRA_TOKEN = "timer_token"
    }
}
