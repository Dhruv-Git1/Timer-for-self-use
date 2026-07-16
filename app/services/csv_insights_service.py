"""Streaming, privacy-preserving summaries for Time Tracker CSV exports.

The CSV may have years of sessions.  This service never loads all rows, never
reads the free-text ``notes`` column, and never sends CSV bytes to Gemini.  It
reduces the file locally to a small aggregate packet instead.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from datetime import date
from typing import Any


class CsvInsightsError(ValueError):
    """A clear, recoverable problem with a selected CSV export."""


class CsvInsightsService:
    """Stream the app's CSV export into a bounded report for AI Coach."""

    REQUIRED_COLUMNS = frozenset({"date", "duration_minutes", "category", "productive"})
    RECENT_DAYS = 60
    RECENT_MONTHS = 36
    TOP_CATEGORIES = 15

    def report_from_path(self, path: str) -> dict[str, Any]:
        """Summarize a Time Tracker CSV in one pass with bounded output size."""
        if not path or not os.path.isfile(path):
            raise CsvInsightsError("The selected CSV file is no longer available.")
        if not path.lower().endswith(".csv"):
            raise CsvInsightsError("Choose a .csv export from Time Tracker.")

        # A few thousand distinct dates/months/categories stay small even when
        # the source has millions of sessions; individual session rows do not.
        daily: dict[str, dict[str, Any]] = {}
        monthly: dict[str, dict[str, int]] = defaultdict(
            lambda: {"productive_minutes": 0, "recorded_minutes": 0, "sessions": 0}
        )
        yearly: dict[str, dict[str, int]] = defaultdict(
            lambda: {"productive_minutes": 0, "recorded_minutes": 0, "sessions": 0}
        )
        categories: dict[str, int] = defaultdict(int)
        rows = 0
        skipped_rows = 0
        first_date: str | None = None
        last_date: str | None = None

        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                fields = set(reader.fieldnames or [])
                missing = self.REQUIRED_COLUMNS - fields
                if missing:
                    names = ", ".join(sorted(missing))
                    raise CsvInsightsError(
                        f"This is not a Time Tracker CSV export (missing {names})."
                    )

                for row in reader:
                    rows += 1
                    try:
                        log_date = self._validated_date(row["date"])
                        minutes = int(row["duration_minutes"])
                    except (KeyError, TypeError, ValueError):
                        skipped_rows += 1
                        continue
                    if minutes <= 0:
                        skipped_rows += 1
                        continue

                    productive = self._as_bool(row.get("productive", ""))
                    category = (row.get("category") or "Uncategorised").strip() or "Uncategorised"
                    bucket = daily.setdefault(
                        log_date,
                        {"date": log_date, "productive_minutes": 0, "recorded_minutes": 0, "sessions": 0},
                    )
                    bucket["recorded_minutes"] += minutes
                    bucket["sessions"] += 1
                    if productive:
                        bucket["productive_minutes"] += minutes

                    month = log_date[:7]
                    year = log_date[:4]
                    monthly[month]["recorded_minutes"] += minutes
                    monthly[month]["sessions"] += 1
                    yearly[year]["recorded_minutes"] += minutes
                    yearly[year]["sessions"] += 1
                    if productive:
                        monthly[month]["productive_minutes"] += minutes
                        yearly[year]["productive_minutes"] += minutes
                    categories[category] += minutes
                    first_date = log_date if first_date is None or log_date < first_date else first_date
                    last_date = log_date if last_date is None or log_date > last_date else last_date
        except OSError as exc:
            raise CsvInsightsError("Could not read the selected CSV file.") from exc

        if not daily:
            raise CsvInsightsError("The CSV has no valid time entries to analyze.")

        recent_daily = [daily[key] for key in sorted(daily)[-self.RECENT_DAYS:]]
        recent_monthly = [
            {"month": month, **values}
            for month, values in sorted(monthly.items())[-self.RECENT_MONTHS:]
        ]
        yearly_history = [
            {"year": year, **values} for year, values in sorted(yearly.items())
        ]
        top_categories = [
            {"category": name, "minutes": minutes}
            for name, minutes in sorted(categories.items(), key=lambda item: (-item[1], item[0]))[
                : self.TOP_CATEGORIES
            ]
        ]
        total_recorded = sum(item["recorded_minutes"] for item in daily.values())
        total_productive = sum(item["productive_minutes"] for item in daily.values())

        return {
            "source": "csv_export",
            "privacy": "CSV rows and free text stayed on device; only aggregates are included.",
            "data_coverage": {
                "first_date": first_date,
                "last_date": last_date,
                "valid_sessions": rows - skipped_rows,
                "skipped_rows": skipped_rows,
            },
            "all_time_summary": {
                "productive_minutes": total_productive,
                "recorded_minutes": total_recorded,
                "active_days": len(daily),
                "categories": len(categories),
            },
            "recent_daily": recent_daily,
            "recent_monthly": recent_monthly,
            "yearly_history": yearly_history,
            "top_categories": top_categories,
        }

    @staticmethod
    def _validated_date(value: str) -> str:
        # Parse instead of trusting an arbitrary string, while preserving the
        # canonical ISO date used by the export and its chronological ordering.
        return date.fromisoformat(value).isoformat()

    @staticmethod
    def _as_bool(value: object) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "y"}
