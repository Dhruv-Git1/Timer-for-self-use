"""Longer-horizon goal data and period vocabulary."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime


PERIOD_WEEKLY = "weekly"
PERIOD_BIWEEKLY = "biweekly"
PERIOD_MONTHLY = "monthly"
PERIOD_CUSTOM = "custom"
PERIOD_TIMELESS = "timeless"
GOAL_PERIODS = {
    PERIOD_WEEKLY,
    PERIOD_BIWEEKLY,
    PERIOD_MONTHLY,
    PERIOD_CUSTOM,
    PERIOD_TIMELESS,
}
INTERVAL_UNITS = {"days", "weeks", "months"}


@dataclass
class Goal:
    """One user-defined target attached to a tracked category."""

    id: int
    title: str
    category_id: int
    target_value: int
    period: str
    start_date: str
    end_date: str | None = None
    is_archived: bool = False
    interval_count: int | None = None
    interval_unit: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Goal":
        columns = set(row.keys())
        return cls(
            id=row["id"],
            title=row["title"],
            category_id=row["category_id"],
            target_value=row["target_value"],
            period=row["period"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            is_archived=bool(row["is_archived"]),
            interval_count=(row["interval_count"] if "interval_count" in columns else None),
            interval_unit=(row["interval_unit"] if "interval_unit" in columns else None),
        )

    @property
    def is_custom_interval(self) -> bool:
        return self.period == PERIOD_CUSTOM and self.interval_count is not None


@dataclass
class GoalProgress:
    """A goal plus the current window and derived tracked progress."""

    goal: Goal
    category_name: str
    category_color: str
    tracking_mode: str
    unit_label: str
    window_start: str
    window_end: str
    window_label: str
    actual: int

    @property
    def completion_pct(self) -> float:
        if self.goal.target_value <= 0:
            return 0.0
        return self.actual / self.goal.target_value * 100.0

    @property
    def is_complete(self) -> bool:
        return self.actual >= self.goal.target_value


@dataclass
class GoalTask:
    """An independent one-off checkbox task."""

    id: int
    title: str
    due_at: str | None = None
    reminder_offset_minutes: int | None = None
    completed_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "GoalTask":
        return cls(
            id=row["id"],
            title=row["title"],
            due_at=row["due_at"],
            reminder_offset_minutes=row["reminder_offset_minutes"],
            completed_at=row["completed_at"],
        )

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def completed_date(self) -> str | None:
        return self.completed_at[:10] if self.completed_at else None

    @property
    def reminder_at(self) -> datetime | None:
        if self.due_at is None or self.reminder_offset_minutes is None:
            return None
        from datetime import timedelta
        return datetime.strptime(self.due_at, "%Y-%m-%d %H:%M") - timedelta(
            minutes=self.reminder_offset_minutes
        )


@dataclass
class GoalRoutine:
    """A permanent checkbox goal scheduled on selected weekdays."""

    id: int
    title: str
    category_id: int | None
    weekdays_mask: int
    start_date: str
    is_archived: bool = False

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "GoalRoutine":
        return cls(
            id=row["id"],
            title=row["title"],
            category_id=row["category_id"],
            weekdays_mask=row["weekdays_mask"],
            start_date=row["start_date"],
            is_archived=bool(row["is_archived"]),
        )


@dataclass(frozen=True)
class RoutineStats:
    completed: int
    scheduled: int
    completion_pct: float
    current_streak: int


@dataclass(frozen=True)
class GoalHistory:
    labels: list[str]
    actual_values: list[float]
    target_values: list[float]
    unit_label: str
