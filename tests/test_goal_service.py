"""Regression coverage for longer-horizon goal definitions and progress."""

from __future__ import annotations

import os
import tempfile
import unittest

from app.models.goal import (
    PERIOD_BIWEEKLY,
    PERIOD_CUSTOM,
    PERIOD_MONTHLY,
    PERIOD_TIMELESS,
    PERIOD_WEEKLY,
)
from app.services.context import AppContext


class GoalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.ctx = AppContext(os.path.join(self.temp.name, "goals.db"))
        for category in self.ctx.category_service.list_categories():
            self.ctx.category_service.set_archived(category.id, True)

        ok, message, self.timer_id = self.ctx.category_service.create(
            "Deep work", "#3B82F6", True, 0
        )
        self.assertTrue(ok, message)
        ok, message, self.counter_id = self.ctx.category_service.create(
            "Pages", "#10B981", False, 0,
            tracking_mode="counter", target_count=1, unit_label="pages",
        )
        self.assertTrue(ok, message)

    def tearDown(self) -> None:
        self.ctx.close()
        self.temp.cleanup()

    def _add_timer_time(self, log_date: str, start: str, end: str) -> None:
        ok, message, _ = self.ctx.entry_service.add_entry(
            self.timer_id, log_date, start, end
        )
        self.assertTrue(ok, message)

    def _create(self, title, category_id, target, period, start, end=None):
        ok, message, goal_id = self.ctx.goal_service.create(
            title, category_id, target, period, start, end
        )
        self.assertTrue(ok, message)
        return goal_id

    def test_weekly_monthly_and_timeless_goals_use_logged_timer_minutes(self) -> None:
        self._add_timer_time("2026-07-13", "09:00", "10:00")
        self._add_timer_time("2026-07-16", "09:00", "10:30")
        self._add_timer_time("2026-06-30", "09:00", "10:00")
        weekly_id = self._create(
            "Weekly focus", self.timer_id, 120, PERIOD_WEEKLY, "2026-07-13"
        )
        monthly_id = self._create(
            "July focus", self.timer_id, 180, PERIOD_MONTHLY, "2026-07-01"
        )
        timeless_id = self._create(
            "Research project", self.timer_id, 210, PERIOD_TIMELESS, "2026-06-30"
        )

        progress = {item.goal.id: item for item in self.ctx.goal_service.progress_for("2026-07-16")}

        self.assertEqual(progress[weekly_id].actual, 150)
        self.assertTrue(progress[weekly_id].is_complete)
        self.assertEqual(progress[monthly_id].actual, 150)
        self.assertEqual(progress[timeless_id].actual, 210)
        self.assertTrue(progress[timeless_id].is_complete)

    def test_biweekly_and_custom_goals_sum_counter_progress_in_their_windows(self) -> None:
        self.ctx.daily_progress_service.set_amount(self.counter_id, "2026-07-14", 9)
        self.ctx.daily_progress_service.set_amount(self.counter_id, "2026-07-15", 2)
        self.ctx.daily_progress_service.set_amount(self.counter_id, "2026-07-16", 3)
        biweekly_id = self._create(
            "Read five pages", self.counter_id, 5, PERIOD_BIWEEKLY, "2026-07-01"
        )
        custom_id = self._create(
            "Launch reading sprint", self.counter_id, 14, PERIOD_CUSTOM,
            "2026-07-14", "2026-07-16",
        )

        progress = {item.goal.id: item for item in self.ctx.goal_service.progress_for("2026-07-16")}

        # 14-day cycles begin on the chosen start date, so July 15 starts cycle two.
        self.assertEqual(progress[biweekly_id].window_start, "2026-07-15")
        self.assertEqual(progress[biweekly_id].actual, 5)
        self.assertTrue(progress[biweekly_id].is_complete)
        self.assertEqual(progress[custom_id].actual, 14)
        self.assertEqual(progress[custom_id].window_end, "2026-07-16")

    def test_custom_goal_requires_dates_and_category_deletion_is_protected(self) -> None:
        ok, message, goal_id = self.ctx.goal_service.create(
            "Incomplete", self.timer_id, 60, PERIOD_CUSTOM, "2026-07-15"
        )
        self.assertFalse(ok)
        self.assertIsNone(goal_id)
        self.assertIn("end date", message)

        self._create("Keep category", self.timer_id, 60, PERIOD_TIMELESS, "2026-07-15")
        ok, message, _ = self.ctx.category_service.delete(self.timer_id)
        self.assertFalse(ok)
        self.assertIn("goal", message)

    def test_goal_validation_rejects_archived_category_and_bad_target(self) -> None:
        self.ctx.category_service.set_archived(self.counter_id, True)
        ok, message, _ = self.ctx.goal_service.create(
            "Archived", self.counter_id, 1, PERIOD_TIMELESS, "2026-07-15"
        )
        self.assertFalse(ok)
        self.assertIn("active category", message)

        ok, message, _ = self.ctx.goal_service.create(
            "Bad target", self.timer_id, 0, PERIOD_WEEKLY, "2026-07-15"
        )
        self.assertFalse(ok)
        self.assertIn("Target", message)


if __name__ == "__main__":
    unittest.main()
