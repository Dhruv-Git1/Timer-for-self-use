package com.timetracker.widget

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
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
            "syncTargetStatus" -> {
                @Suppress("UNCHECKED_CAST")
                TimerWidgetStore.writeTarget(context, call.arguments as? Map<*, *> ?: emptyMap<String, Any>())
                TargetWidgetProvider.updateAll(context)
                result.success(true)
            }
            "syncTaskReminders" -> {
                @Suppress("UNCHECKED_CAST")
                val items = call.arguments as? List<Map<*, *>> ?: emptyList()
                TaskReminderScheduler.reconcile(context, items.mapNotNull(TaskReminderSpec::fromMap))
                result.success(true)
            }
            "scheduleTaskReminder" -> {
                val spec = TaskReminderSpec.fromMap(call.arguments as? Map<*, *>)
                if (spec == null) {
                    result.error("invalid_reminder", "Invalid task reminder payload", null)
                } else {
                    TaskReminderStore.upsert(context, spec)
                    TaskReminderScheduler.schedule(context, spec)
                    result.success(true)
                }
            }
            "cancelTaskReminder" -> {
                val taskId = ((call.arguments as? Map<*, *>)?.get("task_id") as? Number)?.toInt()
                if (taskId == null) {
                    result.error("invalid_task", "Missing task ID", null)
                } else {
                    TaskReminderScheduler.cancel(context, taskId)
                    TaskReminderStore.remove(context, taskId)
                    result.success(true)
                }
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
                TargetWidgetProvider.updateAll(context)
                result.success(true)
            }
            else -> result.notImplemented()
        }
    }

    private fun requestPermissions() {
        val activity = activityBinding?.activity ?: return
        val permissionPrefs = context.getSharedPreferences("timetracker_permissions", Context.MODE_PRIVATE)
        if (permissionPrefs.getBoolean("notification_requested", false)) return
        permissionPrefs.edit().putBoolean("notification_requested", true).apply()
        if (
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
                PackageManager.PERMISSION_GRANTED
        ) {
            activity.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 4601)
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
