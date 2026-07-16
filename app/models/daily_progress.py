"""Daily checkbox/counter values and the Android-only Today score."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import List

from app.models.category import TRACKING_TIMER
from app.utils import time_utils


@dataclass
class DailyProgress:
    """One persisted checkbox/counter value for one local calendar date."""

    category_id: int
    log_date: str
    value: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "DailyProgress":
        return cls(
            category_id=row["category_id"],
            log_date=row["log_date"],
            value=row["value"],
        )


@dataclass
class DailyScoreItem:
    """Unit-neutral progress for one goal-bearing category."""

    category_id: int
    name: str
    color: str
    tracking_mode: str
    actual: int
    target: int
    unit_label: str
    included: bool
    weight: int = 1

    @property
    def completion_pct(self) -> float:
        if self.target <= 0:
            return 0.0
        return min(100.0, self.actual / self.target * 100.0)

    @property
    def actual_label(self) -> str:
        if self.tracking_mode == TRACKING_TIMER:
            return time_utils.fmt_duration(self.actual)
        return str(self.actual)

    @property
    def target_label(self) -> str:
        if self.tracking_mode == TRACKING_TIMER:
            return time_utils.fmt_duration(self.target)
        return str(self.target)


@dataclass
class DailyScore:
    """All daily category progress plus their weighted average score."""

    date: str
    items: List[DailyScoreItem] = field(default_factory=list)

    @property
    def scored_items(self) -> List[DailyScoreItem]:
        return [item for item in self.items if item.included]

    @property
    def average_pct(self) -> float:
        """The weighted completion average across included categories."""
        scored = self.scored_items
        if not scored:
            return 0.0
        total_weight = sum(max(1, item.weight) for item in scored)
        return sum(
            item.completion_pct * max(1, item.weight) for item in scored
        ) / total_weight

    @property
    def has_scored_categories(self) -> bool:
        return bool(self.scored_items)
