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


if __name__ == "__main__":
    unittest.main()
