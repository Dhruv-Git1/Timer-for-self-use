"""Regression tests for tasks, routines, custom cycles, and goal migrations."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import flet as ft

import config
from app.models.goal import GoalTask, PERIOD_CUSTOM
from app.services.context import AppContext
from mobile.app_shell import goal_task_id_from_route
from mobile.services.android_timer_bridge import task_reminder_payload
from mobile.widgets.sheets import dismiss_sheet, form_sheet, show_sheet


class GoalsExpansionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ctx = AppContext(os.path.join(self.temp.name, "expanded-goals.db"))
        for category in self.ctx.category_service.list_categories():
            self.ctx.category_service.set_archived(category.id, True)
        ok, message, self.category_id = self.ctx.category_service.create(
            "Goal test counter", "#3B82F6", False, 0,
            tracking_mode="counter", target_count=1, unit_label="pages",
        )
        self.assertTrue(ok, message)

    def tearDown(self) -> None:
        self.ctx.close()
        self.temp.cleanup()

    def _target(self, title: str, start: str, count: int, unit: str) -> int:
        ok, message, goal_id = self.ctx.goal_service.create(
            title,
            self.category_id,
            10,
            PERIOD_CUSTOM,
            start,
            None,
            count,
            unit,
        )
        self.assertTrue(ok, message)
        self.assertIsNotNone(goal_id)
        return goal_id

    def test_tasks_allow_arbitrary_deadlines_reminders_and_next_day_history(self) -> None:
        now = datetime(2026, 7, 17, 10, 0)
        ok, message, task_id = self.ctx.goal_service.create_task(
            "Bring groceries", "2038-12-31 17:05", 180, now=now
        )
        self.assertTrue(ok, message)
        task = self.ctx.goal_service.get_task(task_id)
        self.assertEqual(task.reminder_at, datetime(2038, 12, 31, 14, 5))
        self.assertEqual(self.ctx.goal_service.pending_task_reminders(now), [task])

        ok, message, _ = self.ctx.goal_service.create_task(
            "Too late", "2026-07-17 11:00", 120, now=now
        )
        self.assertFalse(ok)
        self.assertIn("future", message)

        done_at = datetime(2026, 7, 17, 18, 0)
        self.assertTrue(self.ctx.goal_service.set_task_completed(task_id, True, now=done_at)[0])
        self.assertIn(task_id, [item.id for item in self.ctx.goal_service.list_tasks(as_of="2026-07-17")])
        self.assertNotIn(task_id, [item.id for item in self.ctx.goal_service.list_tasks(as_of="2026-07-18")])
        self.assertIn(task_id, [item.id for item in self.ctx.goal_service.list_tasks(include_history=True)])

        self.assertTrue(self.ctx.goal_service.set_task_completed(task_id, False)[0])
        self.assertIn(task_id, [item.id for item in self.ctx.goal_service.list_tasks(as_of="2026-07-18")])
        self.assertTrue(self.ctx.goal_service.delete_task(task_id)[0])
        self.assertIsNone(self.ctx.goal_service.get_task(task_id))

    def test_custom_intervals_cross_day_week_and_clipped_month_boundaries(self) -> None:
        ten_day = self._target("Ten day sprint", "2026-01-28", 10, "days")
        three_week = self._target("Three week sprint", "2026-01-31", 3, "weeks")
        two_month = self._target("Two month sprint", "2026-01-31", 2, "months")

        progress = self.ctx.goal_service.progress_for_goal(ten_day, "2026-02-06")
        self.assertEqual((progress.window_start, progress.window_end), ("2026-01-28", "2026-02-06"))
        progress = self.ctx.goal_service.progress_for_goal(ten_day, "2026-02-07")
        self.assertEqual((progress.window_start, progress.window_end), ("2026-02-07", "2026-02-16"))

        progress = self.ctx.goal_service.progress_for_goal(three_week, "2026-02-21")
        self.assertEqual((progress.window_start, progress.window_end), ("2026-02-21", "2026-03-13"))

        progress = self.ctx.goal_service.progress_for_goal(two_month, "2026-03-30")
        self.assertEqual((progress.window_start, progress.window_end), ("2026-01-31", "2026-03-30"))
        progress = self.ctx.goal_service.progress_for_goal(two_month, "2026-03-31")
        self.assertEqual((progress.window_start, progress.window_end), ("2026-03-31", "2026-05-30"))
        self.assertLessEqual(len(self.ctx.goal_service.target_history(ten_day, "2026-07-17").labels), 12)

    def test_weekend_routine_has_independent_history_pending_day_and_heatmap(self) -> None:
        weekend_mask = (1 << 5) | (1 << 6)
        ok, message, routine_id = self.ctx.goal_service.create_routine(
            "Revise this week's lessons", self.category_id, weekend_mask, "2026-07-04"
        )
        self.assertTrue(ok, message)
        for day in ("2026-07-04", "2026-07-05", "2026-07-11", "2026-07-12"):
            self.assertTrue(
                self.ctx.goal_service.set_routine_completed(
                    routine_id, day, True, as_of="2026-07-18"
                )[0]
            )

        stats = self.ctx.goal_service.routine_stats(routine_id, "2026-07-18")
        self.assertEqual(stats.completed, 4)
        self.assertEqual(stats.scheduled, 4)
        self.assertEqual(stats.current_streak, 4)
        self.assertEqual(stats.completion_pct, 100.0)
        states = self.ctx.goal_service.routine_heatmap(routine_id, 2026, "2026-07-18")
        self.assertEqual(states["2026-07-12"], "completed")
        self.assertEqual(states["2026-07-18"], "pending")
        self.assertEqual(states["2026-07-19"], "future")
        self.assertEqual(states["2026-07-17"], "unscheduled")

        self.assertTrue(
            self.ctx.goal_service.set_routine_completed(
                routine_id, "2026-07-11", False, as_of="2026-07-18"
            )[0]
        )
        self.assertEqual(
            self.ctx.goal_service.routine_stats(routine_id, "2026-07-18").current_streak,
            1,
        )

        # Category is presentation-only: deleting it preserves routine/check-in history.
        ok, message, _ = self.ctx.category_service.delete(self.category_id)
        self.assertTrue(ok, message)
        routine = self.ctx.goal_service.get_routine(routine_id)
        self.assertIsNone(routine.category_id)
        self.assertTrue(self.ctx.goal_service.routine_is_complete(routine_id, "2026-07-12"))

    def test_task_payload_and_notification_deep_link(self) -> None:
        task = GoalTask(42, "Lab manual", "2027-02-03 17:00", 120)
        payload = task_reminder_payload(task)
        self.assertEqual(payload.task_id, 42)
        self.assertLess(payload.reminder_epoch_ms, payload.due_epoch_ms)
        self.assertEqual(goal_task_id_from_route("timetracker://timer/goals/task/42"), 42)
        self.assertEqual(goal_task_id_from_route("/goals/task/42"), 42)
        self.assertIsNone(goal_task_id_from_route("/timer/countdown"))


class GoalMigrationTests(unittest.TestCase):
    def test_old_custom_range_survives_nullable_interval_migration(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "legacy.db")
            conn = sqlite3.connect(path)
            conn.executescript(
                """
                CREATE TABLE app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    color TEXT NOT NULL DEFAULT '#3B82F6',
                    is_productive INTEGER NOT NULL DEFAULT 1,
                    daily_target_minutes INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    target_value INTEGER NOT NULL,
                    period TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                INSERT INTO app_meta(key, value) VALUES ('first_run', 'done');
                INSERT INTO categories(id, name) VALUES (7, 'Legacy study');
                INSERT INTO goals(
                    id, title, category_id, target_value, period, start_date, end_date
                ) VALUES (9, 'Legacy range', 7, 120, 'custom', '2026-01-01', '2026-01-31');
                """
            )
            conn.commit()
            conn.close()

            ctx = AppContext(path)
            try:
                goal = ctx.goal_service.get(9)
                self.assertEqual(goal.title, "Legacy range")
                self.assertEqual(goal.end_date, "2026-01-31")
                self.assertIsNone(goal.interval_count)
                self.assertIsNone(goal.interval_unit)
                self.assertEqual(ctx.get_setting("schema_version"), config.SCHEMA_VERSION)
                tables = {
                    row[0] for row in ctx.db.conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                self.assertIn("goal_tasks", tables)
                self.assertIn("goal_routines", tables)
                self.assertIn("goal_routine_checkins", tables)
            finally:
                ctx.close()


class _DialogPage:
    """Tiny synchronous model of Flet's managed dialog stack."""

    def __init__(self) -> None:
        self.dialogs: list[ft.DialogControl] = []
        self.overlay: list[ft.Control] = []

    def show_dialog(self, dialog) -> None:
        dialog.open = True
        self.dialogs.append(dialog)

    def pop_dialog(self) -> None:
        dialog = self.dialogs.pop()
        dialog.open = False
        if dialog.on_dismiss:
            dialog.on_dismiss(None)


class ManagedDialogRegressionTests(unittest.TestCase):
    def test_repeated_save_cancel_and_nested_delete_leave_no_modal_barrier(self) -> None:
        page = _DialogPage()
        refreshes = []

        for action in ("save", "cancel", "delete") * 8:
            changed = {"value": False}
            sheet = form_sheet(
                "Editor",
                ft.Column(),
                [],
                lambda _e: None,
                on_dismiss=lambda _e: refreshes.append(action) if changed["value"] else None,
            )
            show_sheet(page, sheet)
            if action == "delete":
                deleted = {"value": False}
                confirmation = ft.AlertDialog(
                    on_dismiss=lambda _e: dismiss_sheet(page, sheet)
                    if deleted["value"] else None
                )
                page.show_dialog(confirmation)
                deleted["value"] = True
                changed["value"] = True
                page.pop_dialog()
            else:
                changed["value"] = action == "save"
                dismiss_sheet(page, sheet)

            self.assertEqual(page.dialogs, [])
            self.assertEqual(page.overlay, [])

        self.assertEqual(len(refreshes), 16)


class AndroidTaskReminderSourceTests(unittest.TestCase):
    def test_native_bridge_persists_restores_falls_back_and_deep_links(self) -> None:
        root = Path(
            "extensions/timetracker_android_widget/flutter/"
            "timetracker_android_widget"
        )
        kotlin = root / "android/src/main/kotlin/com/timetracker/widget"
        plugin = (kotlin / "TimetrackerAndroidWidgetPlugin.kt").read_text(encoding="utf-8")
        scheduler = (kotlin / "TaskReminderScheduler.kt").read_text(encoding="utf-8")
        store = (kotlin / "TaskReminderStore.kt").read_text(encoding="utf-8")
        notifier = (kotlin / "TaskReminderNotifier.kt").read_text(encoding="utf-8")
        manifest = (root / "android/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        dart = (root / "lib/src/timer_bridge_service.dart").read_text(encoding="utf-8")

        self.assertIn('"syncTaskReminders"', plugin)
        self.assertIn('"notification_requested"', plugin)
        self.assertIn("setExactAndAllowWhileIdle", scheduler)
        self.assertIn("setAndAllowWhileIdle", scheduler)
        self.assertIn("getSharedPreferences", store)
        self.assertIn("timetracker://timer/goals/task/", notifier)
        self.assertIn("ReminderRestoreReceiver", manifest)
        self.assertIn("android.intent.action.BOOT_COMPLETED", manifest)
        self.assertIn("android.intent.action.TIME_SET", manifest)
        self.assertIn("sync_task_reminders", dart)
        self.assertIn("args ?? const <dynamic>[]", dart)
        self.assertIn("cancel_task_reminder", dart)


if __name__ == "__main__":
    unittest.main()
