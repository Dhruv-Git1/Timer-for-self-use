import 'package:flet/flet.dart';
import 'package:flutter/widgets.dart';

import 'timer_bridge_service.dart';

class Extension extends FletExtension {
  @override
  FletService? createService(Control control) {
    if (control.type == 'AndroidTimerBridge') {
      return TimerBridgeService(control: control);
    }
    return null;
  }

  @override
  Widget? createWidget(Key? key, Control control) => null;
}
