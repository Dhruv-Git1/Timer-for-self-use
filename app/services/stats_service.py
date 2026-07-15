"""
Statistics business logic.

Computes the aggregate numbers shown on the Statistics screen for any stretch of
days: totals per category, averages (session length, start time, productive time
per day), the longest session, the most and least productive weekdays, and the
current/longest streaks. There are convenience builders for the common windows —
a single day, a week, a month, a year.
"""

from __future__ import annotations

import calendar as _calendar
from typing import Dict, List

from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.entry_repo import EntryRepository
from app.models.category import Category
from app.models.stats import PeriodStats
from app.services import aggregation
from app.services.streak_service import StreakService
from app.utils import time_utils
from config import WEEKDAY_NAMES, TIME_FMT


class StatsService:
    """Builds :class:`PeriodStats` for daily/weekly/monthly/yearly windows."""

    def __init__(
        self,
        category_repo: CategoryRepository,
        entry_repo: EntryRepository,
        streak_service: StreakService,
    ) -> None:
        self.categories = category_repo
        self.entries = entry_repo
        self.streaks = streak_service

    # ------------------------------------------------------------------ #
    # Convenience windows
    # ------------------------------------------------------------------ #
    def daily(self, date_str: str) -> PeriodStats:
        return self.period_stats(date_str, date_str, label=date_str)

    def weekly(self, date_str: str) -> PeriodStats:
        """Stats for the Monday-to-Sunday week containing ``date_str``."""
        d = time_utils.to_date(date_str)
        monday = time_utils.add_days(date_str, -d.weekday())
        sunday = time_utils.add_days(monday, 6)
        return self.period_stats(monday, sunday, label=f"Week of {monday}")

    def monthly(self, year: int, month: int) -> PeriodStats:
        days = _calendar.monthrange(year, month)[1]
        start = f"{year:04d}-{month:02d}-01"
        end = f"{year:04d}-{month:02d}-{days:02d}"
        label = f"{_calendar.month_name[month]} {year}"
        return self.period_stats(start, end, label=label)

    def yearly(self, year: int) -> PeriodStats:
        return self.period_stats(f"{year}-01-01", f"{year}-12-31", label=str(year))

    # ------------------------------------------------------------------ #
    # The core aggregation
    # ------------------------------------------------------------------ #
    def period_stats(self, start_date: str, end_date: str, label: str) -> PeriodStats:
        """Compute every statistic for the window ``[start_date, end_date]``."""
        cats_by_id: Dict[int, Category] = {
            c.id: c for c in self.categories.list_all(include_archived=True)
        }

        # Split-aware per-day, per-category minutes for the window.
        prev_day = time_utils.add_days(start_date, -1)
        span_entries = self.entries.list_by_date_range(prev_day, end_date)
        table = aggregation.build_day_category_minutes(span_entries, start_date, end_date)

        # Totals across the whole window.
        minutes_by_category: Dict[str, int] = {}
        total_recorded = 0
        total_productive = 0
        weekday_productive = [0] * 7   # index 0 = Monday
        weekday_seen = [False] * 7

        for day, per_cat in table.items():
            weekday = time_utils.to_date(day).weekday()
            weekday_seen[weekday] = True
            for cat_id, minutes in per_cat.items():
                category = cats_by_id.get(cat_id)
                name = category.name if category else "Unknown"
                minutes_by_category[name] = minutes_by_category.get(name, 0) + minutes
                total_recorded += minutes
                if category and category.is_productive:
                    total_productive += minutes
                    weekday_productive[weekday] += minutes

        active_days = len(table)

        # Session-level figures use whole entries logged within the window.
        session_entries = self.entries.list_by_date_range(start_date, end_date)
        session_count = len(session_entries)
        longest_session = max(
            (e.duration_minutes for e in session_entries), default=0
        )
        avg_session = (
            sum(e.duration_minutes for e in session_entries) / session_count
            if session_count else 0.0
        )
        avg_start = self._average_start_time(session_entries)

        most_wd, least_wd = self._weekday_extremes(weekday_productive, weekday_seen)

        return PeriodStats(
            label=label,
            start_date=start_date,
            end_date=end_date,
            total_recorded_minutes=total_recorded,
            total_productive_minutes=total_productive,
            minutes_by_category=minutes_by_category,
            active_days=active_days,
            session_count=session_count,
            longest_session_minutes=longest_session,
            avg_session_minutes=avg_session,
            avg_start_time=avg_start,
            current_streak=self.streaks.current_streak(),
            longest_streak=self.streaks.longest_streak(),
            most_productive_weekday=most_wd,
            least_productive_weekday=least_wd,
            avg_productive_minutes_per_active_day=(
                total_productive / active_days if active_days else 0.0
            ),
        )

    # ------------------------------------------------------------------ #
    # Small helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _average_start_time(entries: List) -> str:
        """Average clock start time across entries, as "HH:MM" (or "—" if none).

        We average the minutes-since-midnight of each start, which is the
        intuitive "what time do I usually begin" number. (It does not try to be
        clever about, say, 23:00 and 01:00 wrapping around midnight — for a
        personal tracker the plain average is clear and good enough.)
        """
        if not entries:
            return "—"
        total = 0
        for e in entries:
            t = time_utils.parse_ts(e.start_ts)
            total += t.hour * 60 + t.minute
        avg = round(total / len(entries))
        return f"{avg // 60:02d}:{avg % 60:02d}"

    @staticmethod
    def _weekday_extremes(productive: List[int], seen: List[bool]) -> tuple[str, str]:
        """Names of the most and least productive weekdays (among days seen)."""
        candidates = [i for i in range(7) if seen[i]]
        if not candidates:
            return ("—", "—")
        most = max(candidates, key=lambda i: productive[i])
        least = min(candidates, key=lambda i: productive[i])
        return (WEEKDAY_NAMES[most], WEEKDAY_NAMES[least])
