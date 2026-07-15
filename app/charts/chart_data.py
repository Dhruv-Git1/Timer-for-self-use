"""
Chart data preparation.

Charts need tidy little lists of numbers ("here are 14 days and here are the
hours for each"). This module does that shaping — it asks the services for the
raw minutes and returns ready-to-plot series — so the drawing code in
``chart_factory`` stays purely about pixels, and the views stay simple.

Everything here reuses the same split-at-midnight aggregation the rest of the
app uses, so a chart can never disagree with the dashboard.
"""

from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from config import WEEKDAY_NAMES
from app.models.stats import CategoryInsightStats
from app.services import aggregation
from app.services.context import AppContext
from app.utils import time_utils


@dataclass
class Series:
    """A simple labelled set of values, optionally with per-bar colors."""

    labels: List[str] = field(default_factory=list)
    values: List[float] = field(default_factory=list)
    colors: List[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True when there is nothing (or only zeros) to plot."""
        return not self.values or all(v == 0 for v in self.values)


class ChartDataProvider:
    """Builds the number series behind each chart from the live database."""

    def __init__(self, context: AppContext) -> None:
        self.ctx = context
        self.categories = context.category_repo
        self.entries = context.entry_repo

    # ------------------------------------------------------------------ #
    # Shared building blocks
    # ------------------------------------------------------------------ #
    def _cats_by_id(self):
        return {c.id: c for c in self.categories.list_all(include_archived=True)}

    def _daily_productive(self, start_date: str, end_date: str) -> Dict[str, int]:
        """Productive minutes per day across ``[start_date, end_date]``."""
        prev_day = time_utils.add_days(start_date, -1)
        entries = self.entries.list_by_date_range(prev_day, end_date)
        table = aggregation.build_day_category_minutes(entries, start_date, end_date)
        cats = self._cats_by_id()

        result: Dict[str, int] = {}
        day = start_date
        while day <= end_date:
            productive, _ = aggregation.productive_recorded(table.get(day, {}), cats)
            result[day] = productive
            day = time_utils.add_days(day, 1)
        return result

    # ------------------------------------------------------------------ #
    # 1. Daily productive hours (line)
    # ------------------------------------------------------------------ #
    def daily_productive_hours(self, n_days: int = 14) -> Series:
        today = time_utils.today_str()
        start = time_utils.add_days(today, -(n_days - 1))
        per_day = self._daily_productive(start, today)
        labels, values = [], []
        for day in sorted(per_day):
            labels.append(day[5:])          # "MM-DD"
            values.append(round(per_day[day] / 60, 2))
        return Series(labels=labels, values=values)

    # ------------------------------------------------------------------ #
    # 2. Weekly productivity (bar)
    # ------------------------------------------------------------------ #
    def weekly_productive_hours(self, n_weeks: int = 8) -> Series:
        today = time_utils.today_str()
        # Monday of the current week.
        this_monday = time_utils.add_days(today, -time_utils.to_date(today).weekday())
        start = time_utils.add_days(this_monday, -7 * (n_weeks - 1))
        per_day = self._daily_productive(start, today)

        labels, values = [], []
        for w in range(n_weeks):
            week_start = time_utils.add_days(start, 7 * w)
            total = sum(
                per_day.get(time_utils.add_days(week_start, d), 0) for d in range(7)
            )
            labels.append(week_start[5:])   # week-of "MM-DD"
            values.append(round(total / 60, 1))
        return Series(labels=labels, values=values)

    # ------------------------------------------------------------------ #
    # 3. Monthly totals (bar)
    # ------------------------------------------------------------------ #
    def monthly_productive_hours(self, n_months: int = 6) -> Series:
        today = time_utils.to_date(time_utils.today_str())
        year, month = today.year, today.month

        # Build the list of (year, month) buckets ending with the current month.
        months: List[Tuple[int, int]] = []
        y, m = year, month
        for _ in range(n_months):
            months.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        months.reverse()

        labels, values = [], []
        for (yy, mm) in months:
            days = _calendar.monthrange(yy, mm)[1]
            start = f"{yy:04d}-{mm:02d}-01"
            end = f"{yy:04d}-{mm:02d}-{days:02d}"
            per_day = self._daily_productive(start, end)
            labels.append(f"{_calendar.month_abbr[mm]} {str(yy)[2:]}")
            values.append(round(sum(per_day.values()) / 60, 1))
        return Series(labels=labels, values=values)

    # ------------------------------------------------------------------ #
    # 4. Category distribution (pie)
    # ------------------------------------------------------------------ #
    def category_distribution(self, n_days: int = 30) -> Series:
        today = time_utils.today_str()
        start = time_utils.add_days(today, -(n_days - 1))
        prev_day = time_utils.add_days(start, -1)
        entries = self.entries.list_by_date_range(prev_day, today)
        table = aggregation.build_day_category_minutes(entries, start, today)
        cats = self._cats_by_id()

        totals: Dict[int, int] = {}
        for per_cat in table.values():
            for cat_id, minutes in per_cat.items():
                totals[cat_id] = totals.get(cat_id, 0) + minutes

        # Sort biggest first so the pie reads cleanly.
        ordered = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
        labels, values, colors = [], [], []
        for cat_id, minutes in ordered:
            category = cats.get(cat_id)
            if category is None or minutes == 0:
                continue
            labels.append(category.name)
            values.append(round(minutes / 60, 2))
            colors.append(category.color)
        return Series(labels=labels, values=values, colors=colors)

    # ------------------------------------------------------------------ #
    # 5. Productivity trend (line + 7-day moving average)
    # ------------------------------------------------------------------ #
    def productivity_trend(self, n_days: int = 30) -> Tuple[Series, List[float]]:
        today = time_utils.today_str()
        start = time_utils.add_days(today, -(n_days - 1))
        per_day = self._daily_productive(start, today)

        days = sorted(per_day)
        values = [round(per_day[d] / 60, 2) for d in days]
        labels = [d[5:] for d in days]

        # Simple trailing 7-day moving average to smooth the daily noise.
        window = 7
        moving: List[float] = []
        for i in range(len(values)):
            lo = max(0, i - window + 1)
            chunk = values[lo:i + 1]
            moving.append(round(sum(chunk) / len(chunk), 2))
        return (Series(labels=labels, values=values), moving)

    # ------------------------------------------------------------------ #
    # 7. Per-category insights (Insights screen): calendar heatmap, weekday
    #    pattern, and a summary of one category on its own.
    # ------------------------------------------------------------------ #
    def category_day_minutes(
        self, category_id: int, start_date: str, end_date: str
    ) -> Dict[str, int]:
        """One category's minutes for every day in ``[start_date, end_date]``.

        Every day in the range gets an entry (0 when nothing was logged), so
        callers can rely on the dict covering the whole span without missing
        keys.
        """
        prev_day = time_utils.add_days(start_date, -1)
        entries = [
            e for e in self.entries.list_by_date_range(prev_day, end_date)
            if e.category_id == category_id
        ]
        table = aggregation.build_day_category_minutes(entries, start_date, end_date)

        result: Dict[str, int] = {}
        day = start_date
        while day <= end_date:
            result[day] = table.get(day, {}).get(category_id, 0)
            day = time_utils.add_days(day, 1)
        return result

    def category_year_heatmap(self, category_id: int, year: int) -> Dict[str, int]:
        """One category's minutes for every day of ``year`` (Jan 1 – Dec 31)."""
        return self.category_day_minutes(category_id, f"{year:04d}-01-01", f"{year:04d}-12-31")

    def category_weekday_pattern(self, category_id: int, n_weeks: int = 12) -> Series:
        """Average hours per weekday (Mon..Sun) for one category, last ``n_weeks``."""
        today = time_utils.today_str()
        start = time_utils.add_days(today, -7 * n_weeks)
        per_day = self.category_day_minutes(category_id, start, today)

        totals = [0] * 7
        counts = [0] * 7
        for day, minutes in per_day.items():
            weekday = time_utils.to_date(day).weekday()
            totals[weekday] += minutes
            counts[weekday] += 1

        labels = [name[:3] for name in WEEKDAY_NAMES]
        values = [
            round((totals[i] / counts[i]) / 60, 2) if counts[i] else 0.0
            for i in range(7)
        ]
        return Series(labels=labels, values=values)

    def category_summary_stats(
        self, category_id: int, start_date: str, end_date: str
    ) -> CategoryInsightStats:
        """Total / active days / current streak / best day / average for one category."""
        per_day = self.category_day_minutes(category_id, start_date, end_date)
        active = [(day, minutes) for day, minutes in per_day.items() if minutes > 0]
        total = sum(minutes for _, minutes in active)
        best_day, best_minutes = max(active, key=lambda dm: dm[1]) if active else (None, 0)
        avg = (total / len(active)) if active else 0.0

        # Current streak: consecutive days with any time logged in this
        # category, ending today (or yesterday, if today has nothing logged
        # yet, so an unfinished day never appears to break the streak).
        today = time_utils.today_str()
        cursor = today if per_day.get(today, 0) > 0 else time_utils.add_days(today, -1)
        streak = 0
        while cursor in per_day and per_day[cursor] > 0:
            streak += 1
            cursor = time_utils.add_days(cursor, -1)

        return CategoryInsightStats(
            total_minutes=total,
            active_days=len(active),
            current_streak_days=streak,
            best_day_minutes=best_minutes,
            best_day_date=best_day,
            avg_minutes_per_active_day=avg,
        )

    # ------------------------------------------------------------------ #
    # 6. Streak history (how the running streak grew and reset)
    # ------------------------------------------------------------------ #
    def streak_history(self, n_days: int = 60) -> Series:
        today = time_utils.today_str()
        start = time_utils.add_days(today, -(n_days - 1))
        prev_day = time_utils.add_days(start, -1)
        entries = self.entries.list_by_date_range(prev_day, today)
        categories = self.categories.list_all(include_archived=True)
        bounds = self.entries.date_bounds()
        first_date = bounds[0] if bounds else None

        statuses = aggregation.classify_range(
            entries, categories, start, today, first_date, today
        )

        from app.models.stats import DayStatus
        labels, values = [], []
        running = 0
        for day in sorted(statuses):
            status = statuses[day]
            if status == DayStatus.COMPLETE:
                running += 1
            elif status == DayStatus.NEUTRAL:
                pass  # carry the running value across not-applicable days
            else:
                running = 0
            labels.append(day[5:])
            values.append(running)
        return Series(labels=labels, values=values)
