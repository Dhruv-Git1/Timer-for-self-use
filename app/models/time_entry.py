"""The TimeEntry data object."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from app.utils import time_utils


@dataclass
class TimeEntry:
    """One logged activity session, mirroring a row of ``time_entries``.

    The category name and color are carried alongside the raw fields so the UI
    can show a labelled, colored row without a second database lookup. They are
    filled in by the repository via a JOIN and may be ``None`` for a freshly
    built entry that has not been saved yet.
    """

    id: int
    category_id: int
    log_date: str          # "YYYY-MM-DD" — the day the session started
    start_ts: str          # canonical "YYYY-MM-DD HH:MM"
    end_ts: str            # canonical; may be the next day
    duration_minutes: int
    crosses_midnight: bool
    notes: str = ""
    category_name: Optional[str] = None
    category_color: Optional[str] = None
    is_productive: Optional[bool] = None

    # -- Convenience views used by the UI ------------------------------- #
    @property
    def start_time(self) -> str:
        """Just the start clock time, e.g. "23:00"."""
        return time_utils.ts_to_time(self.start_ts)

    @property
    def end_time(self) -> str:
        """Just the end clock time, e.g. "07:00"."""
        return time_utils.ts_to_time(self.end_ts)

    @property
    def duration_label(self) -> str:
        """Human duration, e.g. "8h" or "2h 30m"."""
        return time_utils.fmt_duration(self.duration_minutes)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TimeEntry":
        """Build a TimeEntry from a database row.

        Handles rows that include the joined category columns as well as rows
        that do not, so the same mapper works for every query.
        """
        keys = row.keys()
        return cls(
            id=row["id"],
            category_id=row["category_id"],
            log_date=row["log_date"],
            start_ts=row["start_ts"],
            end_ts=row["end_ts"],
            duration_minutes=row["duration_minutes"],
            crosses_midnight=bool(row["crosses_midnight"]),
            notes=row["notes"],
            category_name=row["category_name"] if "category_name" in keys else None,
            category_color=row["category_color"] if "category_color" in keys else None,
            is_productive=(
                bool(row["is_productive"]) if "is_productive" in keys else None
            ),
        )
