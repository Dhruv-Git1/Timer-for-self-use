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


@dataclass
class CategoryAnalytics:
    """Computed per-category numbers for the Insights screen — plain counting
    and averaging only, no fitted/predictive model."""

    consistency_pct: int                 # % of the last 30 days with any activity
    momentum_pct: Optional[int]          # last-30-days total vs the 30 before (signed %)
    avg_session_minutes: int             # average length of one session
    session_count: int                   # number of sessions logged (last 90 days)
    share_pct: int                       # this task's share of ALL tracked time (30d)


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

    def category_monthly_hours(self, category_id: int, year: int) -> Series:
        """One category's total hours per month (Jan..Dec) across ``year``.

        Pairs with the year heatmap on the Insights screen: the heatmap shows
        this task day-by-day, this series shows its month-by-month trend for
        the same year — so a single task's whole story lives on one screen.
        """
        per_day = self.category_day_minutes(
            category_id, f"{year:04d}-01-01", f"{year:04d}-12-31"
        )
        totals = [0] * 12
        for day, minutes in per_day.items():
            month = int(day[5:7])          # "YYYY-MM-DD" -> MM
            totals[month - 1] += minutes
        labels = [_calendar.month_abbr[m] for m in range(1, 13)]
        values = [round(minutes / 60, 1) for minutes in totals]
        return Series(labels=labels, values=values)

    def category_daily_hours(self, category_id: int, n_days: int = 30) -> Series:
        """One category's hours per day for the last ``n_days`` (a recent zoom-in
        to complement the year heatmap/monthly trend)."""
        today = time_utils.today_str()
        start = time_utils.add_days(today, -(n_days - 1))
        per_day = self.category_day_minutes(category_id, start, today)
        labels, values = [], []
        for day in sorted(per_day):
            labels.append(day[5:])          # "MM-DD"
            values.append(round(per_day[day] / 60, 2))
        return Series(labels=labels, values=values)

    def category_cumulative_hours(self, category_id: int, year: int) -> Series:
        """One category's running total of hours across ``year`` (a momentum
        line — how the yearly total built up day by day). For the current year
        it stops at today rather than trailing a flat line to Dec 31."""
        today = time_utils.today_str()
        current_year = time_utils.to_date(today).year
        start = f"{year:04d}-01-01"
        end = today if year == current_year else f"{year:04d}-12-31"
        if end < start:                     # a future year — nothing yet
            return Series()
        per_day = self.category_day_minutes(category_id, start, end)
        labels, values = [], []
        running = 0
        for day in sorted(per_day):
            running += per_day[day]
            labels.append(day[5:])          # "MM-DD"
            values.append(round(running / 60, 2))
        return Series(labels=labels, values=values)

    def category_time_of_day(self, category_id: int, n_days: int = 90) -> Series:
        """One category's hours grouped by part of the day (Night/Morning/
        Afternoon/Evening) over the last ``n_days`` — "when do you tend to do
        this?". Each session's minutes are attributed to the part of day it
        started in (four coarse buckets read cleanly on a phone; a full 24-bar
        histogram would be too dense)."""
        today = time_utils.today_str()
        start = time_utils.add_days(today, -(n_days - 1))
        entries = [
            e for e in self.entries.list_by_date_range(start, today)
            if e.category_id == category_id
        ]
        parts = [(0, 6, "Night"), (6, 12, "Morning"),
                 (12, 18, "Afternoon"), (18, 24, "Evening")]
        buckets = [0] * len(parts)
        for entry in entries:
            hour = int(entry.start_time[:2])        # "HH:MM" -> HH
            for i, (lo, hi, _name) in enumerate(parts):
                if lo <= hour < hi:
                    buckets[i] += entry.duration_minutes
                    break
        labels = [name for _lo, _hi, name in parts]
        values = [round(minutes / 60, 2) for minutes in buckets]
        return Series(labels=labels, values=values)

    def category_session_length_distribution(
        self, category_id: int, n_days: int = 90
    ) -> Series:
        """How this task's sessions break down by length over the last
        ``n_days`` — do you do many short bursts or a few long stretches?
        (A frequency histogram: bar height = number of sessions in each band.)"""
        today = time_utils.today_str()
        start = time_utils.add_days(today, -(n_days - 1))
        entries = [
            e for e in self.entries.list_by_date_range(start, today)
            if e.category_id == category_id
        ]
        bands = [(0, 15, "<15m"), (15, 30, "15–30m"), (30, 60, "30–60m"),
                 (60, 120, "1–2h"), (120, 10 ** 9, "2h+")]
        counts = [0] * len(bands)
        for entry in entries:
            for i, (lo, hi, _name) in enumerate(bands):
                if lo <= entry.duration_minutes < hi:
                    counts[i] += 1
                    break
        labels = [name for _lo, _hi, name in bands]
        return Series(labels=labels, values=[float(c) for c in counts])

    def category_analytics(self, category_id: int) -> CategoryAnalytics:
        """The "smart stats" row: consistency, momentum, average session
        length, session count, and this task's share of all tracked time —
        plain counting/averaging, nothing predictive.

        Momentum is ``None`` when there is no prior-period baseline to compare
        against (so the UI can show a dash instead of a divide-by-zero)."""
        today = time_utils.today_str()
        start_60 = time_utils.add_days(today, -59)
        per_day = self.category_day_minutes(category_id, start_60, today)
        days = sorted(per_day)
        last30 = days[-30:]
        prior30 = days[-60:-30]

        last_total = sum(per_day[d] for d in last30)
        prior_total = sum(per_day[d] for d in prior30)
        active_last30 = sum(1 for d in last30 if per_day[d] > 0)
        consistency = round(active_last30 / len(last30) * 100) if last30 else 0

        momentum: Optional[int]
        if prior_total > 0:
            momentum = round((last_total - prior_total) / prior_total * 100)
        else:
            momentum = None

        # Average session length + session count over a 90-day window.
        start_90 = time_utils.add_days(today, -89)
        sessions = [
            e for e in self.entries.list_by_date_range(start_90, today)
            if e.category_id == category_id
        ]
        avg_session = (
            round(sum(e.duration_minutes for e in sessions) / len(sessions))
            if sessions else 0
        )

        # Share of all tracked time in the same recent 30-day window.
        distribution = self.category_distribution(30)
        total_all_hours = sum(distribution.values)
        this_hours = last_total / 60
        share = round(this_hours / total_all_hours * 100) if total_all_hours > 0 else 0

        return CategoryAnalytics(
            consistency_pct=consistency,
            momentum_pct=momentum,
            avg_session_minutes=avg_session,
            session_count=len(sessions),
            share_pct=share,
        )

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
