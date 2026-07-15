"""The Category data object."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


TRACKING_TIMER = "timer"
TRACKING_CHECKOFF = "checkoff"
TRACKING_COUNTER = "counter"
TRACKING_MODES = {TRACKING_TIMER, TRACKING_CHECKOFF, TRACKING_COUNTER}


@dataclass
class Category:
    """One activity category, mirroring a row of the ``categories`` table.

    Using a dataclass gives us a lightweight, typed container with a readable
    ``repr`` for free — much nicer to pass around than a raw database row or a
    loose dictionary.
    """

    id: int
    name: str
    color: str
    is_productive: bool
    daily_target_minutes: int
    sort_order: int = 0
    is_archived: bool = False
    tracking_mode: str = TRACKING_TIMER
    daily_target_count: int = 1
    unit_label: str = "times"
    include_in_daily_score: bool = True
    score_weight: int = 1

    @property
    def has_target(self) -> bool:
        """True when this category has a daily goal set (target > 0)."""
        if self.tracking_mode == TRACKING_TIMER:
            return self.daily_target_minutes > 0
        return True

    @property
    def is_timer(self) -> bool:
        return self.tracking_mode == TRACKING_TIMER

    @property
    def is_checkoff(self) -> bool:
        return self.tracking_mode == TRACKING_CHECKOFF

    @property
    def is_counter(self) -> bool:
        return self.tracking_mode == TRACKING_COUNTER

    @property
    def target_value(self) -> int:
        if self.is_timer:
            return self.daily_target_minutes
        if self.is_checkoff:
            return 1
        return self.daily_target_count

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Category":
        """Build a Category from a database row.

        The integer 0/1 flags stored in SQLite are converted to real booleans
        here so the rest of the app can write natural ``if category.is_productive``
        checks.
        """
        keys = row.keys()
        return cls(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            is_productive=bool(row["is_productive"]),
            daily_target_minutes=row["daily_target_minutes"],
            sort_order=row["sort_order"],
            is_archived=bool(row["is_archived"]),
            tracking_mode=(
                row["tracking_mode"] if "tracking_mode" in keys else TRACKING_TIMER
            ),
            daily_target_count=(
                row["daily_target_count"] if "daily_target_count" in keys else 1
            ),
            unit_label=row["unit_label"] if "unit_label" in keys else "times",
            include_in_daily_score=(
                bool(row["include_in_daily_score"])
                if "include_in_daily_score" in keys else True
            ),
            score_weight=row["score_weight"] if "score_weight" in keys else 1,
        )
