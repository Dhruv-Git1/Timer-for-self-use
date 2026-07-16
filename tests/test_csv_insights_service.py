from __future__ import annotations

import csv
import os
import tempfile
import unittest

from app.services.csv_insights_service import CsvInsightsError, CsvInsightsService


class CsvInsightsServiceTests(unittest.TestCase):
    def test_csv_is_streamed_into_a_bounded_note_free_report(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "history.csv")
            with open(path, "w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=["date", "duration_minutes", "category", "productive", "notes"],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {"date": "2023-01-01", "duration_minutes": 60, "category": "Study", "productive": "True", "notes": "private"},
                        {"date": "2025-07-10", "duration_minutes": 30, "category": "Reading", "productive": "true", "notes": "private"},
                        {"date": "2026-07-10", "duration_minutes": 90, "category": "Study", "productive": "false", "notes": "private"},
                    ]
                )

            report = CsvInsightsService().report_from_path(path)

            self.assertEqual(report["data_coverage"]["valid_sessions"], 3)
            self.assertEqual(report["all_time_summary"]["recorded_minutes"], 180)
            self.assertEqual(report["all_time_summary"]["productive_minutes"], 90)
            self.assertEqual(len(report["yearly_history"]), 3)
            self.assertNotIn("notes", str(report).lower())

    def test_invalid_csv_gets_a_useful_error(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "wrong.csv")
            with open(path, "w", encoding="utf-8", newline="") as csv_file:
                csv_file.write("name,value\nexample,1\n")
            with self.assertRaises(CsvInsightsError):
                CsvInsightsService().report_from_path(path)


if __name__ == "__main__":
    unittest.main()
