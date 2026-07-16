"""A short, user-written explanation of how one day went."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class DailyReflection:
    """One optional free-text reflection, keyed by local calendar day."""

    log_date: str
    notes: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "DailyReflection":
        return cls(log_date=row["log_date"], notes=row["notes"])
