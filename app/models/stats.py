"""
Computed result objects for the dashboard and statistics screens.

Nothing here touches the database. These are the tidy shapes the services hand
back after they have done the counting, so the UI can simply read fields off an
object instead of juggling loose numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

import config
from app.utils import time_utils


class DayStatus(str, Enum):
    """How a single day turned out.

    Subclassing ``str`` means a DayStatus can be used directly as a dictionary
    key or compared with the string constants in config without extra fuss.
    """

    COMPLETE = config.STATUS_COMPLETE   # green  – every targeted category met
    PARTIAL = config.STATUS_PARTIAL     # yellow – some but not all met
    FAILED = config.STATUS_FAILED       # red    – past day, targets, none met
    NEUTRAL = config.STATUS_NEUTRAL     # grey   – no targets / future / pre-data

    @property
    def color(self) -> str:
        """The hex color used to paint this status on the calendar."""
        return config.STATUS_COLORS[self.value]

    @property
    def label(self) -> str:
        """A human word for the status, e.g. "Complete"."""
        return self.value.capitalize()


@dataclass
class CategoryProgress:
    """One row of the dashboard's target-vs-actual table."""

    category_id: int
    name: str
    color: str
    target_minutes: int
    actual_minutes: int

    @property
    def difference_minutes(self) -> int:
        """Actual minus target. Positive means you beat the goal."""
        return self.actual_minutes - self.target_minutes

    @property
    def completion_pct(self) -> float:
        """How much of the goal was met, 0-100 (capped at 100 for display)."""
        if self.target_minutes <= 0:
            return 100.0  # no goal to miss
        return min(100.0, self.actual_minutes / self.target_minutes * 100.0)

    @property
    def is_met(self) -> bool:
        """True when the actual time reaches the target."""
        return self.target_minutes > 0 and self.actual_minutes >= self.target_minutes

    @property
    def target_label(self) -> str:
        return time_utils.fmt_duration(self.target_minutes) if self.target_minutes else "—"

    @property
    def actual_label(self) -> str:
        return time_utils.fmt_duration(self.actual_minutes)

    @property
    def difference_label(self) -> str:
        """Signed difference, e.g. "+30m" or "-1h 15m"."""
        diff = self.difference_minutes
        sign = "+" if diff >= 0 else "-"
        return f"{sign}{time_utils.fmt_duration(abs(diff))}"


@dataclass
class DailySummary:
    """Everything the dashboard needs to describe one day."""

    date: str
    status: DayStatus
    productive_minutes: int          # only productive categories
    recorded_minutes: int            # every category
    total_target_minutes: int        # sum of targets across productive categories
    session_count: int
    longest_session_minutes: int
    current_streak: int
    progress: List[CategoryProgress] = field(default_factory=list)

    @property
    def completion_pct(self) -> float:
        """Overall progress toward the combined daily target, 0-100."""
        if self.total_target_minutes <= 0:
            return 0.0
        return min(100.0, self.productive_minutes / self.total_target_minutes * 100.0)

    @property
    def is_complete(self) -> bool:
        return self.status == DayStatus.COMPLETE

    # Ready-made display labels so the UI stays free of formatting code.
    @property
    def productive_label(self) -> str:
        return time_utils.fmt_duration(self.productive_minutes)

    @property
    def recorded_label(self) -> str:
        return time_utils.fmt_duration(self.recorded_minutes)

    @property
    def longest_session_label(self) -> str:
        return time_utils.fmt_duration(self.longest_session_minutes) if self.longest_session_minutes else "—"


@dataclass
class CategoryInsightStats:
    """Summary numbers for one category over a chosen date range (the Insights screen)."""

    total_minutes: int
    active_days: int
    current_streak_days: int
    best_day_minutes: int
    best_day_date: Optional[str]
    avg_minutes_per_active_day: float

    @property
    def total_label(self) -> str:
        return time_utils.fmt_duration(self.total_minutes)

    @property
    def best_day_label(self) -> str:
        return time_utils.fmt_duration(self.best_day_minutes) if self.best_day_minutes else "—"

    @property
    def avg_label(self) -> str:
        return time_utils.fmt_duration(int(round(self.avg_minutes_per_active_day))) if self.active_days else "—"


@dataclass
class PeriodStats:
    """Aggregated statistics over a stretch of days (week / month / year)."""

    label: str                                   # e.g. "July 2026"
    start_date: str
    end_date: str
    total_recorded_minutes: int
    total_productive_minutes: int
    minutes_by_category: Dict[str, int] = field(default_factory=dict)
    active_days: int = 0                          # days with at least one entry
    session_count: int = 0
    longest_session_minutes: int = 0
    avg_session_minutes: float = 0.0
    avg_start_time: str = "—"                     # average clock start, or "—"
    current_streak: int = 0
    longest_streak: int = 0
    most_productive_weekday: str = "—"
    least_productive_weekday: str = "—"
    avg_productive_minutes_per_active_day: float = 0.0
