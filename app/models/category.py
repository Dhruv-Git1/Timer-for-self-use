"""The Category data object."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


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

    @property
    def has_target(self) -> bool:
        """True when this category has a daily goal set (target > 0)."""
        return self.daily_target_minutes > 0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Category":
        """Build a Category from a database row.

        The integer 0/1 flags stored in SQLite are converted to real booleans
        here so the rest of the app can write natural ``if category.is_productive``
        checks.
        """
        return cls(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            is_productive=bool(row["is_productive"]),
            daily_target_minutes=row["daily_target_minutes"],
            sort_order=row["sort_order"],
            is_archived=bool(row["is_archived"]),
        )
