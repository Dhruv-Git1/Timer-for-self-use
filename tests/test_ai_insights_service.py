from __future__ import annotations

import os
import tempfile
import unittest

from app.services.context import AppContext
from app.utils import time_utils


class AiInsightsServiceTests(unittest.TestCase):
    def test_recent_report_is_local_and_includes_zero_activity_days(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            ctx = AppContext(os.path.join(folder, "test.db"))
            try:
                study = next(c for c in ctx.category_service.list_categories() if c.name == "Study")
                today = time_utils.today_str()
                ok, message, _ = ctx.entry_service.add_entry(study.id, today, "09:00", "10:00")
                self.assertTrue(ok, message)
                saved = ctx.daily_reflection_service.save(
                    today, "I slept well and began before my phone distracted me."
                )
                self.assertIn("slept well", saved)

                report = ctx.ai_insights_service.recent_report(days=3)

                self.assertEqual(report["window"]["days"], 3)
                self.assertEqual(len(report["daily"]), 3)
                self.assertEqual(report["daily"][-1]["productive_minutes"], 60)
                self.assertEqual(report["period_summary"]["active_days"], 1)
                self.assertEqual(report["category_minutes"]["Study"], 60)
                self.assertEqual(len(report["daily_reflections"]), 1)
                self.assertEqual(report["daily_reflections"][0]["date"], today)
            finally:
                ctx.close()

    def test_all_history_report_reads_database_and_stays_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            ctx = AppContext(os.path.join(folder, "test.db"))
            try:
                categories = {c.name: c for c in ctx.category_service.list_categories()}
                study = categories["Study"]
                ok, message, sleep_id = ctx.category_service.create(
                    "Sleep", "#64748B", False, 0
                )
                self.assertTrue(ok, message)
                self.assertIsNotNone(sleep_id)
                today = time_utils.today_str()

                entries = (
                    (study.id, "2024-01-02", "09:00", "10:00"),
                    (sleep_id, "2024-01-02", "22:00", "06:00"),
                    (study.id, today, "14:00", "14:30"),
                )
                for category_id, log_date, start, end in entries:
                    ok, message, _ = ctx.entry_service.add_entry(
                        category_id, log_date, start, end
                    )
                    self.assertTrue(ok, message)

                for offset in range(65):
                    ctx.daily_reflection_service.save(
                        time_utils.add_days(today, -offset),
                        f"Reflection {offset}: slept well and started early. " + "x" * 600,
                    )

                report = ctx.ai_insights_service.all_history_report()

                self.assertEqual(report["source"], "local_database_all_history")
                self.assertEqual(report["data_coverage"]["first_date"], "2024-01-02")
                self.assertEqual(report["data_coverage"]["last_date"], today)
                self.assertEqual(report["data_coverage"]["sessions"], 3)
                self.assertEqual(report["all_time_summary"]["recorded_minutes"], 570)
                self.assertEqual(report["all_time_summary"]["productive_minutes"], 90)
                self.assertEqual(len(report["recent_daily"]), 2)
                self.assertLessEqual(len(report["recent_monthly"]), 36)
                self.assertEqual(len(report["daily_reflections"]), 60)
                self.assertTrue(
                    all(len(item["note"]) <= 500 for item in report["daily_reflections"])
                )
                category_minutes = {
                    item["category"]: item["minutes"]
                    for item in report["top_categories"]
                }
                self.assertEqual(category_minutes["Study"], 90)
                self.assertEqual(category_minutes["Sleep"], 480)
            finally:
                ctx.close()


if __name__ == "__main__":
    unittest.main()
