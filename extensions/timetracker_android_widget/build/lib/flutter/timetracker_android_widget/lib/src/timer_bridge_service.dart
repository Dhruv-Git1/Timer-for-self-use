import 'package:flet/flet.dart';
import 'package:flutter/services.dart';

class TimerBridgeService extends FletService {
  TimerBridgeService({required super.control});

  static const _channel = MethodChannel('timetracker_android_widget');

  @override
  void init() {
    super.init();
    control.addInvokeMethodListener(_invokeMethod);
  }

  Future<dynamic> _invokeMethod(String name, dynamic args) async {
    switch (name) {
      case 'request_permissions':
        return _channel.invokeMethod('requestPermissions');
      case 'sync_state':
        return _channel.invokeMethod('syncState', Map<String, dynamic>.from(args));
      case 'sync_target_status':
        return _channel.invokeMethod('syncTargetStatus', Map<String, dynamic>.from(args));
      case 'sync_task_reminders':
        return _channel.invokeMethod(
          'syncTaskReminders',
          List<dynamic>.from(args ?? const <dynamic>[]),
        );
      case 'schedule_task_reminder':
        return _channel.invokeMethod(
          'scheduleTaskReminder',
          Map<String, dynamic>.from(args),
        );
      case 'cancel_task_reminder':
        return _channel.invokeMethod(
          'cancelTaskReminder',
          Map<String, dynamic>.from(args),
        );
      case 'notify_finished':
        return _channel.invokeMethod('notifyFinished', Map<String, dynamic>.from(args));
      case 'refresh_widgets':
        return _channel.invokeMethod('refreshWidgets');
      default:
        throw Exception('Unknown AndroidTimerBridge method: $name');
    }
  }

  @override
  void dispose() {
    control.removeInvokeMethodListener(_invokeMethod);
    super.dispose();
  }
}
