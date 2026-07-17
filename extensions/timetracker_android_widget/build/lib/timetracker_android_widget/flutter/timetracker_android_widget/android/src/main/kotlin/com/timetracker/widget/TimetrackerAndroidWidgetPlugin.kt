package com.timetracker.widget

import android.Manifest
import android.app.AlarmManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.annotation.NonNull
import io.flutter.embedding.engine.plugins.FlutterPlugin
import io.flutter.embedding.engine.plugins.activity.ActivityAware
import io.flutter.embedding.engine.plugins.activity.ActivityPluginBinding
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

class TimetrackerAndroidWidgetPlugin : FlutterPlugin, MethodChannel.MethodCallHandler, ActivityAware {
    private lateinit var context: Context
    private lateinit var channel: MethodChannel
    private var activityBinding: ActivityPluginBinding? = null

    override fun onAttachedToEngine(@NonNull binding: FlutterPlugin.FlutterPluginBinding) {
        context = binding.applicationContext
        channel = MethodChannel(binding.binaryMessenger, "timetracker_android_widget")
        channel.setMethodCallHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "requestPermissions" -> {
                requestPermissions()
                result.success(true)
            }
            "syncState" -> {
                @Suppress("UNCHECKED_CAST")
                TimerWidgetStore.write(context, call.arguments as? Map<*, *> ?: emptyMap<String, Any>())
                val state = TimerWidgetStore.read(context)
                if (state.active && state.isCountdown) {
                    CountdownAlarmScheduler.schedule(context, state)
                } else {
                    CountdownAlarmScheduler.cancel(context)
                }
                TimerWidgetProvider.updateAll(context)
                result.success(true)
            }
            "notifyFinished" -> {
                val token = (call.arguments as? Map<*, *>)?.get("token") as? String ?: ""
                val state = TimerWidgetStore.read(context)
                if (token.isNotBlank() && token == state.token && state.notifiedToken != token) {
                    CountdownNotifier.show(context, token)
                    TimerWidgetStore.markNotified(context, token)
                }
                TimerWidgetProvider.updateAll(context)
                result.success(true)
            }
            "refreshWidgets" -> {
                TimerWidgetProvider.updateAll(context)
                result.success(true)
            }
            else -> result.notImplemented()
        }
    }

    private fun requestPermissions() {
        val activity = activityBinding?.activity ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            activity.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 4601)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val manager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            if (!manager.canScheduleExactAlarms()) {
                activity.startActivity(
                    Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM)
                        .setData(Uri.parse("package:${context.packageName}")),
                )
            }
        }
    }

    override fun onDetachedFromEngine(@NonNull binding: FlutterPlugin.FlutterPluginBinding) {
        channel.setMethodCallHandler(null)
    }

    override fun onAttachedToActivity(binding: ActivityPluginBinding) { activityBinding = binding }
    override fun onDetachedFromActivityForConfigChanges() { activityBinding = null }
    override fun onReattachedToActivityForConfigChanges(binding: ActivityPluginBinding) { activityBinding = binding }
    override fun onDetachedFromActivity() { activityBinding = null }
}
