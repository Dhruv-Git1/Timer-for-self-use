"""
Calendar business logic.

Turns a month into a ``{date: DayStatus}`` map so the calendar view can paint
each day cell green, amber, red or grey. Reuses the same classifier the
dashboard and streaks use, so the colors always agree with everything else.
"""

from __future__ import annotations

import calendar as _calendar
from typing import Dict, List

from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.entry_repo import EntryRepository
from app.models.stats import DayStatus
from app.models.time_entry import TimeEntry
from app.services import aggregation
from app.utils import time_utils


class CalendarService:
    """Provides per-day status colors and day detail for the calendar view."""

    def __init__(
        self, category_repo: CategoryRepository, entry_repo: EntryRepository
    ) -> None:
        self.categories = category_repo
        self.entries = entry_repo

    def month_status(self, year: int, month: int) -> Dict[str, DayStatus]:
        """Return a status for every day of the given month.

        ``month`` is 1-12. Days with no data, days before your first entry, and
        future days all come back as NEUTRAL (grey).
        """
        days_in_month = _calendar.monthrange(year, month)[1]
        first_day = f"{year:04d}-{month:02d}-01"
        last_day = f"{year:04d}-{month:02d}-{days_in_month:02d}"

        bounds = self.entries.date_bounds()
        first_date = bounds[0] if bounds else None

        # Fetch one extra day at the start so an overnight session from the last
        # day of the previous month contributes to day 1 correctly.
        prev_day = time_utils.add_days(first_day, -1)
        entries = self.entries.list_by_date_range(prev_day, last_day)
        categories = self.categories.list_all(include_archived=True)

        return aggregation.classify_range(
            entries, categories, first_day, last_day,
            first_date, time_utils.today_str(),
        )

    def day_entries(self, date_str: str) -> List[TimeEntry]:
        """All entries logged on a given day (for the click-through detail panel)."""
        return self.entries.list_by_date(date_str)

    @staticmethod
    def month_matrix(year: int, month: int) -> List[List[int]]:
        """A week-by-week grid of day numbers for laying out the calendar.

        Each inner list is one week of seven day-numbers, Monday first, with 0
        used for days that belong to the neighbouring month. Comes straight from
        Python's standard ``calendar`` module.
        """
        return _calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
